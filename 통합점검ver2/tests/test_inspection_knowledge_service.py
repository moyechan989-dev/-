import json

import pandas as pd

from src.inspection_knowledge_service import (
    find_similar_dispositions,
    get_inspection_knowledge_item,
    load_inspection_knowledge,
    public_case_rows,
    search_inspection_knowledge,
)


def test_loads_twelve_read_only_knowledge_items_with_required_fields():
    items = load_inspection_knowledge()
    assert len(items) == 12
    required = {"manual_id", "category", "title", "keywords", "field_checks", "evidence_items", "legal_refs", "verification_status"}
    assert all(required <= set(item) for item in items)
    statuses = {item['manual_id']: item['verification_status'] for item in items}
    assert statuses['IG-05'] == statuses['IG-06'] == statuses['IG-08'] == '공식법령 확인'
    assert statuses['IG-07'] == '개정확인 필요'
    assert all(statuses[manual_id] == '공식법령 확인' for manual_id in ('IG-01', 'IG-02', 'IG-03', 'IG-04', 'IG-09', 'IG-10', 'IG-11', 'IG-12'))
    assert all(set(item["legal_refs"][0]) == {
        "law_name", "article", "paragraph", "role", "summary", "source_url",
        "effective_date", "source_checked_at", "verification_status",
    } for item in items)


def test_loads_legacy_and_structured_legal_references_safely(tmp_path):
    source = tmp_path / "knowledge.json"
    source.write_text(json.dumps([
        {
            "manual_id": "IG-LEGACY", "verification_status": "담당자 검토 필요",
            "effective_date": "확인 필요", "reviewed_at": "2026-09-01",
            "legal_refs": [{"law_name": "기존 법령", "article": "제1조", "check_point": "기존 확인사항"}],
        },
        {
            "manual_id": "IG-STRUCTURED", "verification_status": "공식법령 확인",
            "legal_refs": [{
                "law_name": "검증 법령", "article": "제2조", "paragraph": "제1항", "role": "업무지침",
                "summary": "등록된 요약", "source_url": "https://example.invalid/law",
                "effective_date": "2026-01-01", "source_checked_at": "2026-09-01",
                "verification_status": "공식법령 확인",
            }],
        },
    ], ensure_ascii=False), encoding="utf-8")

    legacy, structured = load_inspection_knowledge(source)
    assert legacy["verification_status"] == "미검증"
    assert legacy["effective_date"] == "" and legacy["reviewed_at"] == ""
    assert legacy["legal_refs"][0]["summary"] == "기존 확인사항"
    assert structured["legal_refs"][0]["source_url"] == "https://example.invalid/law"
    assert structured["legal_refs"][0]["verification_status"] == "공식법령 확인"


def test_searches_by_keyword_category_and_manual_id_without_inference():
    items = [
        {"manual_id": "IG-A", "category": "전자관리", "title": "Record entry", "keywords": ["record"]},
        {"manual_id": "IG-B", "category": "시설관리", "title": "Facility", "keywords": ["facility"]},
    ]
    assert [item["manual_id"] for item in search_inspection_knowledge(items, "record")] == ["IG-A"]
    assert [item["manual_id"] for item in search_inspection_knowledge(items, category="시설관리")] == ["IG-B"]
    assert get_inspection_knowledge_item(items, "IG-B")["title"] == "Facility"


def test_searches_legal_reference_and_verification_status():
    items = [{
        "manual_id": "IG-LAW", "category": "법령", "title": "Law item", "keywords": [], "verification_status": "미검증",
        "legal_refs": [{"law_name": "검증 법령", "article": "제2조", "paragraph": "", "role": "의무근거", "verification_status": "미검증"}],
    }]
    assert [item["manual_id"] for item in search_inspection_knowledge(items, "검증 법령")] == ["IG-LAW"]
    assert [item["manual_id"] for item in search_inspection_knowledge(items, verification_status="미검증")] == ["IG-LAW"]


def test_similar_cases_use_only_keywords_and_public_rows_remove_private_columns():
    dispositions = pd.DataFrame([
        {"company_name": "비공개 업체", "representative_alias": "가명", "address": "비공개 주소", "violation_content": "record missing", "violation_category": "entry", "legal_basis": "rule", "administrative_disposition": "warning", "accusation": "-", "penalty": "-", "disposition_date": "2026-09-01"},
        {"company_name": "다른 업체", "violation_content": "other", "violation_category": "other", "legal_basis": "other", "administrative_disposition": "-", "accusation": "-", "penalty": "-", "disposition_date": "2026-08-01"},
    ])
    matched = find_similar_dispositions(dispositions, {"keywords": ["record"]})
    rows = public_case_rows(matched)
    assert len(rows) == 1
    assert rows[0]["violation_content"] == "record missing"
    assert "company_name" not in rows[0] and "representative_alias" not in rows[0] and "address" not in rows[0]


def test_knowledge_items_five_to_eight_use_confirmed_checks_without_automatic_judgment():
    items = {item['manual_id']: item for item in load_inspection_knowledge()}
    assert '허가증상 허용보관량 확인' in items['IG-05']['field_checks']
    assert '올바로시스템 관련 내역' in items['IG-05']['evidence_items']
    assert any(ref['article'] == '제31조' and ref['verification_status'] == '공식법령 확인' for ref in items['IG-05']['legal_refs'])
    assert '변경내용이 변경허가 대상인지 변경신고 대상인지 구분 확인' in items['IG-06']['field_checks']
    assert {ref['article'] for ref in items['IG-06']['legal_refs']} >= {'제29조', '제33조'}
    assert '영상 저장장치 운영 여부 확인' in items['IG-07']['field_checks']
    assert any(ref['article'] == '제31조의2' and ref['verification_status'] == '개정확인 필요' for ref in items['IG-07']['legal_refs'])
    assert '현장 보관상태가 시행규칙 별표 5의 해당 기준과 맞는지 확인' in items['IG-08']['field_checks']
    assert any(ref['article'] == '제14조 및 별표 5' and ref['verification_status'] == '공식법령 확인' for ref in items['IG-08']['legal_refs'])


def test_knowledge_items_nine_to_twelve_use_confirmed_checks_without_automatic_judgment():
    items = {item['manual_id']: item for item in load_inspection_knowledge()}
    assert {ref['article'] for ref in items['IG-09']['legal_refs']} == {'제30조', '제41조', '별표 10', '해당 시설별 검사방법'}
    assert '시설 종류별 검사주기 확인' in items['IG-09']['follow_up_checks']
    assert {ref['article'] for ref in items['IG-10']['legal_refs']} == {'제32조', '별표 8'}
    assert '업체 업종에 해당하는 별표 8의 개별 준수사항 확인' in items['IG-10']['field_checks']
    assert {ref['article'] for ref in items['IG-11']['legal_refs']} == {'제40조', '제18조', '제21조', '제22조', '제63조의2', '적용 대상 및 업무처리 기준'}
    assert '자동 산정하거나 적정 여부를 확정하지 않는다' in items['IG-11']['caution']
    assert {ref['article'] for ref in items['IG-12']['legal_refs']} == {'제39조의2', '제39조의3', '제48조'}
    assert any(check.startswith('A. 사업장폐기물배출자의 보관기간 초과 관련 처리명령:') for check in items['IG-12']['field_checks'])
    assert any(check.startswith('B. 폐기물처리업자 등에 대한 보관폐기물 처리명령:') for check in items['IG-12']['field_checks'])
    assert any(check.startswith('C. 부적정처리폐기물에 대한 조치명령:') for check in items['IG-12']['field_checks'])


def test_knowledge_items_one_to_four_use_confirmed_checks_without_automatic_judgment():
    items = {item['manual_id']: item for item in load_inspection_knowledge()}
    assert {ref['article'] for ref in items['IG-01']['legal_refs']} == {'제18조', '제20조', '별표 6'}
    assert items['IG-01']['legal_refs'][0]['paragraph'] == '제3항'
    assert {'계량값', '위치정보', '영상정보'} <= set().union(*(set(check.split()) for check in items['IG-01']['field_checks']))
    assert {ref['article'] for ref in items['IG-02']['legal_refs']} == {'제36조', '제58조'}
    assert '종이 장부의 존재 여부만으로 적정 여부를 판단하지 않는다' in items['IG-02']['caution']
    assert {ref['article'] for ref in items['IG-03']['legal_refs']} == {'제38조', '제60조'}
    assert any('다음 연도 2월 말일까지' in ref['summary'] for ref in items['IG-03']['legal_refs'])
    assert {ref['article'] for ref in items['IG-04']['legal_refs']} == {'제35조', '제50조'}
    assert any('추가교육' in check for check in items['IG-04']['field_checks'])
    assert '자동 판정' not in items['IG-04']['caution']


def test_searches_field_expressions_and_preserves_review_statuses():
    items = load_inspection_knowledge()
    expectations = {
        '폐기물이 너무 많이 쌓여': 'IG-05',
        'CCTV 화면': 'IG-07',
        '허가증에 없는 기계': 'IG-06',
        '보험증권': 'IG-11',
        '처리명령 폐기물이 아직 남아': 'IG-12',
    }
    for expression, manual_id in expectations.items():
        assert manual_id in {item['manual_id'] for item in search_inspection_knowledge(items, expression)}
    assert all(item['trigger_conditions'] and item['inspector_questions'] and item['common_mistakes'] for item in items)
    statuses = {item['manual_id']: item['verification_status'] for item in items}
    assert statuses['IG-07'] == '개정확인 필요'
    assert all(statuses[manual_id] == '공식법령 확인' for manual_id in statuses if manual_id != 'IG-07')
    prohibited = ('위반으로 판단됩니다', '법 위반입니다', '행정처분 대상입니다', '영업정지입니다')
    added_values = [value for item in items for field in ('trigger_conditions', 'inspector_questions', 'common_mistakes') for value in item[field]]
    assert not any(term in value for term in prohibited for value in added_values)

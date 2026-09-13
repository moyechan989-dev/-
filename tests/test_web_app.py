from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import web_app
from web_app import create_web_app


class FakeWebRepository:
    def __init__(self):
        self.calls: list[str] = []
        self.secret_key = "test-secret-must-not-be-rendered"

    def list_companies(self) -> pd.DataFrame:
        self.calls.append("list_companies")
        return pd.DataFrame([
            {
                "company_id": "COM-1", "company_name": "가나다환경", "company_name_normalized": "가나다환경",
                "permit_number": "허가-1", "address": "화성시 남양읍", "address_normalized": "화성시남양읍",
                "district": "남양읍", "industry": "폐기물처리업", "entity_type": "법인",
                "is_2026_target": "Y", "planned_inspection_type": "정기",
            },
            {
                "company_id": "COM-2", "company_name": "라마바사자원", "company_name_normalized": "라마바사자원",
                "permit_number": "허가-2", "address": "화성시 동탄", "address_normalized": "화성시동탄",
                "district": "동탄", "industry": "재활용업", "entity_type": "개인",
                "is_2026_target": "N", "planned_inspection_type": "수시",
            },
        ])

    def list_aliases(self) -> pd.DataFrame:
        self.calls.append("list_aliases")
        return pd.DataFrame([{"company_id": "COM-1", "alias_value": "가나다", "normalized_value": "가나다"}])

    def get_counts(self) -> dict[str, int]:
        self.calls.append("get_counts")
        return {"companies": 2, "aliases": 1, "inspections": 7, "dispositions": 3}

    def get_company(self, company_id: str) -> pd.DataFrame:
        return self.list_companies().loc[lambda frame: frame["company_id"].eq(company_id)].copy()

    def list_inspections(self) -> pd.DataFrame:
        return pd.DataFrame([{"inspection_id": "INS-1", "company_id": "COM-1", "inspection_date": "2026-08-27", "inspection_type": "정기", "inspection_result_status": "적정", "inspection_media": "폐기물"}])

    def get_inspections(self, company_id: str) -> pd.DataFrame:
        return self.list_inspections().loc[lambda frame: frame["company_id"].eq(company_id)].copy()

    def get_dispositions(self, company_id: str) -> pd.DataFrame:
        return pd.DataFrame([{"disposition_id": "DSP-1", "company_id": "COM-1", "company_name": "가나다환경", "disposition_date": "2026-08-26", "violation_content": "위반내용", "violation_category": "유형", "administrative_disposition": "경고", "accusation": "", "penalty": "", "legal_basis": "법령", "disposition_status": "완료"}]).loc[lambda frame: frame["company_id"].eq(company_id)].copy()

    def load_all(self) -> dict[str, pd.DataFrame]:
        return {"companies": self.list_companies(), "aliases": self.list_aliases(), "inspections": self.list_inspections(), "dispositions": self.get_dispositions("COM-1")}

    def get_district_counts(self) -> pd.DataFrame:
        return pd.DataFrame([{"지역별 업체 수": "남양읍", "업체 수": 1}])

    def get_industry_counts(self) -> pd.DataFrame:
        return pd.DataFrame([{"업종별 업체 수": "폐기물처리업", "업체 수": 1}])

    def get_2026_target_count(self) -> int:
        return 1


def make_client() -> tuple[TestClient, FakeWebRepository]:
    repository = FakeWebRepository()
    return TestClient(create_web_app(lambda: repository)), repository


def test_root_redirects_to_companies_page():
    client, _ = make_client()
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/companies"


def test_companies_page_uses_existing_repository_and_renders_actual_counts():
    client, repository = make_client()
    response = client.get("/companies")
    assert response.status_code == 200
    assert "검색 결과" in response.text and ">2</strong>개 업체" in response.text
    assert "등록 업체" in response.text and ">7<" in response.text and ">3<" in response.text
    assert "가나다환경" in response.text and "라마바사자원" in response.text
    assert repository.calls == ["list_companies", "list_aliases", "get_counts"]


def test_companies_query_and_filter_match_existing_search_service_rules():
    client, _ = make_client()
    query_response = client.get("/companies", params={"query": "가나다"})
    filter_response = client.get("/companies", params={"industry": "재활용업"})
    assert "가나다환경" in query_response.text and "라마바사자원" not in query_response.text
    assert "라마바사자원" in filter_response.text and "가나다환경" not in filter_response.text


def test_companies_empty_result_and_secrets_are_not_rendered():
    client, _ = make_client()
    response = client.get("/companies", params={"district": "없는 지역"})
    assert response.status_code == 200
    assert "검색 결과" in response.text and ">0</strong>개 업체" in response.text
    assert "조건에 맞는 업체가 없습니다" in response.text
    assert "test-secret-must-not-be-rendered" not in response.text


def test_new_fastapi_pages_render_and_unknown_company_is_safe():
    client, _ = make_client()
    for path in ["/companies/COM-1", "/inspections/new", "/dispositions", "/reports", "/dashboard"]:
        assert client.get(path).status_code == 200
    assert client.get("/companies/UNKNOWN").status_code == 404


def test_inspection_preview_validates_without_local_write_and_excel_is_in_memory():
    client, _ = make_client()
    invalid = client.post("/inspections/preview", data={"company_id": "COM-1"})
    assert invalid.status_code == 200 and "필수 입력항목" in invalid.text
    preview = client.post("/inspections/preview", data={"company_id": "COM-1", "inspection_date": "2026-09-01", "inspection_type": "정기", "inspection_result_status": "적정"})
    assert preview.status_code == 200 and "로컬 모드에서는 DB 저장이 지원되지 않습니다" in preview.text
    for path in ["/exports/companies", "/exports/companies/COM-1", "/exports/all"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")


def test_report_upload_uses_existing_pdf_processor_without_ai_call():
    client, _ = make_client()
    response = client.post("/reports", files=[("files", ("검증.txt", b"test", "text/plain"))])
    assert response.status_code == 200
    assert "파일 오류" in response.text
    assert 'id="analyze-button"' in response.text


def test_presentation_keeps_korean_labels_navigation_and_local_mode_notices(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client, _ = make_client()
    companies = client.get("/companies")
    for menu in ["업체 조회", "지도점검 등록", "행정처분 이력", "출장보고서 AI", "데이터 현황"]:
        assert menu in companies.text

    dispositions = client.get("/dispositions")
    assert "업체명" in dispositions.text
    assert "company_name" not in dispositions.text
    assert "2026-08-26" in dispositions.text

    reports = client.get("/reports")
    for step in ["01</span> PDF 업로드 및 텍스트 추출", "02</span> AI 분석", "03</span> 분석 결과 확인"]:
        assert step in reports.text
    assert "AI 연결 설정이 필요합니다." in reports.text
    assert "현재 로컬 개발모드입니다" not in reports.text

    inspection = client.get("/inspections/new")
    assert "로컬 모드에서는 DB 저장이 지원되지 않습니다" in inspection.text
    assert "test-secret-must-not-be-rendered" not in reports.text


def test_inspection_guide_lists_knowledge_and_keeps_private_case_fields_hidden():
    client, _ = make_client()
    guide = client.get("/inspection-guide")
    assert guide.status_code == 200
    assert "IG-01" in guide.text and "IG-12" in guide.text

    detail = client.get("/inspection-guide", params={"manual_id": "IG-01"})
    assert detail.status_code == 200
    assert "guide-case-table" in detail.text
    assert "legal-reference-table" in detail.text
    assert 'status-badge--official' in detail.text
    assert "company_name" not in detail.text
    assert "자동 위반판정" not in detail.text
    assert "담당자가 최종 판단" in detail.text

    inspection = client.get("/inspections/new")
    assert inspection.status_code == 200
    assert "/inspection-guide" in inspection.text


def test_inspection_guide_renders_structured_official_law_link(monkeypatch):
    item = {
        "manual_id": "IG-LINK", "category": "검증", "title": "구조화된 법령", "keywords": ["test"],
        "applies_to": [], "field_checks": [], "evidence_items": [], "follow_up_checks": [], "caution": "",
        "verification_status": "공식법령 확인", "effective_date": "", "reviewed_at": "",
        "legal_refs": [{
            "law_name": "검증 법령", "article": "제1조", "paragraph": "", "role": "의무근거",
            "summary": "기존 입력 요약", "source_url": "https://example.invalid/law",
            "effective_date": "", "source_checked_at": "", "verification_status": "공식법령 확인",
        }],
    }
    monkeypatch.setattr(web_app, "load_inspection_knowledge", lambda: [item])
    client, _ = make_client()
    response = client.get("/inspection-guide", params={"manual_id": "IG-LINK"})
    assert response.status_code == 200
    assert "https://example.invalid/law" in response.text
    assert 'target="_blank"' in response.text
    assert 'rel="noopener noreferrer"' in response.text


def test_dispositions_default_to_recent_twenty_but_searches_all_records():
    client, repository = make_client()
    records = pd.DataFrame([
        {
            "disposition_id": f"DSP-{index:02}", "company_id": "COM-1", "company_name": f"업체 {index}",
            "disposition_date": f"2026-08-{index:02}", "violation_content": "전체검색대상" if index == 1 else "일반 위반",
            "violation_category": "유형", "administrative_disposition": "경고", "accusation": "", "penalty": "", "legal_basis": "법령", "disposition_status": "완료",
        }
        for index in range(1, 26)
    ])
    repository.load_all = lambda: {"companies": repository.list_companies(), "aliases": repository.list_aliases(), "inspections": repository.list_inspections(), "dispositions": records}

    recent = client.get("/dispositions")
    assert recent.status_code == 200
    assert recent.text.count('class="company-cell"') == 20
    assert "?view=all" in recent.text

    all_rows = client.get("/dispositions", params={"view": "all"})
    assert all_rows.status_code == 200
    assert all_rows.text.count('class="company-cell"') == 25
    assert "?view=all" not in all_rows.text

    searched = client.get("/dispositions", params={"query": "전체검색대상"})
    assert searched.status_code == 200
    assert searched.text.count('class="company-cell"') == 1


def test_inspection_guide_renders_updated_knowledge_statuses_and_details():
    client, _ = make_client()
    for manual_id in ('IG-05', 'IG-06', 'IG-08'):
        response = client.get('/inspection-guide', params={'manual_id': manual_id})
        assert response.status_code == 200
        assert '공식법령 확인' in response.text
        assert 'legal-reference-table' in response.text
    response = client.get('/inspection-guide', params={'manual_id': 'IG-07'})
    assert response.status_code == 200
    assert '개정확인 필요' in response.text
    assert '제31조의2' in response.text
    assert '영상 저장장치 운영 여부 확인' in response.text
    assert 'CCTV 설치현황' in response.text


def test_inspection_guide_renders_confirmed_items_nine_to_twelve():
    client, _ = make_client()
    expectations = {
        'IG-09': ('제30조', '제41조', '별표 10', '해당 시설별 검사방법', '사업장에 설치·운영 중인 폐기물처리시설 종류 확인'),
        'IG-10': ('제32조', '별표 8', '업체 업종에 해당하는 별표 8의 개별 준수사항 확인'),
        'IG-11': ('제40조', '제18조', '제21조', '제22조', '제63조의2', '적용 대상 및 업무처리 기준'),
        'IG-12': ('제39조의2', '제39조의3', '제48조', 'A. 사업장폐기물배출자의 보관기간 초과 관련 처리명령:', 'B. 폐기물처리업자 등에 대한 보관폐기물 처리명령:', 'C. 부적정처리폐기물에 대한 조치명령:'),
    }
    for manual_id, values in expectations.items():
        response = client.get('/inspection-guide', params={'manual_id': manual_id})
        assert response.status_code == 200
        assert '공식법령 확인' in response.text
        assert all(value in response.text for value in values)
    response = client.get('/inspection-guide', params={'manual_id': 'IG-12'})
    assert '자동 확정하지 않는다' in response.text


def test_inspection_guide_renders_confirmed_items_one_to_four():
    client, _ = make_client()
    expectations = {
        'IG-01': ('제18조', '제3항', '제20조', '별표 6', '계량값', '위치정보', '영상정보'),
        'IG-02': ('제36조', '제58조', '업체의 정확한 폐기물처리업 업종 확인', '종이 장부의 존재 여부만으로 적정 여부를 판단하지 않는다'),
        'IG-03': ('제38조', '제60조', '다음 연도 2월 말일까지', '장부·올바로·계근자료 상호 대조'),
        'IG-04': ('제35조', '제50조', '해당 대상자에게 적용되는 재교육 주기 확인', '추가교육 대상이 발생했다면 추가교육 이수 여부 확인'),
    }
    for manual_id, values in expectations.items():
        response = client.get('/inspection-guide', params={'manual_id': manual_id})
        assert response.status_code == 200
        assert '공식법령 확인' in response.text
        assert all(value in response.text for value in values)
    response = client.get('/inspection-guide', params={'manual_id': 'IG-04'})
    assert '자동 판정' not in response.text


def test_inspection_guide_searches_field_expressions_and_renders_field_aids():
    client, _ = make_client()
    expectations = {
        '폐기물이 너무 많이 쌓여': 'IG-05',
        'CCTV 화면': 'IG-07',
        '허가증에 없는 기계': 'IG-06',
        '보험증권': 'IG-11',
        '처리명령 폐기물이 아직 남아': 'IG-12',
    }
    for expression, manual_id in expectations.items():
        response = client.get('/inspection-guide', params={'query': expression})
        assert response.status_code == 200
        assert manual_id in response.text
    detail = client.get('/inspection-guide', params={'manual_id': 'IG-05'})
    assert '이런 상황에서 확인' in detail.text
    assert '현장에서 물어볼 사항' in detail.text
    assert '놓치기 쉬운 점' in detail.text
    assert '현재 보관 중인 폐기물은 종류별로 얼마나 됩니까?' in detail.text
    assert '위반으로 판단됩니다' not in detail.text
    overview = client.get('/inspection-guide')
    assert '이런 경우 확인:' in overview.text


def test_local_inspection_checklist_supports_selection_progress_notes_and_removal():
    client, _ = make_client()
    guide = client.get('/inspection-guide')
    assert guide.status_code == 200
    assert '이번 점검에 담기' in guide.text

    added = client.post('/inspection-checklist/items/IG-05', data={'return_to': '/inspection-checklist'})
    assert added.status_code == 200
    assert '선택 매뉴얼 <strong>1개</strong>' in added.text
    assert '이번 점검에 담김' in client.get('/inspection-guide', params={'manual_id': 'IG-05'}).text
    assert 'IG-05' in added.text and '현장 확인사항' in added.text and '확보·확인할 자료' in added.text

    duplicate = client.post('/inspection-checklist/items/IG-05', data={'return_to': '/inspection-checklist'})
    assert duplicate.status_code == 200
    assert '선택 매뉴얼 <strong>1개</strong>' in duplicate.text

    progressed = client.post('/inspection-checklist/items/IG-05/progress', data={'field_checked': ['0', '1'], 'evidence_checked': ['0'], 'field_note': '현장 수량과 계근자료를 대조함', 'return_to': '/inspection-checklist'})
    assert progressed.status_code == 200
    assert '현장 확인사항 <strong>2 / 10</strong> 확인' in progressed.text
    assert '확보자료 <strong>1 / 7</strong> 확인' in progressed.text
    assert '현장 수량과 계근자료를 대조함' in progressed.text
    assert progressed.text.count('checked') >= 3

    common_note = client.post('/inspection-checklist/common-note', data={'common_note': '현장 공통 메모'})
    assert common_note.status_code == 200 and '현장 공통 메모' in common_note.text

    inspection = client.get('/inspections/new')
    assert inspection.status_code == 200
    assert '이번 점검 체크리스트' in inspection.text and 'IG-05' in inspection.text

    removed = client.post('/inspection-checklist/items/IG-05', data={'action': 'remove', 'return_to': '/inspection-checklist'})
    assert removed.status_code == 200
    assert '아직 선택한 점검 매뉴얼이 없습니다.' in removed.text


def test_local_inspection_checklist_shows_revision_notice_without_legal_judgment():
    client, _ = make_client()
    response = client.post('/inspection-checklist/items/IG-07', data={'return_to': '/inspection-checklist'})
    assert response.status_code == 200
    assert '개정확인 필요' in response.text
    assert '이 항목은 법령 개정 여부를 추가 확인해야 합니다.' in response.text
    assert '위반으로 판단됩니다' not in response.text

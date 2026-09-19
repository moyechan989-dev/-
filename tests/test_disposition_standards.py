import json

import pytest

from src.disposition_standards import (
    STANDARDS_FILE, get_disposition_standard, load_disposition_standards,
    search_disposition_standards,
)
from tests.test_support_ui import Elements
from tests.test_web_app import make_client


def test_catalog_is_complete_and_sorted_even_when_file_order_changes(tmp_path):
    payload = json.loads(STANDARDS_FILE.read_text(encoding='utf-8'))
    payload['standards'].reverse()
    path = tmp_path / 'standards.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    items = load_disposition_standards(path)
    assert len(items) == 15
    assert [item['priority'] for item in items] == list(range(1, 16))
    assert len({item['id'] for item in items}) == 15
    for item in items:
        assert {'id', 'priority', 'category', 'title', 'short_summary', 'keywords', 'legal_basis',
                'variants', 'field_checks', 'source', 'source_date'} <= item.keys()
        for variant in item['variants']:
            assert variant['conditions'] and variant['source']['page'] > 0
            assert variant['sanctions'] is None or len(variant['sanctions']) == 4
            for fine in variant['related_fines']:
                assert len(fine['amounts_manwon']) == 3
                assert '시행령' in fine['source']['file']
                assert fine['conditions']


@pytest.mark.parametrize('query, expected', [
    ('CCTV', 'DS-03'), ('ｃｃｔｖ', 'DS-03'), ('60일', 'DS-03'),
    ('올바로', 'DS-02'), ('변경신고', 'DS-04'), ('장부', 'DS-05'),
    ('누출', 'DS-01'), ('사업장 밖', 'DS-01'), ('제31조제4항', 'DS-13'),
])
def test_keyword_and_condition_search(query, expected):
    assert expected in {item['id'] for item in search_disposition_standards(query)}


def test_combined_category_filter_and_empty_results():
    assert [item['id'] for item in search_disposition_standards('올바로', '장부·보고')] == ['DS-05']
    assert not search_disposition_standards('CCTV', '보관')
    assert not search_disposition_standards('등록되지않은위반유형')
    assert not search_disposition_standards('', '없는분류')
    assert len(search_disposition_standards('  ')) == 15
    assert get_disposition_standard('없는ID') is None


def test_legal_branch_boundaries_are_preserved():
    storage = get_disposition_standard('DS-01')['variants']
    assert storage[0]['sanctions'] == ['영업정지 1개월', '영업정지 3개월', '영업정지 6개월', '허가취소']
    assert storage[1]['sanctions'][0] == '경고'
    assert any('18조제1항' in c for c in storage[0]['conditions'])
    assert any('16)가)' in c for c in storage[2]['conditions'])
    cctv = get_disposition_standard('DS-03')['variants']
    assert [v['sanctions'][0] for v in cctv] == ['영업정지 1개월', '경고', '경고']
    assert all(not v['related_fines'] for v in cctv)
    change = get_disposition_standard('DS-04')['variants']
    assert [v['sanctions'][0] for v in change] == ['영업정지 6개월', '영업정지 1개월', '경고']
    assert change[0]['sanctions'][2:] == [None, None]
    assert not change[0]['related_fines'] and not change[1]['related_fines']
    assert change[2]['related_fines'][0]['amounts_manwon'] == [100, 200, 300]


def test_fine_only_records_do_not_invent_administrative_sanctions():
    for identifier in ('DS-06', 'DS-07'):
        assert all(v['sanctions'] is None for v in get_disposition_standard(identifier)['variants'])
    report = get_disposition_standard('DS-07')['variants']
    assert report[0]['related_fines'][0]['amounts_manwon'] == [50, 70, 100]
    assert report[1]['related_fines'][0]['amounts_manwon'] == [300, 600, 1000]
    assert all(any('1/2' in c for c in v['conditions']) for v in get_disposition_standard('DS-10')['variants'])


def test_catalog_return_values_are_independent():
    item = get_disposition_standard('DS-03')
    item['variants'][0]['sanctions'][0] = '오염된 값'
    assert get_disposition_standard('DS-03')['variants'][0]['sanctions'][0] == '영업정지 1개월'


def test_standards_route_renders_variants_fines_and_closed_details():
    client, _ = make_client()
    response = client.get('/inspection-guide?tab=standards')
    assert response.status_code == 200
    elements = Elements(response.text).elements
    cards = [attrs for tag, attrs in elements if tag == 'article' and attrs.get('class') == 'ds-card']
    assert len(cards) == 15
    assert all('open' not in attrs for tag, attrs in elements if tag == 'details')
    assert '영상정보 60일 저장·보관 미준수' in response.text
    assert '관련 과태료' in response.text and '3차 이상' in response.text
    assert '별표 21에서 직접 행정처분 기준 확인 필요' in response.text
    assert '과태료가 없다는 의미가 아닙니다' in response.text
    assert '적발 빈도순' not in response.text
    assert '등록된 기준에서 일치하는 항목을 찾지 못했습니다.' in response.text


@pytest.mark.parametrize('tab', ['manuals', 'laws', 'cases', 'forms', 'standards'])
def test_other_tabs_keep_selected_panel_and_existing_manual(tab):
    client, _ = make_client()
    response = client.get('/inspection-guide', params={'tab': tab, 'manual_id': 'IG-02'})
    assert response.status_code == 200
    panels = [a for tag, a in Elements(response.text).elements
              if tag == 'section' and a.get('id') in ('manuals', 'laws', 'cases', 'forms', 'standards')]
    assert [p['id'] for p in panels if 'hidden' not in p] == [tab]
    assert 'IG-02' in response.text
    assert 'legal-reference-table' in response.text
    assert '현재 등록된 서식이 없습니다.' in response.text

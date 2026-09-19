from html.parser import HTMLParser

from tests.test_web_app import make_client


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_main_pages_link_to_support_without_registration_actions():
    client, _ = make_client()
    for path in ["/companies", "/companies/COM-1", "/inspection-guide", "/dispositions", "/reports", "/dashboard", "/inspection-checklist"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "지도점검 등록" not in response.text
        links = [attrs.get("href", "") for tag, attrs in Elements(response.text).elements if tag == "a"]
        assert any(link.endswith("/inspection-guide") for link in links)
        assert not any("/inspections/new" in link for link in links)


def test_support_hub_sections_and_honest_empty_states():
    client, _ = make_client()
    response = client.get("/inspection-guide")
    elements = Elements(response.text).elements
    ids = {attrs.get("id") for _, attrs in elements}
    assert {"manuals", "laws", "standards", "cases", "forms"} <= ids
    assert "주요 확인항목" in response.text
    assert 'data-standard-id="DS-01"' in response.text
    assert "현재 등록된 서식이 없습니다." in response.text
    assert "이번 점검에 담기" not in response.text
    assert not any(tag == "a" and "download" in attrs for tag, attrs in elements)
    cards = [attrs for tag, attrs in elements if tag == "article" and attrs.get("class") == "guide-card"]
    assert len(cards) == 12
    assert all(attrs.get('action', '').endswith('/inspection-guide/ai')
               for tag, attrs in elements if tag == 'form' and attrs.get('method') == 'post')


def test_support_cases_use_only_existing_records_and_hide_identifiers():
    client, _ = make_client()
    response = client.get("/inspection-guide", params={"query": "위반내용"})
    assert "위반내용" in response.text and "2026-08-26" in response.text
    assert "경고" in response.text
    assert "가나다환경" not in response.text and "COM-1" not in response.text
    absent = client.get("/inspection-guide", params={"query": "존재하지않는자료"})
    assert "현재 키워드와 일치하는 과거 사례가 없습니다." in absent.text
    assert "2026-08-26" not in absent.text


def test_manual_detail_preserves_filters_and_original_law_links():
    client, _ = make_client()
    response = client.get("/inspection-guide", params={"manual_id": "IG-05", "query": "보관"})
    assert response.status_code == 200
    assert "legal-reference-table" in response.text
    assert 'class="law-summary-col"' in response.text
    assert "확인요약" in response.text
    assert 'class="date-cell"' in response.text
    assert "query=%EB%B3%B4%EA%B4%80" in response.text
    assert "이번 점검에 담기" not in response.text
    assert "처분기준으로 적용하지 않습니다" in response.text

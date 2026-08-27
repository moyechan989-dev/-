from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

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

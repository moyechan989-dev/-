import pandas as pd

from src.search_service import search_companies


def companies():
    return pd.DataFrame([
        {"company_id": "COM-1", "company_name": "가나 환경", "company_name_normalized": "가나환경", "permit_number": "P-1", "address": "가나다로 1", "address_normalized": "가나다로1", "district": "가동", "industry": "처리업", "entity_type": "업체", "is_2026_target": "Y", "planned_inspection_type": "정기"},
        {"company_id": "COM-2", "company_name": "가나환경산업", "company_name_normalized": "가나환경산업", "permit_number": "P-2", "address": "나다로 2", "address_normalized": "나다로2", "district": "나동", "industry": "처리업", "entity_type": "업체", "is_2026_target": "N", "planned_inspection_type": ""},
    ])


def aliases():
    return pd.DataFrame([{"company_id": "COM-2", "alias_value": "옛 상호", "normalized_value": "옛상호"}])


def test_search_ignores_case_and_space_for_company_name():
    result = search_companies(companies(), aliases(), " 가 나 환 경 ")
    assert result["company_id"].tolist() == ["COM-1", "COM-2"]


def test_search_finds_alias_without_merging_companies():
    result = search_companies(companies(), aliases(), "옛상호")
    assert result["company_id"].tolist() == ["COM-2"]


def test_search_finds_permit_number_and_partial_address():
    by_permit = search_companies(companies(), aliases(), "p-1")
    by_address = search_companies(companies(), aliases(), "로 2")
    assert by_permit["company_id"].tolist() == ["COM-1"]
    assert by_address["company_id"].tolist() == ["COM-2"]


def test_search_and_filter_apply_together_and_support_unregistered():
    result = search_companies(companies(), aliases(), "가나", {"district": "나동", "planned_inspection_type": "미등록"})
    assert result["company_id"].tolist() == ["COM-2"]


def test_search_returns_empty_result_for_unknown_text():
    result = search_companies(companies(), aliases(), "존재하지않음")
    assert result.empty

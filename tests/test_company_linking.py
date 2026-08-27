import inspect

import pandas as pd
import pytest

from src.company_linking import company_information_may_differ, confirm_company_link, recommend_company_candidates
from src.inspection_review_draft import complete_review, get_review_state, start_review
from tests.test_inspection_review_draft import report


def companies():
    return pd.DataFrame([
        {"company_id": "COM-1", "company_name": "삼우리싸이클", "company_name_normalized": "삼우리싸이클", "permit_number": "P-1", "address": "화성시 장안면 화곡로 241", "address_normalized": "화성시장안면화곡로241", "district": "장안면", "industry": "폐기물 종합재활용업"},
        {"company_id": "COM-2", "company_name": "삼우리리사이클산업", "company_name_normalized": "삼우리리사이클산업", "permit_number": "P-2", "address": "화성시 우정읍", "address_normalized": "화성시우정읍", "district": "우정읍", "industry": "폐기물처리업"},
    ])


def aliases():
    return pd.DataFrame([{"company_id": "COM-2", "alias_value": "구 삼우리", "normalized_value": "구삼우리"}])


def completed_state():
    state: dict[str, object] = {}
    review = start_review(state, "A.pdf", "A text", report())
    values = dict(review["values"])
    values.update({"inspection_date": "2026-08-27", "inspection_type": "정기", "inspection_result_status": "적정"})
    complete_review(state, "A.pdf", "A text", values)
    return state


def test_ai_company_name_candidate_searches_existing_companies():
    result = recommend_company_candidates(companies(), aliases(), "삼우리싸이클")
    assert result["company_id"].tolist() == ["COM-1"]


def test_exact_name_match_is_first_recommendation():
    result = recommend_company_candidates(companies(), aliases(), " 삼우리 싸이클 ")
    assert result.iloc[0]["candidate_reason"].startswith("업체명 정확 일치")


def test_exact_alias_match_is_recommended_without_auto_linking():
    result = recommend_company_candidates(companies(), aliases(), "구삼우리")
    assert result.iloc[0]["company_id"] == "COM-2"
    assert result.iloc[0]["candidate_reason"].startswith("업체 별칭 정확 일치")


def test_location_and_industry_are_context_for_candidate_ordering():
    result = recommend_company_candidates(companies(), aliases(), "삼우리", "장안면 화곡로 241", "폐기물 종합재활용업")
    assert result.iloc[0]["company_id"] == "COM-1"
    assert "장소/지역 참고 일치" in result.iloc[0]["candidate_reason"]


def test_no_candidate_returns_empty_result():
    assert recommend_company_candidates(companies(), aliases(), "존재하지 않는 업체").empty


def test_manual_search_can_use_existing_search_fields():
    result = recommend_company_candidates(companies(), aliases(), "P-2")
    assert result.iloc[0]["company_id"] == "COM-2"


def test_single_candidate_is_not_automatically_confirmed():
    state = completed_state()
    assert "company_link" not in next(iter(state.values()))


def test_reviewer_confirms_actual_company_id_only():
    state = completed_state()
    linked = confirm_company_link(state, "A.pdf", "A text", companies().iloc[0], confirmed=True)
    assert linked["company_link"]["selected_company_id"] == "COM-1"
    assert linked["company_link"]["selected_company_name"] == "삼우리싸이클"


def test_company_confirmation_checkbox_is_required():
    with pytest.raises(ValueError, match="확정"):
        confirm_company_link(completed_state(), "A.pdf", "A text", companies().iloc[0], confirmed=False)


def test_company_information_difference_creates_warning_only():
    assert company_information_may_differ("다른 업체", "다른 지역", companies().iloc[0]) is True


def test_pdf_company_link_states_are_independent():
    state = completed_state()
    review_b = start_review(state, "B.pdf", "B text", report())
    values_b = dict(review_b["values"])
    values_b.update({"inspection_date": "2026-08-28", "inspection_type": "정기", "inspection_result_status": "적정"})
    complete_review(state, "B.pdf", "B text", values_b)
    confirm_company_link(state, "A.pdf", "A text", companies().iloc[0], confirmed=True)
    assert get_review_state(state, "A.pdf", "A text")["company_link"]["selected_company_id"] == "COM-1"
    assert "company_link" not in get_review_state(state, "B.pdf", "B text")


def test_company_linking_has_no_database_dependency_or_fuzzy_matching():
    import src.company_linking as linking
    source = inspect.getsource(linking).lower()
    assert "repository" not in source
    assert "supabase" not in source
    assert "difflib" not in source

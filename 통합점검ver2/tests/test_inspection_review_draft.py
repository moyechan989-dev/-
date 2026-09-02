from datetime import date
import inspect
from datetime import date

import pytest

from src.ai_report_extractor import AiReportResult, BusinessInfo, ConfirmedViolation, PlannedActions
from src.inspection_review_draft import (
    build_initial_review_values,
    complete_review,
    get_review_state,
    inspection_draft_display_values,
    invalidate_review_for_new_ai_result,
    missing_required_draft_fields,
    parse_inspection_date,
    review_matches_ai_result,
    save_review_values,
    start_review,
)


def report() -> AiReportResult:
    return AiReportResult(
        report_title="출장결과보고서",
        company_name_candidate="가나다환경",
        inspection_date_raw="2025. 11. 11.(화) 14:00",
        location="화성시 사업장",
        inspection_purpose="현장 확인",
        business_info=BusinessInfo(industry="폐기물처리업", permit_numbers=("허가 1", "신고 2")),
        field_observations=("보관시설 확인", "배출시설 확인"),
        confirmed_violation=ConfirmedViolation(True, "문서 기재 위반사실", ("법령 조항",), "점검 사진"),
        planned_actions=PlannedActions("조업정지 30일 예정", "고발 예정"),
        summary=None,
        evidence=(),
        warnings=(),
    )


def test_ai_result_populates_review_initial_values():
    values = build_initial_review_values(report())
    assert values["company_name_candidate"] == "가나다환경"
    assert values["inspection_purpose"] == "현장 확인"
    assert values["key_findings"] == "보관시설 확인\n배출시설 확인"


def test_ai_original_and_reviewer_values_are_separate():
    state: dict[str, object] = {}
    original = report()
    review = start_review(state, "A.pdf", "A text", original)
    edited = dict(review["values"])
    edited["company_name_candidate"] = "담당자 수정 업체명"
    save_review_values(state, "A.pdf", "A text", edited)
    assert original.company_name_candidate == "가나다환경"
    assert get_review_state(state, "A.pdf", "A text")["values"]["company_name_candidate"] == "담당자 수정 업체명"


def test_raw_date_and_selected_inspection_date_are_separate():
    values = build_initial_review_values(report())
    values["inspection_date"] = date(2025, 11, 12)
    assert values["inspection_date_raw"] == "2025. 11. 11.(화) 14:00"
    assert values["inspection_date"] == date(2025, 11, 12)


def test_documented_violation_is_mapped_only_when_mentioned():
    values = build_initial_review_values(report())
    assert values["suspected_violation"] == "문서 기재 위반사실"
    no_violation = report().__class__(**{**report().__dict__, "confirmed_violation": ConfirmedViolation(False, "참고 문구", (), None)})
    assert build_initial_review_values(no_violation)["suspected_violation"] == ""


def test_planned_actions_remain_labelled_as_plans_and_not_dispositions():
    values = build_initial_review_values(report())
    assert "보고서상 향후 계획" in values["follow_up_action"]
    assert "administrative_disposition" not in values
    assert "accusation" not in values


def test_inspection_type_and_result_are_reviewer_choices():
    values = build_initial_review_values(report())
    assert values["inspection_type"] == ""
    assert values["inspection_result_status"] == ""


def test_multiple_pdf_review_states_remain_independent():
    state: dict[str, object] = {}
    start_review(state, "A.pdf", "A text", report())
    start_review(state, "B.pdf", "B text", report())
    first = get_review_state(state, "A.pdf", "A text")
    edited = dict(first["values"])
    edited["inspection_purpose"] = "A만 수정"
    save_review_values(state, "A.pdf", "A text", edited)
    assert get_review_state(state, "B.pdf", "B text")["values"]["inspection_purpose"] == "현장 확인"


def test_completed_review_keeps_an_inspection_draft_without_database_fields():
    state: dict[str, object] = {}
    review = start_review(state, "A.pdf", "A text", report())
    values = dict(review["values"])
    values.update({"inspection_date": date(2025, 11, 12), "inspection_type": "정기", "inspection_result_status": "적정"})
    completed = complete_review(state, "A.pdf", "A text", values)
    assert completed["status"] == "completed"
    assert "company_id" not in completed["inspection_draft"]
    assert "disposition" not in " ".join(completed["inspection_draft"])


@pytest.mark.parametrize(
    ("field", "label"),
    [("inspection_date", "점검일"), ("inspection_type", "점검유형"), ("inspection_result_status", "점검결과")],
)
def test_review_cannot_complete_without_required_inspection_value(field, label):
    state: dict[str, object] = {}
    review = start_review(state, "A.pdf", "A text", report())
    values = dict(review["values"])
    values.update({"inspection_date": date(2025, 11, 12), "inspection_type": "정기", "inspection_result_status": "적정"})
    values[field] = None
    assert missing_required_draft_fields(values) == (label,)
    with pytest.raises(ValueError, match=label):
        complete_review(state, "A.pdf", "A text", values)


def test_review_completes_when_all_required_inspection_values_exist():
    values = build_initial_review_values(report())
    values.update({"inspection_date": date(2025, 11, 12), "inspection_type": "정기", "inspection_result_status": "적정"})
    assert missing_required_draft_fields(values) == ()


def test_draft_display_values_use_korean_labels_and_safe_empty_values():
    displayed = inspection_draft_display_values({"inspection_date": None, "inspection_media": None, "key_findings": None})
    assert displayed["점검일"] == "-"
    assert displayed["점검매체"] == "미입력"
    assert displayed["주요 점검내용"] == "-"
    assert "inspection_date" not in displayed


def test_review_module_has_no_database_storage_dependency():
    import src.inspection_review_draft as review_module
    source = inspect.getsource(review_module).lower()
    assert "repository" not in source
    assert "supabase" not in source


def test_reanalysis_invalidates_existing_unsaved_review_draft():
    state: dict[str, object] = {}
    first = report()
    review = start_review(state, "A.pdf", "same text", first, ai_result_version=1)
    edited = dict(review["values"])
    edited["follow_up_action"] = "보고서상 향후 계획 - 이전 PDF 내용"
    save_review_values(state, "A.pdf", "same text", edited)
    updated = first.__class__(**{**first.__dict__, "planned_actions": PlannedActions("새 계획", None)})

    assert invalidate_review_for_new_ai_result(state, "A.pdf", "same text", updated, 2) == "invalidated"
    assert get_review_state(state, "A.pdf", "same text") is None


def test_reanalysis_invalidates_review_even_when_structured_output_is_the_same():
    state: dict[str, object] = {}
    start_review(state, "A.pdf", "same text", report(), ai_result_version=1)

    assert invalidate_review_for_new_ai_result(state, "A.pdf", "same text", report(), 2) == "invalidated"
    assert get_review_state(state, "A.pdf", "same text") is None


def test_reanalysis_preserves_already_saved_history_state():
    state: dict[str, object] = {}
    review = start_review(state, "A.pdf", "same text", report(), ai_result_version=1)
    review["final_save"] = {"status": "saved", "inspection_id": "INS-1"}
    state[next(iter(state))] = review

    assert invalidate_review_for_new_ai_result(state, "A.pdf", "same text", report(), 2) == "saved_retained"
    retained = get_review_state(state, "A.pdf", "same text")
    assert retained["final_save"]["inspection_id"] == "INS-1"
    assert retained["ai_result_changed_after_save"] is True


def test_pdf_reviews_do_not_cross_contaminate_planned_actions():
    state: dict[str, object] = {}
    first = report().__class__(**{**report().__dict__, "planned_actions": PlannedActions("A 계획", None)})
    second = report().__class__(**{**report().__dict__, "planned_actions": PlannedActions("B 계획", "B 고발")})
    review_a = start_review(state, "A.pdf", "A text", first, ai_result_version=1)
    review_b = start_review(state, "B.pdf", "B text", second, ai_result_version=1)

    assert "A 계획" in review_a["values"]["follow_up_action"]
    assert "B 계획" not in review_a["values"]["follow_up_action"]
    assert "B 계획" in review_b["values"]["follow_up_action"]
    assert "A 계획" not in review_b["values"]["follow_up_action"]


def test_initial_review_safely_suggests_date_result_and_media_values():
    source = report().__class__(**{**report().__dict__, "report_title": "대기 배출시설 출장결과보고서"})
    values = build_initial_review_values(source, result_statuses=["적정", "위반"], media_values=["대기", "서면"])
    assert values["inspection_date"] == date(2025, 11, 11)
    assert values["inspection_result_status"] == "위반"
    assert values["inspection_media"] == "대기"
    assert values["inspection_type"] == ""


def test_ambiguous_values_are_not_suggested():
    source = report().__class__(**{
        **report().__dict__,
        "inspection_date_raw": "2025년 11월 중",
        "confirmed_violation": ConfirmedViolation(None, None, (), None),
        "report_title": "일반 출장결과보고서",
    })
    values = build_initial_review_values(source, result_statuses=["위반", "적정"], media_values=["대기"])
    assert parse_inspection_date(source.inspection_date_raw) is None
    assert values["inspection_result_status"] == ""
    assert values["inspection_media"] == ""
    assert values["inspection_type"] == ""


def test_review_records_the_ai_result_version_it_was_created_from():
    state: dict[str, object] = {}
    created = start_review(state, "A.pdf", "A text", report(), ai_result_version=3)
    assert created["ai_result_version"] == 3
    assert review_matches_ai_result(created, report(), 3)
    assert not review_matches_ai_result(created, report(), 4)

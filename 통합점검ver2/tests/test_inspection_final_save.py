from datetime import date

import pandas as pd
import pytest

from src.company_linking import confirm_company_link
from src.inspection_final_save import (
    build_final_inspection_record,
    get_final_save_state,
    save_final_inspection,
)
from src.inspection_review_draft import complete_review, get_review_state, start_review
from tests.test_inspection_review_draft import report


def company() -> pd.Series:
    return pd.Series({"company_id": "COM-1", "company_name": "검증 업체", "permit_number": "P-1"})


def completed_and_linked_state() -> dict[str, object]:
    state: dict[str, object] = {}
    review = start_review(state, "A.pdf", "A text", report())
    values = dict(review["values"])
    values.update({
        "inspection_date": date(2026, 8, 27),
        "inspection_type": "정기",
        "inspection_result_status": "적정",
        "inspection_media": "서면",
    })
    complete_review(state, "A.pdf", "A text", values)
    confirm_company_link(state, "A.pdf", "A text", company(), confirmed=True)
    return state


def test_final_record_uses_review_draft_and_confirmed_actual_company_id():
    state = completed_and_linked_state()
    review = get_review_state(state, "A.pdf", "A text")
    record = build_final_inspection_record(review, company())
    assert record["company_id"] == "COM-1"
    assert record["company_name"] == "검증 업체"
    assert record["inspection_date"] == "2026-08-27"
    assert record["inspection_date_raw"] == "2026-08-27"
    assert record["inspection_purpose"] == "현장 확인"
    assert record["data_source"] == "manual_entry"
    assert record["review_status"] == "등록완료"
    assert "disposition_id" not in record
    assert "company_name_candidate" not in record


def test_final_record_requires_completed_review_and_confirmed_link():
    state: dict[str, object] = {}
    review = start_review(state, "A.pdf", "A text", report())
    with pytest.raises(ValueError, match="검토 완료"):
        build_final_inspection_record(review, company())
    values = dict(review["values"])
    values.update({"inspection_date": date(2026, 8, 27), "inspection_type": "정기", "inspection_result_status": "적정"})
    complete_review(state, "A.pdf", "A text", values)
    with pytest.raises(ValueError, match="업체 연결"):
        build_final_inspection_record(get_review_state(state, "A.pdf", "A text"), company())


def test_final_record_rejects_company_different_from_confirmed_company():
    state = completed_and_linked_state()
    other = pd.Series({"company_id": "COM-2", "company_name": "다른 업체"})
    with pytest.raises(ValueError, match="일치하지"):
        build_final_inspection_record(get_review_state(state, "A.pdf", "A text"), other)


def test_final_record_blocks_stale_review_after_ai_result_version_changes():
    state: dict[str, object] = {}
    review = start_review(state, "A.pdf", "A text", report(), ai_result_version=1)
    values = dict(review["values"])
    values.update({"inspection_date": date(2026, 8, 27), "inspection_type": "정기", "inspection_result_status": "적정"})
    complete_review(state, "A.pdf", "A text", values)
    confirm_company_link(state, "A.pdf", "A text", company(), confirmed=True)

    with pytest.raises(ValueError, match="AI 분석 결과가 변경"):
        build_final_inspection_record(get_review_state(state, "A.pdf", "A text"), company(), report(), 2)


def test_successful_save_marks_only_its_pdf_and_prevents_repeat_call():
    state = completed_and_linked_state()
    calls: list[dict[str, object]] = []

    def create(record):
        calls.append(record)
        return {**record, "inspection_id": "INS-SAVED"}

    saved, updated = save_final_inspection(state, "A.pdf", "A text", company(), create)
    assert saved["inspection_id"] == "INS-SAVED"
    assert len(calls) == 1
    assert get_final_save_state(updated)["inspection_id"] == "INS-SAVED"
    with pytest.raises(ValueError, match="이미 저장"):
        save_final_inspection(state, "A.pdf", "A text", company(), create)
    assert len(calls) == 1


def test_save_failure_keeps_review_and_company_link_for_retry():
    state = completed_and_linked_state()

    def fail(_record):
        raise RuntimeError("저장 실패")

    with pytest.raises(RuntimeError, match="저장 실패"):
        save_final_inspection(state, "A.pdf", "A text", company(), fail)
    review = get_review_state(state, "A.pdf", "A text")
    assert review["company_link"]["selected_company_id"] == "COM-1"
    assert get_final_save_state(review) is None


def test_pdf_final_save_states_are_independent():
    state = completed_and_linked_state()
    review_b = start_review(state, "B.pdf", "B text", report())
    values_b = dict(review_b["values"])
    values_b.update({"inspection_date": date(2026, 8, 28), "inspection_type": "정기", "inspection_result_status": "적정"})
    complete_review(state, "B.pdf", "B text", values_b)
    confirm_company_link(state, "B.pdf", "B text", company(), confirmed=True)
    save_final_inspection(state, "A.pdf", "A text", company(), lambda record: record)
    assert get_final_save_state(get_review_state(state, "A.pdf", "A text"))["status"] == "saved"
    assert get_final_save_state(get_review_state(state, "B.pdf", "B text")) is None

from __future__ import annotations

import json

import pandas as pd
import pytest

from src.inspection_final_save import save_final_inspection
from src.inspection_review_draft import complete_review, get_review_state, start_review
from src.company_linking import confirm_company_link
from src.report_audit import ReportAuditError, build_report_item_record, get_report_audit_state, record_report_audit
from tests.test_inspection_final_save import company, completed_and_linked_state
from tests.test_inspection_review_draft import report


PDF_TEXT = "A text"


class FakeAuditRepository:
    def __init__(self, fail_item: bool = False):
        self.imports: list[dict[str, object]] = []
        self.items: list[dict[str, object]] = []
        self.fail_item = fail_item

    def get_report_item_by_inspection_id(self, inspection_id: str) -> pd.DataFrame:
        return pd.DataFrame([item for item in self.items if item["inspection_id"] == inspection_id])

    def create_report_import(self, record: dict[str, object]) -> dict[str, object]:
        saved = {**record, "report_id": f"REPORT-{len(self.imports) + 1}"}
        self.imports.append(saved)
        return saved

    def create_report_item(self, record: dict[str, object]) -> dict[str, object]:
        if self.fail_item:
            raise RuntimeError("report item failure")
        saved = {**record, "report_item_id": f"ITEM-{len(self.items) + 1}"}
        self.items.append(saved)
        return saved


def saved_pdf_review_state() -> dict[str, object]:
    state = completed_and_linked_state()
    save_final_inspection(state, "A.pdf", PDF_TEXT, company(), lambda record: {**record, "inspection_id": "INS-1"})
    return state


def test_pdf_save_uses_distinct_pdf_ai_reviewed_data_source():
    state = completed_and_linked_state()
    records: list[dict[str, object]] = []
    save_final_inspection(state, "A.pdf", "A text", company(), lambda record: records.append(record) or record)
    assert records[0]["data_source"] == "pdf_ai_reviewed"


def test_records_import_and_item_after_existing_inspection_save():
    state = saved_pdf_review_state()
    repository = FakeAuditRepository()

    audit = record_report_audit(state, "A.pdf", PDF_TEXT, "pdf-hash", report(), repository)

    assert audit["status"] == "saved"
    assert repository.imports == [{
        "original_filename": "A.pdf", "file_hash": "pdf-hash", "report_status": "uploaded",
        "detected_company_count": 1, "review_status": "pending", "report_id": "REPORT-1",
    }]
    item = repository.items[0]
    assert item["report_id"] == "REPORT-1"
    assert item["company_id"] == "COM-1"
    assert item["inspection_id"] == "INS-1"
    assert item["extracted_company_name"] == "가나다환경"
    assert item["extracted_permit_number"] == "허가 1, 신고 2"
    assert item["extracted_inspection_date"] == "2026-08-27"
    assert item["disposition_reference_status"] == "review_needed"
    assert item["disposition_review_needed"] is True
    assert set(item["extracted_data"]) == {"ai_result", "reviewed_draft"}
    assert json.dumps(item["extracted_data"], ensure_ascii=False)
    assert PDF_TEXT not in json.dumps(item, ensure_ascii=False)
    assert "pdf-hash" not in json.dumps(item, ensure_ascii=False)


def test_planned_actions_absent_never_creates_disposition_and_marks_not_mentioned():
    result = report().__class__(**{**report().__dict__, "planned_actions": report().planned_actions.__class__(None, None)})
    record = build_report_item_record("REPORT-1", "INS-1", "COM-1", result, {"inspection_draft": {}})
    assert record["disposition_reference_status"] == "not_mentioned"
    assert record["disposition_review_needed"] is False
    assert all("disposition_id" not in key for key in record)


def test_duplicate_inspection_audit_is_not_created_twice():
    state = saved_pdf_review_state()
    repository = FakeAuditRepository()
    record_report_audit(state, "A.pdf", PDF_TEXT, "pdf-hash", report(), repository)
    record_report_audit(state, "A.pdf", PDF_TEXT, "pdf-hash", report(), repository)
    assert len(repository.imports) == 1
    assert len(repository.items) == 1


def test_failed_item_record_can_retry_without_second_inspection_or_import():
    state = saved_pdf_review_state()
    repository = FakeAuditRepository(fail_item=True)
    with pytest.raises(ReportAuditError, match="처리이력 기록"):
        record_report_audit(state, "A.pdf", PDF_TEXT, "pdf-hash", report(), repository)
    review = get_review_state(state, "A.pdf", PDF_TEXT)
    assert review["final_save"]["status"] == "saved"
    assert get_report_audit_state(review) == {"status": "failed", "report_id": "REPORT-1"}
    assert len(repository.imports) == 1

    repository.fail_item = False
    record_report_audit(state, "A.pdf", PDF_TEXT, "pdf-hash", report(), repository)
    assert len(repository.imports) == 1
    assert len(repository.items) == 1


def test_pdf_audit_states_do_not_cross_between_files():
    first = saved_pdf_review_state()
    state = first
    review_b = start_review(state, "B.pdf", "B text", report())
    values_b = dict(review_b["values"])
    values_b.update({"inspection_date": "2026-08-28", "inspection_type": "정기", "inspection_result_status": "적정"})
    complete_review(state, "B.pdf", "B text", values_b)
    confirm_company_link(state, "B.pdf", "B text", company(), confirmed=True)
    save_final_inspection(state, "B.pdf", "B text", company(), lambda record: {**record, "inspection_id": "INS-2"})
    repository = FakeAuditRepository()

    record_report_audit(state, "A.pdf", PDF_TEXT, "hash-a", report(), repository)
    assert get_report_audit_state(get_review_state(state, "B.pdf", "B text")) is None

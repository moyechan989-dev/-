from datetime import date
from uuid import UUID

import pandas as pd
import pytest

from src.inspection_service import build_inspection_record, create_inspection_id, find_duplicate_inspections
from src.repositories.local_repository import LocalRepository


def company() -> pd.Series:
    return pd.Series({"company_id": "COM-1", "company_name": "검증 업체"})


def form() -> dict[str, object]:
    return {
        "inspection_date": date(2026, 8, 27),
        "inspection_type": "정기",
        "inspection_result_status": "적정",
        "inspection_media": "폐기물",
        "inspection_purpose": "정기 확인",
        "key_findings": "확인 완료",
        "suspected_violation": "",
        "on_site_action": "",
        "follow_up_action": "",
        "correction_due_date": None,
        "next_check_points": "다음 확인",
    }


def test_new_inspection_record_uses_existing_company_and_db_columns(monkeypatch):
    monkeypatch.setattr("src.inspection_service.uuid4", lambda: UUID("12345678-1234-5678-1234-567812345678"))
    record = build_inspection_record(company(), form())
    assert record["inspection_id"] == "INS-12345678-1234-5678-1234-567812345678"
    assert record["company_id"] == "COM-1"
    assert record["company_name"] == "검증 업체"
    assert record["data_source"] == "manual_entry"
    assert record["review_status"] == "등록완료"
    assert "disposition_id" not in record


@pytest.mark.parametrize("field", ["inspection_date", "inspection_type", "inspection_result_status"])
def test_required_inspection_inputs(field):
    invalid = form()
    invalid[field] = ""
    with pytest.raises(ValueError, match="필수 입력항목"):
        build_inspection_record(company(), invalid)


def test_duplicate_check_uses_company_date_and_type_only():
    inspections = pd.DataFrame([
        {"inspection_id": "INS-1", "company_id": "COM-1", "inspection_date": "2026-08-27", "inspection_type": "정기"},
        {"inspection_id": "INS-2", "company_id": "COM-1", "inspection_date": "2026-08-27", "inspection_type": "수시"},
        {"inspection_id": "INS-3", "company_id": "COM-2", "inspection_date": "2026-08-27", "inspection_type": "정기"},
    ])
    assert find_duplicate_inspections(inspections, "COM-1", date(2026, 8, 27), "정기")["inspection_id"].tolist() == ["INS-1"]


def test_new_ids_are_unique():
    assert create_inspection_id() != create_inspection_id()


def test_local_backend_blocks_inspection_writes(tmp_path):
    with pytest.raises(RuntimeError, match="Supabase 모드"):
        LocalRepository(tmp_path).create_inspection({"inspection_id": "INS-test"})

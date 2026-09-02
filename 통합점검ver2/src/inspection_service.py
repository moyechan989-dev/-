from __future__ import annotations

from datetime import date
from uuid import uuid4

import pandas as pd


def create_inspection_id() -> str:
    """기존 INS 접두어를 유지하면서 전역 충돌 가능성을 사실상 제거합니다."""
    return f"INS-{uuid4()}".upper()


def find_duplicate_inspections(
    inspections: pd.DataFrame,
    company_id: str,
    inspection_date: date | str | None,
    inspection_type: str,
) -> pd.DataFrame:
    if not company_id or not inspection_date or not inspection_type:
        return inspections.iloc[0:0].copy()
    date_text = str(inspection_date)
    return inspections.loc[
        inspections["company_id"].eq(company_id)
        & inspections["inspection_date"].fillna("").astype(str).eq(date_text)
        & inspections["inspection_type"].fillna("").astype(str).eq(inspection_type)
    ].copy()


def build_inspection_record(company: pd.Series, form: dict[str, object]) -> dict[str, object]:
    required = {
        "company_id": company.get("company_id", ""),
        "inspection_date": form.get("inspection_date"),
        "inspection_type": form.get("inspection_type", ""),
        "inspection_result_status": form.get("inspection_result_status", ""),
    }
    missing = [field for field, value in required.items() if value is None or str(value).strip() == ""]
    if missing:
        raise ValueError("업체, 점검일, 점검유형, 점검결과는 필수 입력항목입니다.")

    def optional(name: str) -> str | None:
        value = form.get(name, "")
        return str(value).strip() or None

    inspection_date = str(form["inspection_date"])
    return {
        "inspection_id": create_inspection_id(),
        "company_id": str(company["company_id"]),
        "company_name": str(company["company_name"]),
        "inspection_date": inspection_date,
        "inspection_date_raw": inspection_date,
        "inspection_type": str(form["inspection_type"]).strip(),
        "inspection_media": optional("inspection_media") or "미입력",
        "inspection_result_status": str(form["inspection_result_status"]).strip(),
        "inspection_result_detail": optional("inspection_result_detail"),
        "key_findings": optional("key_findings"),
        "suspected_violation": optional("suspected_violation"),
        "on_site_action": optional("on_site_action"),
        "follow_up_action": optional("follow_up_action"),
        "inspection_purpose": optional("inspection_purpose"),
        "correction_due_date": str(form["correction_due_date"]) if form.get("correction_due_date") else None,
        "next_check_points": optional("next_check_points"),
        "review_status": "등록완료",
        "data_source": "manual_entry",
    }

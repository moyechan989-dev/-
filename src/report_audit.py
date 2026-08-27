from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Protocol

import pandas as pd

from src.ai_report_extractor import AiReportResult
from src.inspection_review_draft import get_review_state, review_session_key


class ReportAuditError(RuntimeError):
    """지도점검 저장 뒤 발생한 출장보고서 처리이력 기록 오류입니다."""


class ReportAuditRepository(Protocol):
    def get_report_item_by_inspection_id(self, inspection_id: str) -> pd.DataFrame: ...
    def create_report_import(self, record: dict[str, object]) -> dict[str, object]: ...
    def create_report_item(self, record: dict[str, object]) -> dict[str, object]: ...


def get_report_audit_state(review: dict[str, Any]) -> dict[str, Any] | None:
    final_save = review.get("final_save")
    if not isinstance(final_save, dict):
        return None
    audit = final_save.get("report_audit")
    return audit if isinstance(audit, dict) else None


def build_report_import_record(filename: str, file_hash: str) -> dict[str, object]:
    """기존 schema의 기본 상태값만 사용하며 PDF 원본은 포함하지 않는다."""
    return {
        "original_filename": filename,
        "file_hash": file_hash,
        "report_status": "uploaded",
        "detected_company_count": 1,
        "review_status": "pending",
    }


def build_report_item_record(
    report_id: str,
    inspection_id: str,
    company_id: str,
    result: AiReportResult,
    review: dict[str, Any],
) -> dict[str, object]:
    values = review.get("values") if isinstance(review.get("values"), dict) else {}
    draft = review.get("inspection_draft") if isinstance(review.get("inspection_draft"), dict) else {}
    has_planned_action = bool(result.planned_actions.administrative_disposition or result.planned_actions.accusation)
    return {
        "report_id": report_id,
        "company_id": company_id,
        "inspection_id": inspection_id,
        "item_order": 1,
        "extracted_company_name": result.company_name_candidate,
        "extracted_permit_number": ", ".join(result.business_info.permit_numbers) or None,
        "extracted_inspection_date": str(draft.get("inspection_date")) if draft.get("inspection_date") else None,
        "extracted_data": {
            "ai_result": _json_safe(asdict(result)),
            "reviewed_draft": {
                "review_values": _json_safe(values),
                "inspection_draft": _json_safe(draft),
            },
        },
        "disposition_reference_status": "review_needed" if has_planned_action else "not_mentioned",
        "disposition_review_needed": has_planned_action,
        "review_status": "pending",
    }


def record_report_audit(
    state: MutableMapping[str, object],
    filename: str,
    text: str,
    file_hash: str,
    result: AiReportResult,
    repository: ReportAuditRepository,
) -> dict[str, Any]:
    """이미 저장된 지도점검에만 처리이력을 연결하고, 실패 시 재시도 상태를 남긴다."""
    review = get_review_state(state, filename, text)
    if not review:
        raise ReportAuditError("출장보고서 검토 상태를 찾을 수 없습니다.")
    final_save = review.get("final_save")
    if not isinstance(final_save, dict) or final_save.get("status") != "saved":
        raise ReportAuditError("지도점검 저장 후에만 출장보고서 처리이력을 기록할 수 있습니다.")
    inspection_id = str(final_save.get("inspection_id", "")).strip()
    company_id = str(final_save.get("company_id", "")).strip()
    if not inspection_id or not company_id:
        raise ReportAuditError("저장된 지도점검 연결정보를 확인할 수 없습니다.")

    previous = get_report_audit_state(review) or {}
    if previous.get("status") == "saved":
        return previous

    report_id = str(previous.get("report_id", "")).strip()
    try:
        existing = repository.get_report_item_by_inspection_id(inspection_id)
        if not existing.empty:
            return _save_audit_state(state, filename, text, {
                "status": "saved",
                "report_id": str(existing.iloc[0].get("report_id", report_id)),
                "report_item_id": str(existing.iloc[0].get("report_item_id", "")),
            })
        if not report_id:
            report_import = repository.create_report_import(build_report_import_record(filename, file_hash))
            report_id = str(report_import.get("report_id", "")).strip()
            if not report_id:
                raise ReportAuditError("출장보고서 처리이력 ID를 확인할 수 없습니다.")
            _save_audit_state(state, filename, text, {"status": "in_progress", "report_id": report_id})
            review = get_review_state(state, filename, text) or review

        report_item = repository.create_report_item(
            build_report_item_record(report_id, inspection_id, company_id, result, review)
        )
    except Exception as error:
        _save_audit_state(state, filename, text, {"status": "failed", "report_id": report_id})
        if isinstance(error, ReportAuditError):
            raise
        raise ReportAuditError("출장보고서 처리이력 기록에 실패했습니다.") from error

    return _save_audit_state(state, filename, text, {
        "status": "saved",
        "report_id": report_id,
        "report_item_id": str(report_item.get("report_item_id", "")),
    })


def _save_audit_state(
    state: MutableMapping[str, object], filename: str, text: str, audit: dict[str, Any],
) -> dict[str, Any]:
    review = get_review_state(state, filename, text)
    if not review:
        raise ReportAuditError("출장보고서 검토 상태를 찾을 수 없습니다.")
    updated = deepcopy(review)
    final_save = dict(updated.get("final_save") or {})
    final_save["report_audit"] = audit
    updated["final_save"] = final_save
    state[review_session_key(filename, text)] = updated
    return audit


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value

from __future__ import annotations

import hashlib
import re
from collections.abc import MutableMapping
from copy import deepcopy
from datetime import date
from typing import Any

from src.ai_report_extractor import AiReportResult
from src.ai_analysis_state import ai_result_fingerprint


INSPECTION_DRAFT_FIELDS = (
    "inspection_date",
    "inspection_type",
    "inspection_result_status",
    "inspection_media",
    "inspection_purpose",
    "key_findings",
    "suspected_violation",
    "on_site_action",
    "follow_up_action",
    "correction_due_date",
    "next_check_points",
)

REQUIRED_DRAFT_FIELDS = {
    "inspection_date": "점검일",
    "inspection_type": "점검유형",
    "inspection_result_status": "점검결과",
}

DRAFT_DISPLAY_LABELS = {
    "inspection_date": "점검일",
    "inspection_type": "점검유형",
    "inspection_result_status": "점검결과",
    "inspection_media": "점검매체",
    "inspection_purpose": "점검목적",
    "key_findings": "주요 점검내용",
    "suspected_violation": "위반·지적사항",
    "on_site_action": "현장조치",
    "follow_up_action": "후속조치",
    "correction_due_date": "시정기한",
    "next_check_points": "다음 점검 참고사항",
}


def review_session_key(filename: str, text: str) -> str:
    digest = hashlib.sha256(f"{filename}\0{text}".encode("utf-8")).hexdigest()[:16]
    return f"inspection_review_{digest}"


def build_initial_review_values(
    result: AiReportResult,
    inspection_types: tuple[str, ...] | list[str] = (),
    result_statuses: tuple[str, ...] | list[str] = (),
    media_values: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    planned_actions = _planned_actions_text(result)
    return {
        "company_name_candidate": result.company_name_candidate or "",
        "inspection_date_raw": result.inspection_date_raw or "",
        "location": result.location or "",
        "inspection_purpose": result.inspection_purpose or "",
        "industry": result.business_info.industry or "",
        "permit_numbers": "\n".join(result.business_info.permit_numbers),
        "field_observations": "\n".join(result.field_observations),
        "confirmed_violation_mentioned": result.confirmed_violation.mentioned,
        "confirmed_violation_content": result.confirmed_violation.content or "",
        "confirmed_violation_legal_basis": "\n".join(result.confirmed_violation.legal_basis),
        "confirmed_violation_evidence_document": result.confirmed_violation.evidence_document or "",
        "planned_administrative_disposition": result.planned_actions.administrative_disposition or "",
        "planned_accusation": result.planned_actions.accusation or "",
        "inspection_date": parse_inspection_date(result.inspection_date_raw),
        "inspection_type": "",
        "inspection_result_status": _suggest_result_status(result, result_statuses),
        "inspection_media": _suggest_inspection_media(result, media_values),
        "key_findings": "\n".join(result.field_observations),
        "suspected_violation": result.confirmed_violation.content if result.confirmed_violation.mentioned is True else "",
        "on_site_action": "",
        "follow_up_action": planned_actions,
        "correction_due_date": None,
        "next_check_points": "",
    }


def build_inspection_draft(values: dict[str, Any]) -> dict[str, Any]:
    return {field: values.get(field) for field in INSPECTION_DRAFT_FIELDS}


def missing_required_draft_fields(values: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        label for field, label in REQUIRED_DRAFT_FIELDS.items()
        if values.get(field) is None or not str(values.get(field)).strip()
    )


def inspection_draft_display_values(draft: dict[str, Any]) -> dict[str, str]:
    """사용자 화면에는 한국어 항목명과 안전한 표시값만 제공한다."""
    displayed: dict[str, str] = {}
    for field, label in DRAFT_DISPLAY_LABELS.items():
        value = draft.get(field)
        if value is None or not str(value).strip():
            displayed[label] = "미입력" if field == "inspection_media" else "-"
        else:
            displayed[label] = str(value)
    return displayed


def parse_inspection_date(raw_value: str | None) -> date | None:
    if not raw_value:
        return None
    match = re.search(r"(?<!\d)(20\d{2})\s*(?:[.\-/]|년)\s*(\d{1,2})\s*(?:[.\-/]|월)\s*(\d{1,2})(?:\s*(?:[.]|일))?", raw_value)
    if not match:
        return None
    try:
        return date(*(int(value) for value in match.groups()))
    except ValueError:
        return None


def get_review_state(state: MutableMapping[str, object], filename: str, text: str) -> dict[str, Any] | None:
    value = state.get(review_session_key(filename, text))
    return value if isinstance(value, dict) else None


def start_review(
    state: MutableMapping[str, object],
    filename: str,
    text: str,
    result: AiReportResult,
    ai_result_version: int | None = None,
    inspection_types: tuple[str, ...] | list[str] = (),
    result_statuses: tuple[str, ...] | list[str] = (),
    media_values: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    current = get_review_state(state, filename, text)
    if current and review_matches_ai_result(current, result, ai_result_version):
        return current
    review = {
        "status": "in_progress",
        "values": build_initial_review_values(result, inspection_types, result_statuses, media_values),
        "inspection_draft": None,
        "ai_result_fingerprint": ai_result_fingerprint(result),
        "ai_result_version": ai_result_version,
    }
    state[review_session_key(filename, text)] = review
    return review


def save_review_values(state: MutableMapping[str, object], filename: str, text: str, values: dict[str, Any]) -> dict[str, Any]:
    current = get_review_state(state, filename, text)
    if not current:
        raise ValueError("먼저 검토를 시작해 주세요.")
    updated = {
        "status": "in_progress",
        "values": deepcopy(values),
        "inspection_draft": None,
        "ai_result_fingerprint": current.get("ai_result_fingerprint"),
        "ai_result_version": current.get("ai_result_version"),
    }
    state[review_session_key(filename, text)] = updated
    return updated


def complete_review(state: MutableMapping[str, object], filename: str, text: str, values: dict[str, Any]) -> dict[str, Any]:
    missing = missing_required_draft_fields(values)
    if missing:
        raise ValueError(f"다음 필수항목을 확인해주세요: {', '.join(missing)}")
    current = get_review_state(state, filename, text)
    if not current:
        raise ValueError("먼저 검토를 시작해 주세요.")
    completed = {
        "status": "completed",
        "values": deepcopy(values),
        "inspection_draft": build_inspection_draft(values),
        "ai_result_fingerprint": current.get("ai_result_fingerprint"),
        "ai_result_version": current.get("ai_result_version"),
    }
    state[review_session_key(filename, text)] = completed
    return completed


def review_matches_ai_result(review: dict[str, Any], result: AiReportResult, ai_result_version: int | None = None) -> bool:
    if review.get("ai_result_fingerprint") != ai_result_fingerprint(result):
        return False
    expected_version = review.get("ai_result_version")
    return ai_result_version is None or expected_version is None or expected_version == ai_result_version


def invalidate_review_for_new_ai_result(
    state: MutableMapping[str, object], filename: str, text: str, result: AiReportResult, ai_result_version: int | None,
) -> str:
    review = get_review_state(state, filename, text)
    if not review or review_matches_ai_result(review, result, ai_result_version):
        return "unchanged"
    final_save = review.get("final_save")
    if isinstance(final_save, dict) and final_save.get("status") == "saved":
        retained = deepcopy(review)
        retained["ai_result_changed_after_save"] = True
        state[review_session_key(filename, text)] = retained
        return "saved_retained"
    state.pop(review_session_key(filename, text), None)
    return "invalidated"


def _suggest_result_status(result: AiReportResult, result_statuses: tuple[str, ...] | list[str]) -> str:
    return "위반" if result.confirmed_violation.mentioned is True and "위반" in result_statuses else ""


def _suggest_inspection_media(result: AiReportResult, media_values: tuple[str, ...] | list[str]) -> str:
    source = " ".join((result.report_title or "", result.inspection_purpose or "", *result.field_observations))
    return "대기" if "대기" in source and "대기" in media_values else ""


def _planned_actions_text(result: AiReportResult) -> str:
    parts = []
    if result.planned_actions.administrative_disposition:
        parts.append(f"보고서상 향후 계획 - 행정처분: {result.planned_actions.administrative_disposition}")
    if result.planned_actions.accusation:
        parts.append(f"보고서상 향후 계획 - 고발: {result.planned_actions.accusation}")
    return "\n".join(parts)

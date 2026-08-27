from __future__ import annotations

from collections.abc import Callable, MutableMapping
from copy import deepcopy
from typing import Any

import pandas as pd

from src.inspection_review_draft import get_review_state, review_matches_ai_result, review_session_key
from src.ai_report_extractor import AiReportResult
from src.inspection_service import build_inspection_record


def build_final_inspection_record(
    review: dict[str, Any],
    company: pd.Series,
    current_ai_result: AiReportResult | None = None,
    current_ai_result_version: int | None = None,
) -> dict[str, object]:
    """검토자가 확정한 초안과 선택한 실제 업체만 저장 레코드로 만든다."""
    if review.get("status") != "completed":
        raise ValueError("검토 완료된 지도점검 등록 초안만 저장할 수 있습니다.")
    if current_ai_result and not review_matches_ai_result(review, current_ai_result, current_ai_result_version):
        raise ValueError("AI 분석 결과가 변경되었습니다. 검토 내용을 다시 확인해주세요.")
    link = review.get("company_link")
    if not isinstance(link, dict):
        raise ValueError("저장 전에 담당자가 업체 연결을 확정해 주세요.")
    company_id = str(company.get("company_id", "")).strip()
    if not company_id or company_id != str(link.get("selected_company_id", "")).strip():
        raise ValueError("확정된 업체 정보와 선택한 업체 정보가 일치하지 않습니다.")
    draft = review.get("inspection_draft")
    if not isinstance(draft, dict):
        raise ValueError("지도점검 등록 초안을 찾을 수 없습니다.")
    return build_inspection_record(company, draft)


def get_final_save_state(review: dict[str, Any]) -> dict[str, Any] | None:
    value = review.get("final_save")
    return value if isinstance(value, dict) else None


def save_final_inspection(
    state: MutableMapping[str, object],
    filename: str,
    text: str,
    company: pd.Series,
    create_inspection: Callable[[dict[str, object]], dict[str, object]],
    current_ai_result: AiReportResult | None = None,
    current_ai_result_version: int | None = None,
) -> tuple[dict[str, object], dict[str, Any]]:
    """명시적인 저장 요청에서만 저장하고, 성공한 경우에만 PDF별 상태를 갱신한다."""
    review = get_review_state(state, filename, text)
    if not review:
        raise ValueError("지도점검 등록 초안을 찾을 수 없습니다.")
    previous = get_final_save_state(review)
    if previous and previous.get("status") == "saved":
        raise ValueError("이 PDF의 지도점검 초안은 이미 저장되었습니다.")

    record = build_final_inspection_record(review, company, current_ai_result, current_ai_result_version)
    record["data_source"] = "pdf_ai_reviewed"
    saved = create_inspection(record)

    updated = deepcopy(review)
    updated["final_save"] = {
        "status": "saved",
        "inspection_id": str(saved.get("inspection_id", record["inspection_id"])),
        "company_id": str(saved.get("company_id", record["company_id"])),
        "company_name": str(saved.get("company_name", record["company_name"])),
        "inspection_date": str(saved.get("inspection_date", record["inspection_date"])),
    }
    state[review_session_key(filename, text)] = updated
    return saved, updated

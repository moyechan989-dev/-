from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.search_service import normalize_text


KNOWLEDGE_FILE = Path(__file__).resolve().parents[1] / "data" / "reference" / "inspection_knowledge_v1.json"
CASE_COLUMNS = (
    "violation_content", "legal_basis", "administrative_disposition", "accusation", "penalty", "disposition_date",
)
VERIFICATION_STATUSES = ("미검증", "공식법령 확인", "내부업무 검토완료", "개정확인 필요")


def load_inspection_knowledge(path: Path = KNOWLEDGE_FILE) -> list[dict[str, Any]]:
    """공개 참고용 지식항목만 읽으며 업무 데이터는 변경하지 않는다."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("지도점검 지식자료 형식이 올바르지 않습니다.")
    return [_normalize_item(item) for item in payload if isinstance(item, dict)]


def search_inspection_knowledge(
    items: list[dict[str, Any]], keyword: str = "", category: str = "", verification_status: str = "",
) -> list[dict[str, Any]]:
    query = normalize_text(keyword)
    selected = []
    for item in items:
        if category and item.get("category") != category:
            continue
        if verification_status and item.get("verification_status") != verification_status:
            continue
        searchable = [
            item.get("manual_id", ""), item.get("category", ""), item.get("title", ""), item.get("verification_status", ""),
            *item.get("keywords", []),
            *item.get("trigger_conditions", []),
            *item.get("inspector_questions", []),
        ]
        for reference in item.get("legal_refs", []):
            searchable.extend(reference.get(key, "") for key in ("law_name", "article", "paragraph", "role", "verification_status"))
        if query and not any(query in normalize_text(value) for value in searchable):
            continue
        selected.append(item)
    return sorted(selected, key=lambda item: str(item.get("manual_id", "")))


def get_inspection_knowledge_item(items: list[dict[str, Any]], manual_id: str) -> dict[str, Any] | None:
    return next((item for item in items if item.get("manual_id") == manual_id), None)


def find_similar_dispositions(
    dispositions: pd.DataFrame, item: dict[str, Any], limit: int = 20,
) -> pd.DataFrame:
    """지식항목의 키워드로만 기존 처분 사례를 찾고 자동 판단은 하지 않는다."""
    keywords = [normalize_text(keyword) for keyword in item.get("keywords", []) if normalize_text(keyword)]
    if not keywords:
        return dispositions.iloc[0:0].copy()
    matches = pd.Series(False, index=dispositions.index)
    for column in ("violation_content", "violation_category", "legal_basis"):
        if column not in dispositions:
            continue
        values = dispositions[column].fillna("").astype(str).map(normalize_text)
        for keyword in keywords:
            matches |= values.str.contains(keyword, regex=False)
    result = dispositions.loc[matches].copy()
    if result.empty:
        return result
    result["_sort_date"] = pd.to_datetime(result["disposition_date"], errors="coerce")
    return result.sort_values("_sort_date", ascending=False, na_position="last", kind="stable").drop(columns="_sort_date").head(limit)


def public_case_rows(dispositions: pd.DataFrame) -> list[dict[str, str]]:
    """업체명·대표자·주소·식별자는 노출하지 않는 유사사례 표시용 행이다."""
    rows = []
    for _, source in dispositions.iterrows():
        rows.append({column: _display_value(source.get(column)) for column in CASE_COLUMNS})
    return rows


def _display_value(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return str(value).strip() or "-"


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    legacy_status = str(item.get("verification_status", "")).strip()
    normalized["verification_status"] = _normalize_status(legacy_status)
    normalized["legal_refs"] = [_normalize_legal_ref(reference) for reference in item.get("legal_refs", [])]
    normalized["trigger_conditions"] = _text_values(item.get("trigger_conditions", []))
    normalized["inspector_questions"] = _text_values(item.get("inspector_questions", []))
    normalized["common_mistakes"] = _text_values(item.get("common_mistakes", []))
    normalized["effective_date"] = "" if legacy_status == "담당자 검토 필요" else str(item.get("effective_date", "")).strip()
    normalized["reviewed_at"] = "" if legacy_status == "담당자 검토 필요" else str(item.get("reviewed_at", "")).strip()
    return normalized


def _text_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]

def _normalize_legal_ref(reference: object) -> dict[str, str]:
    if isinstance(reference, str):
        source: dict[str, object] = {"law_name": reference}
    elif isinstance(reference, dict):
        source = reference
    else:
        source = {}
    article, paragraph = _split_article(str(source.get("article", "")).strip(), str(source.get("paragraph", "")).strip())
    law_name = str(source.get("law_name", "")).strip()
    return {
        "law_name": law_name,
        "article": article,
        "paragraph": paragraph,
        "role": str(source.get("role", "")).strip(),
        "summary": str(source.get("summary", source.get("check_point", ""))).strip(),
        "source_url": str(source.get("source_url", "")).strip(),
        "effective_date": str(source.get("effective_date", "")).strip(),
        "source_checked_at": str(source.get("source_checked_at", "")).strip(),
        "verification_status": _normalize_status(str(source.get("verification_status", "")).strip()),
    }


def _split_article(article: str, paragraph: str) -> tuple[str, str]:
    if paragraph or "제" not in article or "항" not in article:
        return article, paragraph
    before_paragraph, marker, after_paragraph = article.partition("제")
    second_marker = after_paragraph.find("제")
    if not marker or second_marker < 0:
        return article, paragraph
    candidate_article = f"제{after_paragraph[:second_marker]}"
    candidate_paragraph = f"제{after_paragraph[second_marker + 1:]}"
    return (candidate_article, candidate_paragraph) if candidate_paragraph.endswith("항") else (article, paragraph)


def _normalize_status(value: str) -> str:
    return value if value in VERIFICATION_STATUSES else "미검증"

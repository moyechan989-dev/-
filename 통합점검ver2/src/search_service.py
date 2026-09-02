from __future__ import annotations

import re

import pandas as pd


SEARCH_COLUMNS = [
    "company_name",
    "company_name_normalized",
    "permit_number",
    "address",
    "address_normalized",
]
FILTER_COLUMNS = ["district", "industry", "entity_type", "is_2026_target", "planned_inspection_type"]


def normalize_text(value: object) -> str:
    """대소문자와 모든 공백을 무시하는 부분 일치용 정규화."""
    return re.sub(r"\s+", "", str(value or "")).casefold()


def option_values(companies: pd.DataFrame, column: str) -> list[str]:
    values = companies[column].fillna("").astype(str).str.strip()
    return sorted(value for value in values.unique().tolist() if value)


def search_companies(
    companies: pd.DataFrame,
    aliases: pd.DataFrame,
    query: str = "",
    filters: dict[str, str] | None = None,
) -> pd.DataFrame:
    """정확한 문자열 부분 일치만 수행하며 유사도 기반 병합은 하지 않는다."""
    result = companies.copy()
    normalized_query = normalize_text(query)
    if normalized_query:
        direct_match = pd.Series(False, index=result.index)
        for column in SEARCH_COLUMNS:
            if column in result.columns:
                direct_match |= result[column].map(normalize_text).str.contains(normalized_query, regex=False)
        alias_ids = set(
            aliases.loc[
                aliases["alias_value"].map(normalize_text).str.contains(normalized_query, regex=False)
                | aliases["normalized_value"].map(normalize_text).str.contains(normalized_query, regex=False),
                "company_id",
            ]
        )
        result = result.loc[direct_match | result["company_id"].isin(alias_ids)]
    for column, selected in (filters or {}).items():
        if not selected or column not in FILTER_COLUMNS:
            continue
        values = result[column].fillna("").astype(str).str.strip()
        if selected == "미등록":
            result = result.loc[values.eq("")]
        else:
            result = result.loc[values.eq(selected)]
    return result.sort_values(["company_name", "company_id"], kind="stable").reset_index(drop=True)

from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy

import pandas as pd

from src.inspection_review_draft import get_review_state, review_session_key
from src.search_service import normalize_text, search_companies


def recommend_company_candidates(
    companies: pd.DataFrame,
    aliases: pd.DataFrame,
    company_name_candidate: str,
    location: str = "",
    industry: str = "",
    limit: int = 5,
) -> pd.DataFrame:
    """기존 검색 결과만 정렬하며, 어떤 후보도 자동 선택하지 않습니다."""
    if not normalize_text(company_name_candidate):
        return companies.iloc[0:0].copy()
    candidates = search_companies(companies, aliases, company_name_candidate)
    if candidates.empty:
        return candidates
    query = normalize_text(company_name_candidate)
    alias_ids = set(aliases.loc[
        aliases["alias_value"].map(normalize_text).eq(query)
        | aliases["normalized_value"].map(normalize_text).eq(query),
        "company_id",
    ])
    ranked = candidates.copy()
    ranked["_name_rank"] = ranked.apply(
        lambda row: 0 if normalize_text(row.get("company_name")) == query or normalize_text(row.get("company_name_normalized")) == query
        else 1 if row["company_id"] in alias_ids else 2,
        axis=1,
    )
    ranked["_location_match"] = ranked.apply(lambda row: _location_matches(location, row), axis=1)
    ranked["_industry_match"] = ranked["industry"].map(normalize_text).eq(normalize_text(industry)) if normalize_text(industry) else False
    ranked["candidate_reason"] = ranked.apply(
        lambda row: _candidate_reason(row["_name_rank"], row["_location_match"], row["_industry_match"]), axis=1
    )
    return ranked.sort_values(
        ["_name_rank", "_location_match", "_industry_match", "company_name", "company_id"],
        ascending=[True, False, False, True, True],
        kind="stable",
    ).head(limit).drop(columns=["_name_rank", "_location_match", "_industry_match"]).reset_index(drop=True)


def company_information_may_differ(report_name: str, report_location: str, company: pd.Series) -> bool:
    name = normalize_text(report_name)
    company_name = normalize_text(company.get("company_name"))
    name_differs = bool(name and company_name and name not in company_name and company_name not in name)
    location_differs = bool(normalize_text(report_location) and not _location_matches(report_location, company))
    return name_differs or location_differs


def confirm_company_link(
    state: MutableMapping[str, object],
    filename: str,
    text: str,
    company: pd.Series,
    confirmed: bool,
) -> dict[str, object]:
    if not confirmed:
        raise ValueError("업체 연결을 확정하려면 확인을 선택해 주세요.")
    review = get_review_state(state, filename, text)
    if not review or review.get("status") != "completed":
        raise ValueError("검토 완료된 지도점검 등록 초안에서만 업체를 연결할 수 있습니다.")
    company_id = str(company.get("company_id", "")).strip()
    if not company_id:
        raise ValueError("선택한 업체의 company_id가 없습니다.")
    updated = deepcopy(review)
    updated["company_link"] = {
        "selected_company_id": company_id,
        "selected_company_name": str(company.get("company_name", "")).strip(),
    }
    state[review_session_key(filename, text)] = updated
    return updated


def _location_matches(location: str, company: pd.Series) -> bool:
    source = normalize_text(location)
    if not source:
        return False
    address = normalize_text(company.get("address"))
    district = normalize_text(company.get("district"))
    return bool((address and (address in source or source in address)) or (district and district in source))


def _candidate_reason(name_rank: int, location_match: bool, industry_match: bool) -> str:
    name_reason = "업체명 정확 일치" if name_rank == 0 else "업체 별칭 정확 일치" if name_rank == 1 else "기존 검색 결과"
    context = []
    if location_match:
        context.append("장소/지역 참고 일치")
    if industry_match:
        context.append("업종 참고 일치")
    return " · ".join([name_reason, *context])

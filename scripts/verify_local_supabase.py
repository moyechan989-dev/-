"""로컬 CSV와 원격 Supabase 조회 결과를 읽기 전용으로 비교합니다."""

from __future__ import annotations

from collections.abc import Iterable
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.company_service import build_summary, get_company_history
from src.repositories.local_repository import LocalRepository
from src.repositories.supabase_repository import SupabaseRepository
from src.search_service import FILTER_COLUMNS, search_companies


EXPECTED_COUNTS = {"companies": 545, "aliases": 2371, "inspections": 616, "dispositions": 366}
COMPANY_FIELDS = [
    "company_id", "permit_number", "company_name", "company_name_normalized", "address",
    "address_normalized", "district", "industry", "entity_type", "is_2026_target",
    "planned_inspection_type", "manager_alias", "air_scale", "water_scale", "air_grade",
    "water_grade", "target_media_waste", "source_tags", "source_record_count",
    "major_complaint_note", "manual_inspection_note",
]


def normalized_value(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise RuntimeError(message)


def latest_date(frame: pd.DataFrame, column: str) -> str:
    if frame.empty:
        return "-"
    dates = pd.to_datetime(frame[column], errors="coerce")
    return dates.max().strftime("%Y-%m-%d") if dates.notna().any() else "-"


def validate_company(repository: SupabaseRepository, local_data: dict[str, pd.DataFrame], company_id: str) -> None:
    local_company = local_data["companies"].loc[local_data["companies"]["company_id"].eq(company_id)]
    remote_company = repository.get_company(company_id)
    assert_equal(len(remote_company), 1, "원격 업체 기본정보 조회 건수가 일치하지 않습니다.")
    for field in COMPANY_FIELDS:
        assert_equal(
            normalized_value(remote_company.iloc[0].get(field, "")),
            normalized_value(local_company.iloc[0].get(field, "")),
            "원격 업체 기본정보가 로컬 CSV와 일치하지 않습니다.",
        )

    local_inspections, local_dispositions = get_company_history(
        company_id, local_data["inspections"], local_data["dispositions"]
    )
    remote_inspections = repository.get_inspections(company_id)
    remote_dispositions = repository.get_dispositions(company_id)
    remote_inspections, remote_dispositions = get_company_history(
        company_id, remote_inspections, remote_dispositions
    )
    assert_equal(len(remote_inspections), len(local_inspections), "원격 지도점검 건수가 로컬 CSV와 일치하지 않습니다.")
    assert_equal(len(remote_dispositions), len(local_dispositions), "원격 행정처분 건수가 로컬 CSV와 일치하지 않습니다.")
    assert_equal(
        remote_inspections["inspection_id"].tolist(), local_inspections["inspection_id"].tolist(),
        "원격 지도점검 ID가 로컬 CSV와 일치하지 않습니다.",
    )
    assert_equal(
        remote_dispositions["disposition_id"].tolist(), local_dispositions["disposition_id"].tolist(),
        "원격 행정처분 ID가 로컬 CSV와 일치하지 않습니다.",
    )
    assert_equal(latest_date(remote_inspections, "inspection_date"), latest_date(local_inspections, "inspection_date"), "최근 지도점검일이 일치하지 않습니다.")
    assert_equal(latest_date(remote_dispositions, "disposition_date"), latest_date(local_dispositions, "disposition_date"), "최근 행정처분일이 일치하지 않습니다.")
    assert_equal(build_summary(remote_inspections, remote_dispositions), build_summary(local_inspections, local_dispositions), "업체 이력 요약이 일치하지 않습니다.")


def first_id(ids: Iterable[str], excluded: set[str]) -> str:
    for company_id in ids:
        if company_id not in excluded:
            return company_id
    raise RuntimeError("비교할 대표 업체를 찾을 수 없습니다.")


def main() -> None:
    url = os.getenv("SUPABASE_URL", "")
    secret_key = os.getenv("SUPABASE_SECRET_KEY", "")
    if not url or not secret_key:
        raise RuntimeError("Supabase 조회에는 URL과 서버 전용 Secret Key가 필요합니다.")

    local = LocalRepository()
    remote = SupabaseRepository(url, secret_key)
    local_data = local.load_all()
    remote_counts = remote.get_counts()
    assert_equal(local.get_counts(), EXPECTED_COUNTS, "로컬 CSV 건수가 기대값과 일치하지 않습니다.")
    assert_equal(remote_counts, EXPECTED_COUNTS, "원격 Supabase 건수가 기대값과 일치하지 않습니다.")

    remote_companies = remote.list_companies()
    remote_aliases = remote.list_aliases()
    for field in ("district", "industry", "is_2026_target"):
        local_counts = local_data["companies"][field].fillna("").value_counts().sort_index().to_dict()
        remote_field_counts = remote_companies[field].fillna("").value_counts().sort_index().to_dict()
        assert_equal(remote_field_counts, local_counts, "업체 분류별 건수가 로컬 CSV와 일치하지 않습니다.")

    inspection_ids = set(local_data["inspections"]["company_id"])
    disposition_ids = set(local_data["dispositions"]["company_id"])
    company_ids = local_data["companies"]["company_id"].tolist()
    selected: list[str] = []
    selected.append(first_id(inspection_ids & disposition_ids, set(selected)))
    selected.append(first_id(inspection_ids - disposition_ids, set(selected)))
    selected.append(first_id(disposition_ids - inspection_ids, set(selected)))
    selected.append(first_id(set(company_ids) - inspection_ids - disposition_ids, set(selected)))
    alias_row = local_data["aliases"].loc[local_data["aliases"]["alias_value"].fillna("").ne("")].iloc[0]
    alias_query = str(alias_row["alias_value"])
    local_alias_results = search_companies(local_data["companies"], local_data["aliases"], alias_query)
    remote_alias_results = search_companies(remote_companies, remote_aliases, alias_query)
    assert_equal(remote_alias_results["company_id"].tolist(), local_alias_results["company_id"].tolist(), "별칭 검색 결과가 로컬 CSV와 일치하지 않습니다.")
    selected.append(first_id([str(alias_row["company_id"]), *company_ids], set(selected)))

    for company_id in selected:
        validate_company(remote, local_data, company_id)

    filter_source = local_data["companies"].dropna(subset=FILTER_COLUMNS)
    filter_source = filter_source.loc[(filter_source[FILTER_COLUMNS].fillna("") != "").all(axis=1)]
    if filter_source.empty:
        raise RuntimeError("필터 조합을 비교할 업체를 찾을 수 없습니다.")
    filters = {field: str(filter_source.iloc[0][field]) for field in FILTER_COLUMNS}
    assert_equal(
        search_companies(remote_companies, remote_aliases, filters=filters)["company_id"].tolist(),
        search_companies(local_data["companies"], local_data["aliases"], filters=filters)["company_id"].tolist(),
        "필터 조합 검색 결과가 로컬 CSV와 일치하지 않습니다.",
    )
    print("원격 Supabase 읽기 전용 비교 통과")
    print("전체 건수: 업체 545, 업체별칭 2371, 지도점검 616, 행정처분 366")
    print("대표 업체 5개, 별칭 검색, 필터 조합 비교 통과")


if __name__ == "__main__":
    main()

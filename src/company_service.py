from __future__ import annotations

import pandas as pd


def _latest_date(frame: pd.DataFrame, column: str) -> str:
    if frame.empty:
        return "-"
    parsed = pd.to_datetime(frame[column], errors="coerce")
    if parsed.notna().any():
        return parsed.max().strftime("%Y-%m-%d")
    return "-"


def get_company_history(
    company_id: str,
    inspections: pd.DataFrame,
    dispositions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    company_inspections = inspections.loc[inspections["company_id"].eq(company_id)].copy()
    company_dispositions = dispositions.loc[dispositions["company_id"].eq(company_id)].copy()
    company_inspections["_sort_date"] = pd.to_datetime(company_inspections["inspection_date"], errors="coerce")
    company_dispositions["_sort_date"] = pd.to_datetime(company_dispositions["disposition_date"], errors="coerce")
    return (
        company_inspections.sort_values("_sort_date", ascending=False, na_position="last", kind="stable").drop(columns="_sort_date"),
        company_dispositions.sort_values("_sort_date", ascending=False, na_position="last", kind="stable").drop(columns="_sort_date"),
    )


def build_summary(inspections: pd.DataFrame, dispositions: pd.DataFrame) -> dict[str, str]:
    latest_inspection = _latest_date(inspections, "inspection_date")
    latest_disposition = _latest_date(dispositions, "disposition_date")
    latest_result = "-"
    if latest_inspection != "-":
        latest_rows = inspections.loc[inspections["inspection_date"].eq(latest_inspection)]
        if not latest_rows.empty:
            latest_result = latest_rows.iloc[0].get("inspection_result_status", "") or "-"
    latest_content = "-"
    if latest_disposition != "-":
        latest_rows = dispositions.loc[dispositions["disposition_date"].eq(latest_disposition)]
        if not latest_rows.empty:
            latest_content = latest_rows.iloc[0].get("administrative_disposition", "") or "-"
    return {
        "최근 지도점검일": latest_inspection,
        "최근 지도점검 결과": latest_result,
        "전체 지도점검 건수": str(len(inspections)),
        "최근 행정처분일": latest_disposition,
        "최근 행정처분 내용": latest_content,
        "전체 행정처분 건수": str(len(dispositions)),
    }

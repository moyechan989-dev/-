import pandas as pd

from src.company_service import build_summary, get_company_history


def test_company_history_links_only_by_company_id_and_sorts_dates():
    inspections = pd.DataFrame([
        {"company_id": "COM-1", "inspection_date": "2025-01-01", "inspection_result_status": "적정"},
        {"company_id": "COM-1", "inspection_date": "2026-02-01", "inspection_result_status": "위반"},
        {"company_id": "COM-2", "inspection_date": "2026-03-01", "inspection_result_status": "적정"},
    ])
    dispositions = pd.DataFrame([
        {"company_id": "COM-1", "disposition_date": "2026-01-03", "administrative_disposition": "경고"},
        {"company_id": "COM-2", "disposition_date": "2026-04-03", "administrative_disposition": "과태료"},
    ])
    company_inspections, company_dispositions = get_company_history("COM-1", inspections, dispositions)
    assert company_inspections["inspection_date"].tolist() == ["2026-02-01", "2025-01-01"]
    assert company_dispositions["company_id"].tolist() == ["COM-1"]
    summary = build_summary(company_inspections, company_dispositions)
    assert summary["최근 지도점검일"] == "2026-02-01"
    assert summary["최근 행정처분 내용"] == "경고"


def test_summary_uses_dash_when_history_is_empty():
    inspections = pd.DataFrame(columns=["company_id", "inspection_date", "inspection_result_status"])
    dispositions = pd.DataFrame(columns=["company_id", "disposition_date", "administrative_disposition"])
    summary = build_summary(inspections, dispositions)
    assert summary["최근 지도점검일"] == "-"
    assert summary["전체 행정처분 건수"] == "0"


def test_company_history_does_not_include_same_named_different_company():
    inspections = pd.DataFrame([
        {"company_id": "COM-1", "inspection_date": "2026-01-01", "inspection_result_status": "적정"},
        {"company_id": "COM-2", "inspection_date": "2026-02-01", "inspection_result_status": "위반"},
    ])
    dispositions = pd.DataFrame(columns=["company_id", "disposition_date", "administrative_disposition"])
    selected, _ = get_company_history("COM-1", inspections, dispositions)
    assert selected["company_id"].tolist() == ["COM-1"]

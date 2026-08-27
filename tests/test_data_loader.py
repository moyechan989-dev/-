import pandas as pd
import pytest

from src.data_loader import _read_csv


def test_read_csv_reads_utf8_sig_and_keeps_blank_text(tmp_path):
    path = tmp_path / "01_companies.csv"
    path.write_text("company_id,company_name,permit_number,address\nCOM-1,업체,PER-1,\n", encoding="utf-8-sig")
    frame = _read_csv("01_companies.csv", tmp_path)
    assert frame.loc[0, "address"] == ""


def test_read_csv_reports_missing_required_column(tmp_path):
    (tmp_path / "01_companies.csv").write_text("company_id,company_name\nCOM-1,업체\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="필수 열"):
        _read_csv("01_companies.csv", tmp_path)

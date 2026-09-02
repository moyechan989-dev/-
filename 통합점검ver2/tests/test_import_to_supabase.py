import csv
import os
from pathlib import Path

import pytest

from scripts.import_to_supabase import (
    SPECS,
    SupabaseRestWriter,
    apply_import,
    build_import_plan,
    build_remote_preflight,
    build_table_plan,
    load_env_file,
    main,
)


def write_csv(path: Path, headers: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def valid_row(spec, row_id: str, company_id: str = "COM-1") -> dict[str, str]:
    row = {column: "값" for column in spec.columns}
    for column in spec.date_columns:
        row[column] = "2026-01-01"
    for column in spec.integer_columns:
        row[column] = "1"
    for column in spec.number_columns:
        row[column] = "100"
    row[spec.unique_key[0]] = row_id
    if "company_id" in row:
        row["company_id"] = company_id
    if "is_2026_target" in row:
        row["is_2026_target"] = "Y"
    if "is_primary" in row:
        row["is_primary"] = "N"
    return row


def test_csv_to_db_mapping_and_import_order(tmp_path):
    ids = {"companies": "COM-1", "company_aliases": "COM-1", "inspections": "INS-1", "dispositions": "DSP-1"}
    for spec in SPECS:
        write_csv(tmp_path / spec.filename, spec.columns, [valid_row(spec, ids[spec.table])])
    plans = build_import_plan(tmp_path)
    assert [plan.table for plan in plans] == ["companies", "company_aliases", "inspections", "dispositions"]
    assert all(len(plan.records) == 1 for plan in plans)


def test_required_value_duplicate_orphan_and_bad_date_are_excluded():
    inspection = next(spec for spec in SPECS if spec.table == "inspections")
    good = valid_row(inspection, "INS-1")
    missing = valid_row(inspection, "INS-2")
    missing["company_id"] = ""
    duplicate = good.copy()
    orphan = valid_row(inspection, "INS-3", "COM-X")
    bad_date = valid_row(inspection, "INS-4")
    bad_date["inspection_date"] = "날짜오류"
    plan = build_table_plan(inspection, [good, missing, duplicate, orphan, bad_date], {"COM-1"})
    assert len(plan.records) == 1
    assert (plan.missing_required, plan.duplicate_ids, plan.orphan_company_ids, plan.date_failures) == (1, 1, 1, 1)


def test_apply_uses_ignore_duplicate_writer_only_after_clean_dry_run():
    company = next(spec for spec in SPECS if spec.table == "companies")
    plan = build_table_plan(company, [valid_row(company, "COM-1")], {"COM-1"})

    class Writer:
        calls = []

        def insert_ignore_duplicates(self, table, rows, on_conflict):
            self.calls.append((table, len(rows), on_conflict))

    writer = Writer()
    apply_import([plan], writer)
    assert writer.calls == [("companies", 1, ("company_id",))]


def test_apply_stops_when_validation_has_exclusions():
    company = next(spec for spec in SPECS if spec.table == "companies")
    bad = valid_row(company, "COM-1")
    bad["company_name"] = ""
    plan = build_table_plan(company, [bad], {"COM-1"})
    with pytest.raises(ValueError, match="적용을 중단"):
        apply_import([plan], object())


def test_default_main_is_dry_run_without_supabase_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    assert main([]) == 0


def test_load_env_file_reads_values_without_overwriting_shell_environment(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# import credentials\nSUPABASE_URL=https://example.supabase.co\nSUPABASE_SECRET_KEY='test-secret'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "shell-secret")

    load_env_file(env_file)

    assert os.environ["SUPABASE_URL"] == "https://example.supabase.co"
    assert os.environ["SUPABASE_SECRET_KEY"] == "shell-secret"


def test_preflight_skips_existing_records_without_modifying_plan():
    company = next(spec for spec in SPECS if spec.table == "companies")
    plan = build_table_plan(
        company,
        [valid_row(company, "COM-1", "COM-1"), valid_row(company, "COM-2", "COM-2")],
        {"COM-1", "COM-2"},
    )

    class ReadOnlyWriter:
        def fetch_rows(self, table, columns):
            assert (table, columns) == ("companies", ("company_id",))
            return [{"company_id": "COM-1"}]

    result = build_remote_preflight([plan], ReadOnlyWriter())[0]
    assert (result.csv_count, result.remote_count, result.planned_count, result.skip_existing, result.error_count) == (2, 1, 1, 1, 0)
    assert result.records[0]["company_id"] == "COM-2"


def test_remote_requests_send_secret_only_as_apikey_header():
    class Response:
        status = 200

        def read(self):
            return b"[]"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    def opener(request):
        assert request.get_header("Apikey") == "test-secret"
        assert request.get_header("Authorization") is None
        return Response()

    writer = SupabaseRestWriter("https://example.supabase.co", "test-secret", opener=opener)
    assert writer.fetch_rows("companies", ("company_id",)) == []

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_unique_backing_index_names_are_not_created_in_indexes_sql():
    constraints = (ROOT / "supabase" / "constraints.sql").read_text(encoding="utf-8")
    indexes = (ROOT / "supabase" / "indexes.sql").read_text(encoding="utf-8")
    unique_names = {"company_aliases_natural_key", "report_items_order_unique"}
    index_names = set(re.findall(r"create index if not exists\s+(\w+)", indexes, flags=re.I))
    assert unique_names.isdisjoint(index_names)
    assert "unique using index company_aliases_natural_key" in constraints
    assert "unique using index report_items_order_unique" in constraints


def test_schema_owns_base_foreign_keys_and_constraints_are_safe_for_existing_schema():
    schema = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8")
    constraints = (ROOT / "supabase" / "constraints.sql").read_text(encoding="utf-8")
    foreign_keys = {
        "company_aliases_company_fk", "inspections_company_fk", "dispositions_company_fk",
        "company_notes_company_fk", "company_notes_inspection_fk", "report_items_report_fk", "report_items_company_fk",
    }
    assert all(f"constraint {name}" in schema for name in foreign_keys)
    assert all(f"conname = '{name}'" in constraints for name in foreign_keys)


def test_sql_files_do_not_include_destructive_object_or_data_removal():
    sql = "\n".join((ROOT / "supabase" / name).read_text(encoding="utf-8") for name in ("schema.sql", "constraints.sql", "indexes.sql"))
    assert "drop " not in sql.lower()
    assert "delete from" not in sql.lower()
    assert "truncate " not in sql.lower()


def test_migration_baseline_and_follow_up_are_separated_and_safe():
    migrations = ROOT / "supabase" / "migrations"
    baseline = migrations / "20260827015851_baseline_schema.sql"
    follow_up = migrations / "20260827015900_add_constraints_indexes.sql"
    baseline_sql = baseline.read_text(encoding="utf-8")
    follow_up_sql = follow_up.read_text(encoding="utf-8")

    assert baseline.exists()
    assert follow_up.exists()
    assert "create table if not exists public.companies" in baseline_sql
    assert "foreign key" not in baseline_sql.lower()
    assert "create table" not in follow_up_sql.lower()
    assert "unique using index company_aliases_natural_key" in follow_up_sql
    assert "create index if not exists companies_name_normalized_idx" in follow_up_sql
    assert all(word not in follow_up_sql.lower() for word in ("drop ", "delete from", "truncate "))


def test_report_item_inspection_link_migration_is_minimal_and_safe():
    migration = ROOT / "supabase" / "migrations" / "20260827020000_add_report_items_inspection_link.sql"
    sql = migration.read_text(encoding="utf-8")

    assert migration.exists()
    assert "add column if not exists inspection_id text" in sql
    assert "constraint report_items_inspection_fk" in sql
    assert "references public.inspections (inspection_id)" in sql
    assert "on delete set null" in sql
    assert "create unique index if not exists report_items_inspection_id_unique" in sql
    assert "where inspection_id is not null" in sql
    assert "report_items_order_unique" not in sql
    assert "file_hash" not in sql
    assert all(word not in sql.lower() for word in ("drop ", "delete from", "truncate "))

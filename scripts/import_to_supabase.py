"""CSV를 Supabase용 레코드로 검증·변환한다.

기본 실행은 항상 dry-run이다. --apply가 있을 때만 REST 쓰기를 시도한다.
이번 설계 단계에서는 --apply를 실행하지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "private" / "input"


def load_env_file(env_path: Path = ROOT / ".env") -> None:
    """프로젝트 전용 .env를 읽되 이미 설정된 셸 환경변수는 유지합니다."""
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)

@dataclass(frozen=True)
class TableSpec:
    filename: str
    table: str
    columns: tuple[str, ...]
    required: tuple[str, ...]
    unique_key: tuple[str, ...]
    date_columns: tuple[str, ...] = ()
    integer_columns: tuple[str, ...] = ()
    number_columns: tuple[str, ...] = ()


@dataclass
class TablePlan:
    table: str
    source_count: int
    records: list[dict[str, object]] = field(default_factory=list)
    missing_required: int = 0
    duplicate_ids: int = 0
    orphan_company_ids: int = 0
    date_failures: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def excluded_count(self) -> int:
        return self.source_count - len(self.records)

    @property
    def error_count(self) -> int:
        return self.missing_required + self.duplicate_ids + self.orphan_company_ids + self.date_failures


@dataclass
class RemotePreflight:
    table: str
    csv_count: int
    remote_count: int
    planned_count: int
    skip_existing: int
    error_count: int
    records: list[dict[str, object]] = field(default_factory=list)


SPECS = (
    TableSpec(
        "01_companies.csv", "companies",
        ("company_id", "permit_number", "company_name", "company_name_normalized", "address", "address_normalized", "district", "industry", "entity_type", "is_2026_target", "planned_inspection_type", "manager_alias", "air_scale", "water_scale", "air_grade", "water_grade", "target_media_waste", "source_tags", "source_record_count", "major_complaint_note", "manual_inspection_note"),
        ("company_id", "permit_number", "company_name", "company_name_normalized", "entity_type", "is_2026_target"),
        ("company_id",), integer_columns=("source_record_count",),
    ),
    TableSpec(
        "04_company_aliases.csv", "company_aliases",
        ("company_id", "alias_type", "alias_value", "normalized_value", "source", "is_primary"),
        ("company_id", "alias_type", "alias_value", "source", "is_primary"),
        ("company_id", "alias_type", "alias_value", "source"),
    ),
    TableSpec(
        "02_inspections.csv", "inspections",
        ("inspection_id", "company_id", "company_name", "inspection_date", "inspection_date_raw", "inspection_type", "inspection_media", "inspection_result_status", "inspection_result_detail", "key_findings", "suspected_violation", "on_site_action", "follow_up_action", "inspector_alias", "manager_alias", "review_status", "source_file", "source_sheet", "source_row", "match_method", "match_score"),
        ("inspection_id", "company_id", "company_name", "inspection_type", "inspection_media", "inspection_result_status", "review_status"),
        ("inspection_id",), date_columns=("inspection_date",), integer_columns=("source_row",), number_columns=("match_score",),
    ),
    TableSpec(
        "03_dispositions.csv", "dispositions",
        ("disposition_id", "company_id", "company_name", "inspection_date", "disposition_date", "violation_content", "legal_basis", "administrative_disposition", "accusation", "penalty", "violation_category", "representative_alias", "source_media", "disposition_status", "source_file", "source_sheet", "source_row", "match_method", "match_score"),
        ("disposition_id", "company_id", "company_name", "disposition_date", "violation_content", "source_media", "disposition_status"),
        ("disposition_id",), date_columns=("inspection_date", "disposition_date"), integer_columns=("source_row",), number_columns=("match_score",),
    ),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"필수 CSV 파일을 찾을 수 없습니다: {path.name}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def convert_value(value: str, column: str, spec: TableSpec) -> object:
    value = value.strip()
    if value == "":
        return None
    if column in spec.date_columns:
        return date.fromisoformat(value).isoformat()
    if column in spec.integer_columns:
        return int(value)
    if column in spec.number_columns:
        return float(value)
    return value


def build_table_plan(spec: TableSpec, rows: list[dict[str, str]], company_ids: set[str]) -> TablePlan:
    plan = TablePlan(table=spec.table, source_count=len(rows))
    seen: set[tuple[str, ...]] = set()
    for row_number, row in enumerate(rows, start=2):
        if any(not row.get(column, "").strip() for column in spec.required):
            plan.missing_required += 1
            plan.warnings.append(f"{row_number}행: 필수값 누락")
            continue
        unique_value = tuple(row.get(column, "").strip() for column in spec.unique_key)
        if unique_value in seen:
            plan.duplicate_ids += 1
            plan.warnings.append(f"{row_number}행: 중복 키 {unique_value}")
            continue
        seen.add(unique_value)
        if spec.table != "companies" and row.get("company_id", "").strip() not in company_ids:
            plan.orphan_company_ids += 1
            plan.warnings.append(f"{row_number}행: 업체마스터에 없는 company_id")
            continue
        record: dict[str, object] = {}
        try:
            for column in spec.columns:
                record[column] = convert_value(row.get(column, ""), column, spec)
        except (ValueError, TypeError):
            plan.date_failures += 1
            plan.warnings.append(f"{row_number}행: 날짜 또는 숫자 변환 실패")
            continue
        plan.records.append(record)
    return plan


def build_import_plan(input_dir: Path = DEFAULT_INPUT_DIR) -> list[TablePlan]:
    source_rows = {spec.table: read_csv(input_dir / spec.filename) for spec in SPECS}
    company_ids = {row.get("company_id", "").strip() for row in source_rows["companies"] if row.get("company_id", "").strip()}
    return [build_table_plan(spec, source_rows[spec.table], company_ids) for spec in SPECS]


def print_plan(plans: list[TablePlan]) -> None:
    print("Supabase 가져오기 dry-run 결과")
    print("DB 연결 및 쓰기: 수행하지 않음")
    for plan in plans:
        print(f"\n{plan.table}")
        print(f"  원본: {plan.source_count}")
        print(f"  등록 예정: {len(plan.records)}")
        print(f"  필수값 누락: {plan.missing_required}")
        print(f"  중복 ID/키: {plan.duplicate_ids}")
        print(f"  외래키 미연결: {plan.orphan_company_ids}")
        print(f"  날짜·숫자 변환 실패: {plan.date_failures}")
        print(f"  제외 예정: {plan.excluded_count}")
        print(f"  경고: {len(plan.warnings)}")


class SupabaseRestWriter:
    def __init__(self, url: str, key: str, opener: Callable = urlopen):
        if not url or not key:
            raise ValueError("--apply에는 SUPABASE_URL과 SUPABASE_KEY가 필요합니다.")
        self.url = url.rstrip("/")
        self.key = key
        self.opener = opener

    def fetch_rows(self, table: str, columns: tuple[str, ...]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        page_size = 1000
        offset = 0
        while True:
            query = urlencode({"select": ",".join(columns), "limit": page_size, "offset": offset})
            request = Request(
                f"{self.url}/rest/v1/{table}?{query}",
                headers={"apikey": self.key, "Accept": "application/json"},
            )
            with self.opener(request) as response:
                if response.status != 200:
                    raise RuntimeError(f"{table} 원격 사전 점검 실패: HTTP {response.status}")
                page = json.loads(response.read().decode("utf-8"))
            if not isinstance(page, list):
                raise RuntimeError(f"{table} 원격 사전 점검 응답 형식이 올바르지 않습니다.")
            rows.extend(page)
            if len(page) < page_size:
                return rows
            offset += page_size

    def insert_ignore_duplicates(self, table: str, rows: list[dict[str, object]], on_conflict: tuple[str, ...]) -> None:
        query = urlencode({"on_conflict": ",".join(on_conflict)})
        for start in range(0, len(rows), 200):
            payload = json.dumps(rows[start:start + 200], ensure_ascii=False).encode("utf-8")
            request = Request(
                f"{self.url}/rest/v1/{table}?{query}", data=payload, method="POST",
                headers={
                    "apikey": self.key,
                    "Content-Type": "application/json",
                    "Prefer": "resolution=ignore-duplicates,return=minimal",
                },
            )
            with self.opener(request) as response:
                if response.status not in (200, 201, 204):
                    raise RuntimeError(f"{table} 저장 실패: HTTP {response.status}")


def apply_import(plans: list[TablePlan], writer: SupabaseRestWriter) -> None:
    if any(plan.error_count or plan.excluded_count for plan in plans):
        raise ValueError("검증 오류 또는 제외 행이 있어 적용을 중단했습니다. dry-run 결과를 먼저 확인하세요.")
    specs_by_table = {spec.table: spec for spec in SPECS}
    for plan in plans:
        writer.insert_ignore_duplicates(plan.table, plan.records, specs_by_table[plan.table].unique_key)


def record_key(record: dict[str, object], columns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple("" if record.get(column) is None else str(record.get(column)) for column in columns)


def build_remote_preflight(plans: list[TablePlan], writer: SupabaseRestWriter) -> list[RemotePreflight]:
    """읽기 전용 REST 요청으로 원격 기존 키와 등록 예정 건수를 계산합니다."""
    specs_by_table = {spec.table: spec for spec in SPECS}
    results: list[RemotePreflight] = []
    for plan in plans:
        spec = specs_by_table[plan.table]
        remote_rows = writer.fetch_rows(plan.table, spec.unique_key)
        existing_keys = {record_key(row, spec.unique_key) for row in remote_rows}
        records = [row for row in plan.records if record_key(row, spec.unique_key) not in existing_keys]
        results.append(RemotePreflight(
            table=plan.table,
            csv_count=plan.source_count,
            remote_count=len(remote_rows),
            planned_count=len(records),
            skip_existing=len(plan.records) - len(records),
            error_count=plan.error_count + plan.excluded_count,
            records=records,
        ))
    return results


def print_remote_preflight(results: list[RemotePreflight]) -> None:
    print("원격 Supabase 사전 점검 결과")
    for result in results:
        print(f"\n{result.table}")
        print(f"  CSV: {result.csv_count}")
        print(f"  원격 기존: {result.remote_count}")
        print(f"  신규 등록 예정: {result.planned_count}")
        print(f"  skip 예정: {result.skip_existing}")
        print(f"  오류: {result.error_count}")


def apply_preflighted_import(results: list[RemotePreflight], writer: SupabaseRestWriter) -> None:
    if any(result.error_count for result in results):
        raise ValueError("사전 점검 오류 또는 제외 행이 있어 실제 적용을 중단합니다.")
    specs_by_table = {spec.table: spec for spec in SPECS}
    for result in results:
        writer.insert_ignore_duplicates(result.table, result.records, specs_by_table[result.table].unique_key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="로컬 CSV의 Supabase 가져오기 계획을 검증합니다.")
    parser.add_argument("--apply", action="store_true", help="검증된 데이터를 실제 Supabase에 저장합니다.")
    parser.add_argument("--preflight", action="store_true", help="원격 DB에 읽기 전용 사전 점검을 수행합니다.")
    args = parser.parse_args(argv)
    try:
        load_env_file()
        plans = build_import_plan()
        print_plan(plans)
        if args.preflight or args.apply:
            writer = SupabaseRestWriter(
                os.getenv("SUPABASE_URL", ""),
                os.getenv("SUPABASE_SECRET_KEY", ""),
            )
            results = build_remote_preflight(plans, writer)
            print_remote_preflight(results)
            if args.apply:
                apply_preflighted_import(results, writer)
                print("\nSupabase 저장이 완료되었습니다.")
        else:
            print("\n안내: 실제 저장은 --apply를 명시한 경우에만 수행됩니다.")
        return 0
    except (FileNotFoundError, ValueError, RuntimeError, URLError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

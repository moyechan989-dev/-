"""Read-only audit for the private input CSV files.

It never modifies input CSVs. Outputs are UTF-8 with BOM so that Excel can open
the summary correctly on Windows.
"""
from __future__ import annotations

import csv
import hashlib
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "private" / "input"
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports"

DATE_COLUMNS = {"inspection_date", "inspection_date_raw", "disposition_date", "complaint_date", "reviewed_at"}
ID_COLUMNS = {"company_id", "inspection_id", "disposition_id", "report_id", "complaint_id", "match_id"}
EXPECTED = [
    "01_companies.csv", "02_inspections.csv", "03_dispositions.csv",
    "04_company_aliases.csv", "05_report_import_template.csv",
    "06_complaint_input_template.csv", "07_matching_review.csv",
    "08_data_issues.csv", "09_data_dictionary.csv",
]


def detect_encoding(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "unknown"


def read_csv(path: Path, encoding: str) -> tuple[list[str], list[dict[str, str]]]:
    if encoding == "unknown":
        return [], []
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def duplicate_values(rows: list[dict[str, str]], column: str) -> list[str]:
    values = [row.get(column, "").strip() for row in rows if row.get(column, "").strip()]
    return sorted(value for value, count in Counter(values).items() if count > 1)


def valid_date(value: str) -> bool:
    if not value.strip():
        return True
    try:
        date.fromisoformat(value.strip()[:10])
        return True
    except ValueError:
        return False


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    body = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    body.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(body)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    files = {path.name: path for path in INPUT.glob("*.csv")}
    audit: dict[str, dict] = {}
    for name in EXPECTED:
        path = files.get(name)
        if not path:
            audit[name] = {"missing": True}
            continue
        encoding = detect_encoding(path)
        headers, rows = read_csv(path, encoding)
        empty = {h: sum(not row.get(h, "").strip() for row in rows) for h in headers}
        audit[name] = {
            "missing": False, "path": path, "encoding": encoding, "headers": headers, "rows": rows,
            "empty": empty, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    companies = audit.get("01_companies.csv", {}).get("rows", [])
    company_ids = {row.get("company_id", "").strip() for row in companies if row.get("company_id", "").strip()}
    checks: list[tuple[str, str, str]] = []
    for name, id_column in (("01_companies.csv", "company_id"), ("02_inspections.csv", "inspection_id"), ("03_dispositions.csv", "disposition_id")):
        rows = audit.get(name, {}).get("rows", [])
        duplicates = duplicate_values(rows, id_column)
        checks.append((f"{name} {id_column} 중복", "통과" if not duplicates else "확인 필요", str(len(duplicates))))
    for name, item in audit.items():
        if item.get("missing"):
            continue
        headers, rows = item["headers"], item["rows"]
        duplicate_rows = len(rows) - len({tuple(row.get(h, "") for h in headers) for row in rows})
        checks.append((f"{name} 완전 중복 행", "통과" if not duplicate_rows else "확인 필요", str(duplicate_rows)))
        nan_cells = sum(row.get(header, "").strip().lower() == "nan" for row in rows for header in headers)
        checks.append((f"{name} 문자열 NaN", "통과" if not nan_cells else "확인 필요", str(nan_cells)))
    for name in ("02_inspections.csv", "03_dispositions.csv"):
        rows = audit.get(name, {}).get("rows", [])
        orphan = [row.get("company_id", "") for row in rows if row.get("company_id", "").strip() not in company_ids]
        checks.append((f"{name}의 company_id 참조", "통과" if not orphan else "확인 필요", str(len(orphan))))
    aliases = audit.get("04_company_aliases.csv", {}).get("rows", [])
    alias_orphans = [row.get("company_id", "") for row in aliases if row.get("company_id", "").strip() not in company_ids]
    checks.append(("04_company_aliases.csv의 company_id 참조", "통과" if not alias_orphans else "확인 필요", str(len(alias_orphans))))
    for name, item in audit.items():
        if item.get("missing"):
            continue
        for column in DATE_COLUMNS.intersection(item["headers"]):
            invalid = [r[column] for r in item["rows"] if not valid_date(r.get(column, ""))]
            checks.append((f"{name} {column} 날짜", "통과" if not invalid else "확인 필요", str(len(invalid))))

    dictionary = audit.get("09_data_dictionary.csv", {}).get("rows", [])
    documented_columns = {row.get("column", "").strip() for row in dictionary}
    actual_columns = {col for item in audit.values() if not item.get("missing") for col in item["headers"]}
    checks.append(("데이터 사전 열 설명", "통과" if actual_columns <= documented_columns else "확인 필요", str(len(actual_columns - documented_columns))))
    searchable = {"company_name", "company_name_normalized", "permit_number", "address", "address_normalized", "district", "industry", "entity_type", "is_2026_target", "planned_inspection_type"}
    company_headers = set(audit.get("01_companies.csv", {}).get("headers", []))
    checks.append(("업체 검색·필터 후보 열", "통과", str(len(searchable & company_headers))))
    sensitive_candidates = {"representative", "representative_alias", "manager_alias", "inspector_alias", "reviewer_alias"}
    present_sensitive = {col for col in actual_columns if col in sensitive_candidates}
    checks.append(("가명 처리 후보 열", "검토 필요", ", ".join(sorted(present_sensitive)) or "없음"))

    quality_rows = []
    inventory_rows = []
    mapping_sections = []
    for name in EXPECTED:
        item = audit.get(name, {})
        if item.get("missing"):
            quality_rows.append([name, "없음", "-", "-", "-", "입력 폴더에 없음"])
            continue
        rows, headers, empty = item["rows"], item["headers"], item["empty"]
        max_empty = max((empty[h] / len(rows) * 100 for h in headers), default=0)
        quality_rows.append([name, item["encoding"], str(len(rows)), str(len(headers)), f"{max_empty:.1f}%", "감사 완료"])
        inventory_rows.append([name, str(item["path"].stat().st_size), item["sha256"][:16] + "…"])
        mapping_sections.append(f"## {name}\n\n- 행 수: {len(rows)}\n- 열: `" + "`, `".join(headers) + "`\n")
        profiles = []
        for header in headers:
            values = [row.get(header, "").strip() for row in rows]
            profiles.append(f"- `{header}`: 빈 값 {sum(not v for v in values)}건, 고유 비어있지 않은 값 {len(set(v for v in values if v))}건")
        mapping_sections.append("### 열 품질 요약\n\n" + "\n".join(profiles) + "\n")

    audit_markdown = "# 데이터 감사 결과\n\n이 문서는 `python scripts/audit_data.py` 실행으로 생성됩니다. 입력 CSV는 읽기만 하며 수정하지 않습니다.\n\n## 파일 요약\n\n" + markdown_table(["파일", "인코딩", "행 수", "열 수", "최대 빈 값 비율", "상태"], quality_rows) + "\n\n## 무결성 검사\n\n" + markdown_table(["검사", "결과", "문제 건수"], [list(row) for row in checks]) + "\n\n## 입력 복사본 지문\n\n" + markdown_table(["파일", "바이트", "SHA-256 앞 16자리"], inventory_rows) + "\n"
    (DOCS / "DATA_AUDIT.md").write_text(audit_markdown, encoding="utf-8")
    supabase_mapping = """
## Supabase CSV 매핑

| CSV | DB 테이블 | 기본/중복 방지 키 | 변환 |
| --- | --- | --- | --- |
| `01_companies.csv` | `companies` | `company_id` | `source_record_count`만 정수, 나머지 실제 열 보존 |
| `04_company_aliases.csv` | `company_aliases` | `(company_id, alias_type, alias_value, source)` | `alias_id`는 DB에서 생성 |
| `02_inspections.csv` | `inspections` | `inspection_id` | `inspection_date`는 date, `inspection_date_raw`는 text 보존 |
| `03_dispositions.csv` | `dispositions` | `disposition_id` | `inspection_date`, `disposition_date`는 date |

CSV의 기존 열은 DB에서도 같은 이름을 사용한다. 향후 입력용 열은 별도로 추가한다. `source_*`, `match_*`, 검토 상태는 이력 추적을 위해 보존하지만 일반 업체 조회 화면의 검색·표시 대상에서는 제외한다.
"""
    mapping = "# 데이터 매핑\n\n이 문서는 실제 `data/private/input` CSV의 헤더를 기준으로 생성됩니다. 검색·필터는 업체 마스터에 실제 존재하고 업무상 허용된 열만 사용합니다.\n\n" + "\n".join(mapping_sections) + "\n" + supabase_mapping
    (DOCS / "DATA_MAPPING.md").write_text(mapping, encoding="utf-8")
    with (REPORTS / "data_quality_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["파일", "인코딩", "행 수", "열 수", "최대 빈 값 비율", "상태"])
        writer.writerows(quality_rows)
    print(f"감사 완료: {len([x for x in audit.values() if not x.get('missing')])}개 CSV")
    for check, result, count in checks:
        print(f"- {check}: {result} (문제 {count}건)")


if __name__ == "__main__":
    main()

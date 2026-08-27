import json
from urllib.parse import parse_qs, urlparse

import pytest

from src.repositories import create_repository
from src.repositories.local_repository import LocalRepository
from src.repositories.supabase_repository import SupabaseConnectionError, SupabaseRepository


class FakeResponse:
    def __init__(self, rows, headers=None, status=200):
        self.rows = rows
        self.headers = headers or {}
        self.status = status

    def read(self):
        return json.dumps(self.rows).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_local_repository_preserves_existing_csv_loading(tmp_path):
    files = {
        "01_companies.csv": ("company_id,company_name,permit_number,address\n", "COM-1,업체,P-1,주소\n"),
        "02_inspections.csv": ("inspection_id,company_id,inspection_date\n", "INS-1,COM-1,2026-01-01\n"),
        "03_dispositions.csv": ("disposition_id,company_id,disposition_date\n", "DSP-1,COM-1,2026-01-02\n"),
        "04_company_aliases.csv": ("company_id,alias_value,normalized_value\n", "COM-1,별칭,별칭\n"),
    }
    for filename, (header, row) in files.items():
        (tmp_path / filename).write_text(header + row, encoding="utf-8-sig")
    repository = LocalRepository(tmp_path)
    assert repository.get_company("COM-1").loc[0, "company_id"] == "COM-1"
    assert len(repository.get_inspections("COM-1")) == 1
    assert len(repository.get_dispositions("COM-1")) == 1
    assert repository.get_counts() == {"companies": 1, "aliases": 1, "inspections": 1, "dispositions": 1}


def test_repository_factory_selects_local_backend():
    assert isinstance(create_repository("local"), LocalRepository)
    with pytest.raises(ValueError, match="local 또는 supabase"):
        create_repository("other")


def test_repository_factory_selects_supabase_backend(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-secret")
    assert isinstance(create_repository("supabase"), SupabaseRepository)


def test_supabase_repository_requires_server_only_settings():
    with pytest.raises(ValueError, match="Secret Key"):
        SupabaseRepository("https://example.supabase.co", "")


def test_supabase_alias_pagination_and_secret_header_only():
    aliases = [{"alias_id": index, "company_id": f"COM-{index}", "alias_value": "별칭", "normalized_value": "별칭"} for index in range(2371)]
    requests = []

    def opener(request):
        requests.append(request)
        query = parse_qs(urlparse(request.full_url).query)
        offset = int(query["offset"][0])
        return FakeResponse(aliases[offset: offset + 1000])

    result = SupabaseRepository("https://example.supabase.co", "test-secret", opener=opener).list_aliases()
    assert len(result) == 2371
    assert len(requests) == 3
    assert [parse_qs(urlparse(request.full_url).query)["offset"][0] for request in requests] == ["0", "1000", "2000"]
    header_names = {name.lower() for name, _ in requests[0].header_items()}
    assert "apikey" in header_names
    assert "authorization" not in header_names


def test_supabase_histories_are_filtered_by_company_id_and_empty_is_safe():
    requests = []

    def opener(request):
        requests.append(request)
        if "inspections" in request.full_url:
            return FakeResponse([{"inspection_id": "INS-1", "company_id": "COM-1", "inspection_date": "2026-01-01"}])
        return FakeResponse([])

    repository = SupabaseRepository("https://example.supabase.co", "test-secret", opener=opener)
    inspections = repository.get_inspections("COM-1")
    dispositions = repository.get_dispositions("COM-2")
    inspection_query = parse_qs(urlparse(requests[0].full_url).query)
    disposition_query = parse_qs(urlparse(requests[1].full_url).query)
    assert inspections["company_id"].tolist() == ["COM-1"]
    assert dispositions.empty and "company_id" in dispositions.columns
    assert inspection_query["company_id"] == ["eq.COM-1"]
    assert disposition_query["company_id"] == ["eq.COM-2"]


def test_supabase_counts_use_read_only_exact_count_headers():
    expected = {"companies": 545, "company_aliases": 2371, "inspections": 616, "dispositions": 366}

    def opener(request):
        table = urlparse(request.full_url).path.rsplit("/", 1)[1]
        return FakeResponse([], {"Content-Range": f"0-0/{expected[table]}"})

    counts = SupabaseRepository("https://example.supabase.co", "test-secret", opener=opener).get_counts()
    assert counts == {"companies": 545, "aliases": 2371, "inspections": 616, "dispositions": 366}


def test_supabase_connection_error_is_korean_and_does_not_expose_key():
    def opener(_request):
        raise OSError("network down")

    with pytest.raises(SupabaseConnectionError, match="Supabase 데이터베이스에 연결할 수 없습니다") as error:
        SupabaseRepository("https://example.supabase.co", "test-secret", opener=opener).list_companies()
    assert "test-secret" not in str(error.value)


def test_supabase_creates_one_inspection_without_authorization_header():
    requests = []

    def opener(request):
        requests.append(request)
        return FakeResponse([{"inspection_id": "INS-new", "company_id": "COM-1"}], status=201)

    saved = SupabaseRepository("https://example.supabase.co", "test-secret", opener=opener).create_inspection({
        "inspection_id": "INS-new", "company_id": "COM-1", "company_name": "검증 업체",
        "inspection_type": "정기", "inspection_media": "폐기물", "inspection_result_status": "적정",
        "review_status": "등록완료", "data_source": "manual_entry",
    })
    headers = {name.lower() for name, _ in requests[0].header_items()}
    assert saved["inspection_id"] == "INS-new"
    assert requests[0].get_method() == "POST"
    assert "apikey" in headers and "authorization" not in headers
    assert b"test-secret" not in (requests[0].data or b"")


def test_supabase_inspection_save_error_does_not_expose_key():
    def opener(_request):
        raise OSError("network down")

    with pytest.raises(SupabaseConnectionError, match="지도점검 저장 중 오류") as error:
        SupabaseRepository("https://example.supabase.co", "test-secret", opener=opener).create_inspection({})
    assert "test-secret" not in str(error.value)


def test_supabase_report_audit_methods_use_only_expected_tables_and_secret_header():
    requests = []

    def opener(request):
        requests.append(request)
        if request.get_method() == "GET":
            return FakeResponse([])
        table = urlparse(request.full_url).path.rsplit("/", 1)[1]
        return FakeResponse([{f"{table[:-1]}_id": "ID-1"}], status=201)

    repository = SupabaseRepository("https://example.supabase.co", "test-secret", opener=opener)
    assert repository.get_report_item_by_inspection_id("INS-1").empty
    repository.create_report_import({"original_filename": "A.pdf"})
    repository.create_report_item({"report_id": "REPORT-1", "inspection_id": "INS-1"})

    assert [urlparse(request.full_url).path.rsplit("/", 1)[1] for request in requests] == [
        "report_items", "report_imports", "report_items",
    ]
    assert all("authorization" not in {name.lower() for name, _ in request.header_items()} for request in requests)
    assert all(b"test-secret" not in (request.data or b"") for request in requests)

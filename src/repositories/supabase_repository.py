from __future__ import annotations

import json
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from src.repositories.base_repository import DataRepository
from src.search_service import search_companies


class SupabaseConnectionError(RuntimeError):
    """Supabase 연결 오류입니다."""


class SupabaseRepository(DataRepository):
    """서버 측 Secret Key로만 사용하는 Supabase REST 저장소입니다."""

    PAGE_SIZE = 1000
    EMPTY_COLUMNS = {
        "companies": ["company_id", "company_name", "permit_number", "address"],
        "company_aliases": ["company_id", "alias_value", "normalized_value"],
        "inspections": ["inspection_id", "company_id", "inspection_date"],
        "dispositions": ["disposition_id", "company_id", "disposition_date"],
    }

    def __init__(self, url: str, secret_key: str, opener: Callable = urlopen):
        if not url or not secret_key:
            raise ValueError("Supabase 조회에는 URL과 서버 전용 Secret Key가 필요합니다.")
        self.url = url.rstrip("/")
        self.secret_key = secret_key
        self.opener = opener

    def _fetch_rows(self, table: str, params: dict[str, object] | None = None) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        offset = 0
        base_params = {"select": "*", **(params or {})}
        while True:
            query = urlencode({**base_params, "limit": self.PAGE_SIZE, "offset": offset})
            request = Request(
                f"{self.url}/rest/v1/{table}?{query}",
                headers={"apikey": self.secret_key, "Accept": "application/json"},
            )
            try:
                with self.opener(request) as response:
                    if response.status != 200:
                        raise SupabaseConnectionError(f"Supabase 데이터베이스에 연결할 수 없습니다. HTTP {response.status}")
                    page = json.loads(response.read().decode("utf-8"))
            except SupabaseConnectionError:
                raise
            except Exception as error:
                raise SupabaseConnectionError("Supabase 데이터베이스에 연결할 수 없습니다.") from error
            if not isinstance(page, list):
                raise SupabaseConnectionError("Supabase 조회 응답 형식이 올바르지 않습니다.")
            rows.extend(page)
            if len(page) < self.PAGE_SIZE:
                if not rows:
                    return pd.DataFrame(columns=self.EMPTY_COLUMNS.get(table, []))
                return pd.DataFrame(rows).fillna("")
            offset += self.PAGE_SIZE

    def _count(self, table: str) -> int:
        query = urlencode({"select": "*", "limit": 1})
        request = Request(
            f"{self.url}/rest/v1/{table}?{query}",
            headers={"apikey": self.secret_key, "Accept": "application/json", "Prefer": "count=exact"},
        )
        try:
            with self.opener(request) as response:
                content_range = response.headers.get("Content-Range", "")
        except Exception as error:
            raise SupabaseConnectionError("Supabase 데이터베이스에 연결할 수 없습니다.") from error
        if "/" not in content_range:
            raise SupabaseConnectionError("Supabase 건수 조회 응답을 확인할 수 없습니다.")
        return int(content_range.rsplit("/", 1)[1])

    def list_companies(self) -> pd.DataFrame:
        return self._fetch_rows("companies", {"order": "company_name.asc,company_id.asc"})

    def list_aliases(self) -> pd.DataFrame:
        return self._fetch_rows("company_aliases", {"order": "alias_id.asc"})

    def list_inspections(self) -> pd.DataFrame:
        return self._fetch_rows("inspections", {"order": "inspection_id.asc"})

    def get_company(self, company_id: str) -> pd.DataFrame:
        return self._fetch_rows("companies", {"company_id": f"eq.{company_id}", "limit": 1})

    def search_companies(self, query: str = "", filters: dict[str, str] | None = None) -> pd.DataFrame:
        return search_companies(self.list_companies(), self.list_aliases(), query, filters)

    def get_inspections(self, company_id: str) -> pd.DataFrame:
        return self._fetch_rows("inspections", {
            "company_id": f"eq.{company_id}",
            "order": "inspection_date.desc.nullslast,inspection_id.asc",
        })

    def get_dispositions(self, company_id: str) -> pd.DataFrame:
        return self._fetch_rows("dispositions", {
            "company_id": f"eq.{company_id}",
            "order": "disposition_date.desc.nullslast,disposition_id.asc",
        })

    def create_inspection(self, record: dict[str, object]) -> dict[str, object]:
        request = Request(
            f"{self.url}/rest/v1/inspections",
            data=json.dumps(record, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "apikey": self.secret_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
        try:
            with self.opener(request) as response:
                if response.status not in (200, 201):
                    raise SupabaseConnectionError("지도점검 저장 중 오류가 발생했습니다.")
                saved = json.loads(response.read().decode("utf-8"))
        except SupabaseConnectionError:
            raise
        except Exception as error:
            raise SupabaseConnectionError("지도점검 저장 중 오류가 발생했습니다.") from error
        if not isinstance(saved, list) or len(saved) != 1 or not isinstance(saved[0], dict):
            raise SupabaseConnectionError("지도점검 저장 중 오류가 발생했습니다.")
        return saved[0]

    def get_counts(self) -> dict[str, int]:
        return {
            "companies": self._count("companies"),
            "aliases": self._count("company_aliases"),
            "inspections": self._count("inspections"),
            "dispositions": self._count("dispositions"),
        }

    def _group_counts(self, field: str, label: str) -> pd.DataFrame:
        values = self.list_companies()[field].replace("", "미등록")
        return values.value_counts().rename_axis(label).reset_index(name="업체 수")

    def get_district_counts(self) -> pd.DataFrame:
        return self._group_counts("district", "지역별 업체 수")

    def get_industry_counts(self) -> pd.DataFrame:
        return self._group_counts("industry", "업종별 업체 수")

    def get_2026_target_count(self) -> int:
        return int(self.list_companies()["is_2026_target"].eq("Y").sum())

    def load_all(self) -> dict[str, pd.DataFrame]:
        return {
            "companies": self.list_companies(),
            "inspections": self.list_inspections(),
            "dispositions": self._fetch_rows("dispositions", {"order": "disposition_id.asc"}),
            "aliases": self.list_aliases(),
        }

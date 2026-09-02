from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import INPUT_DIR
from src.data_loader import load_all_data
from src.repositories.base_repository import DataRepository
from src.search_service import search_companies


class LocalRepository(DataRepository):
    def __init__(self, input_dir: Path = INPUT_DIR):
        self.input_dir = input_dir

    def load_all(self) -> dict[str, pd.DataFrame]:
        return load_all_data(self.input_dir)

    def list_companies(self) -> pd.DataFrame:
        return self.load_all()["companies"]

    def list_aliases(self) -> pd.DataFrame:
        return self.load_all()["aliases"]

    def list_inspections(self) -> pd.DataFrame:
        return self.load_all()["inspections"]

    def get_company(self, company_id: str) -> pd.DataFrame:
        companies = self.list_companies()
        return companies.loc[companies["company_id"].eq(company_id)].copy()

    def search_companies(self, query: str = "", filters: dict[str, str] | None = None) -> pd.DataFrame:
        return search_companies(self.list_companies(), self.list_aliases(), query, filters)

    def get_inspections(self, company_id: str) -> pd.DataFrame:
        inspections = self.list_inspections()
        return inspections.loc[inspections["company_id"].eq(company_id)].copy()

    def get_dispositions(self, company_id: str) -> pd.DataFrame:
        dispositions = self.load_all()["dispositions"]
        return dispositions.loc[dispositions["company_id"].eq(company_id)].copy()

    def create_inspection(self, record: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("지도점검 등록은 Supabase 모드에서 사용할 수 있습니다.")

    def get_report_item_by_inspection_id(self, inspection_id: str) -> pd.DataFrame:
        return pd.DataFrame(columns=["report_item_id", "inspection_id"])

    def create_report_import(self, record: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("출장보고서 처리이력 저장은 Supabase 모드에서 사용할 수 있습니다.")

    def create_report_item(self, record: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("출장보고서 처리이력 저장은 Supabase 모드에서 사용할 수 있습니다.")

    def get_counts(self) -> dict[str, int]:
        data = self.load_all()
        return {name: len(data[name]) for name in ("companies", "aliases", "inspections", "dispositions")}

    def _group_counts(self, field: str, label: str) -> pd.DataFrame:
        values = self.list_companies()[field].replace("", "미등록")
        return values.value_counts().rename_axis(label).reset_index(name="업체 수")

    def get_district_counts(self) -> pd.DataFrame:
        return self._group_counts("district", "지역별 업체 수")

    def get_industry_counts(self) -> pd.DataFrame:
        return self._group_counts("industry", "업종별 업체 수")

    def get_2026_target_count(self) -> int:
        return int(self.list_companies()["is_2026_target"].eq("Y").sum())

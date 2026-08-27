from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataRepository(ABC):
    @abstractmethod
    def list_companies(self) -> pd.DataFrame:
        """업체 전체를 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def list_aliases(self) -> pd.DataFrame:
        """업체 별칭 전체를 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def list_inspections(self) -> pd.DataFrame:
        """점검유형·결과 목록 등에 필요한 지도점검 전체를 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def search_companies(self, query: str = "", filters: dict[str, str] | None = None) -> pd.DataFrame:
        """통합 검색과 필터 조건에 맞는 업체를 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def get_company(self, company_id: str) -> pd.DataFrame:
        """company_id의 업체 기본정보를 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def get_inspections(self, company_id: str) -> pd.DataFrame:
        """company_id의 지도점검 이력을 최신 날짜순으로 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def get_dispositions(self, company_id: str) -> pd.DataFrame:
        """company_id의 행정처분 이력을 최신 날짜순으로 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def create_inspection(self, record: dict[str, object]) -> dict[str, object]:
        """신규 지도점검 한 건을 등록합니다."""
        raise NotImplementedError

    @abstractmethod
    def get_counts(self) -> dict[str, int]:
        """조회 화면에 필요한 전체 건수를 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def get_district_counts(self) -> pd.DataFrame:
        """지역별 업체 수를 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def get_industry_counts(self) -> pd.DataFrame:
        """업종별 업체 수를 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def get_2026_target_count(self) -> int:
        """2026년 점검대상 업체 수를 반환합니다."""
        raise NotImplementedError

    @abstractmethod
    def load_all(self) -> dict[str, pd.DataFrame]:
        """조회 화면에 필요한 네 데이터 집합을 반환한다."""
        raise NotImplementedError

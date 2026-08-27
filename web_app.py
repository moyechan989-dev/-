from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.repositories import create_repository
from src.repositories.base_repository import DataRepository
from src.search_service import FILTER_COLUMNS, option_values, search_companies


ROOT_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=ROOT_DIR / "templates")
TEMPLATES.env.filters["format_number"] = lambda value: f"{int(value):,}"

FILTER_LABELS = {
    "district": "지역",
    "industry": "업종",
    "entity_type": "업체구분",
    "is_2026_target": "2026 점검대상",
    "planned_inspection_type": "예정 점검유형",
}


def create_web_app(repository_factory: Callable[[], DataRepository] = create_repository) -> FastAPI:
    """기존 repository·검색 서비스를 사용하는 업체조회 전용 웹 UI다."""
    app = FastAPI(title="폐기물처리업체 통합 이력관리", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/companies", status_code=307)

    @app.get("/companies", response_class=HTMLResponse, name="companies")
    async def companies(
        request: Request,
        query: str = "",
        district: str = "",
        industry: str = "",
        entity_type: str = "",
        is_2026_target: str = "",
        planned_inspection_type: str = "",
    ) -> HTMLResponse:
        repository = repository_factory()
        company_data = repository.list_companies()
        aliases = repository.list_aliases()
        selected_filters = {
            "district": district,
            "industry": industry,
            "entity_type": entity_type,
            "is_2026_target": is_2026_target,
            "planned_inspection_type": planned_inspection_type,
        }
        results = search_companies(company_data, aliases, query, selected_filters)
        counts = repository.get_counts()
        return TEMPLATES.TemplateResponse(
            request=request,
            name="companies.html",
            context={
                "query": query,
                "filters": selected_filters,
                "filter_options": _filter_options(company_data),
                "companies": _company_rows(results),
                "result_count": len(results),
                "counts": counts,
            },
        )

    return app


def _filter_options(companies: pd.DataFrame) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for column in FILTER_COLUMNS:
        values = option_values(companies, column)
        options.append({
            "field": column,
            "label": FILTER_LABELS[column],
            "choices": [{"value": "", "label": "전체"}, *[
                {"value": value, "label": _filter_label(column, value)} for value in values
            ], {"value": "미등록", "label": "미등록"}],
        })
    return options


def _filter_label(column: str, value: str) -> str:
    if column == "is_2026_target":
        return {"Y": "대상", "N": "비대상"}.get(value, value)
    return value


def _company_rows(companies: pd.DataFrame) -> list[dict[str, str]]:
    columns = (
        "company_id", "company_name", "permit_number", "address", "district", "industry",
        "entity_type", "is_2026_target", "planned_inspection_type",
    )
    rows: list[dict[str, str]] = []
    for _, source in companies.iterrows():
        row = {column: _display_value(source.get(column)) for column in columns}
        row["target_label"] = "대상" if row["is_2026_target"] == "Y" else "-"
        rows.append(row)
    return rows


def _display_value(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    text = str(value).strip()
    return text or "-"


app = create_web_app()

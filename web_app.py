from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4
from time import monotonic

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool
from fastapi.templating import Jinja2Templates

from src.ai_report_extractor import AiReportApiError, extract_report_with_ai, is_openai_api_key_configured
from src.company_service import build_summary, get_company_history
from src.disposition_standards import load_disposition_standards, load_disposition_general_rules, disposition_search_text
from src.disposition_ai import AI_UNAVAILABLE, answer_disposition_question
from src.config import DATA_BACKEND
from src.excel_export import all_data_filename, build_all_data_excel, build_company_history_excel, build_search_results_excel, company_history_filename
from src.inspection_service import build_inspection_record, find_duplicate_inspections
from src.inspection_knowledge_service import (
    VERIFICATION_STATUSES,
    find_similar_dispositions,
    get_inspection_knowledge_item,
    load_inspection_knowledge,
    public_case_rows,
    search_inspection_knowledge,
)
from src.pdf_batch_processor import process_pdf_files, processing_counts
from src.repositories import create_repository
from src.repositories.base_repository import DataRepository
from src.search_service import FILTER_COLUMNS, option_values, search_companies

ROOT_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=ROOT_DIR / "templates")
TEMPLATES.env.filters["format_number"] = lambda value: f"{int(value):,}"
FILTER_LABELS = {"district": "지역", "industry": "업종", "entity_type": "업체구분", "is_2026_target": "2026 점검대상", "planned_inspection_type": "예정 점검유형"}
DISPLAY_COLUMNS = {"inspection_date": "점검일", "inspection_type": "점검유형", "inspection_result_status": "점검결과", "inspection_media": "점검매체", "key_findings": "주요 점검내용", "suspected_violation": "위반 또는 지적사항", "on_site_action": "현장조치", "follow_up_action": "후속조치", "disposition_date": "처분일", "violation_content": "위반내용", "violation_category": "위반유형", "administrative_disposition": "행정처분", "accusation": "고발", "penalty": "과태료", "legal_basis": "관련 법령", "disposition_status": "처분상태"}
EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class DispositionQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def create_web_app(repository_factory: Callable[[], DataRepository] = create_repository) -> FastAPI:
    """기존 repository·서비스를 재사용하는 FastAPI HTML UI다."""
    app = FastAPI(title="폐기물처리업체 통합 이력관리", docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=os.getenv('INSPECTION_CHECKLIST_SESSION_SECRET', 'local-inspection-checklist-session-key'))
    app.state.inspection_checklists = {}
    app.state.report_sessions = {}
    app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")

    def render(request: Request, name: str, **context: Any) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request=request, name=name, context={"data_backend": DATA_BACKEND, **context})

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/companies", status_code=307)

    @app.get("/companies", response_class=HTMLResponse, name="companies")
    async def companies(request: Request, query: str = "", district: str = "", industry: str = "", entity_type: str = "", is_2026_target: str = "", planned_inspection_type: str = "") -> HTMLResponse:
        repository = repository_factory()
        filters = _filters(district, industry, entity_type, is_2026_target, planned_inspection_type)
        data = repository.list_companies()
        results = search_companies(data, repository.list_aliases(), query, filters)
        return render(request, "companies.html", query=query, filters=filters, filter_options=_filter_options(data), companies=_company_rows(results), result_count=len(results), counts=repository.get_counts())

    @app.get("/companies/{company_id}", response_class=HTMLResponse, name="company_detail")
    async def company_detail(request: Request, company_id: str) -> HTMLResponse:
        repository = repository_factory()
        company = _company_or_404(repository, company_id)
        inspections, dispositions = get_company_history(company_id, repository.get_inspections(company_id), repository.get_dispositions(company_id))
        return render(request, "company_detail.html", company=_display_record(company), inspections=_table_rows(inspections), dispositions=_table_rows(dispositions), summary=build_summary(inspections, dispositions))

    @app.get("/inspections/new", response_class=HTMLResponse, name="inspection_new")
    async def inspection_new(request: Request, query: str = "", company_id: str = "") -> HTMLResponse:
        repository = repository_factory()
        matches = search_companies(repository.list_companies(), repository.list_aliases(), query) if query.strip() else pd.DataFrame()
        company = _company_or_none(repository, company_id)
        inspections = repository.get_inspections(company_id) if company is not None else pd.DataFrame()
        dispositions = repository.get_dispositions(company_id) if company is not None else pd.DataFrame()
        return _render_inspection(request, repository, query, matches, company, inspections, dispositions)

    @app.post("/inspections/preview", response_class=HTMLResponse, name="inspection_preview")
    async def inspection_preview(request: Request, company_id: str = Form(""), inspection_date: str = Form(""), inspection_type: str = Form(""), inspection_result_status: str = Form(""), inspection_media: str = Form(""), inspection_purpose: str = Form(""), key_findings: str = Form(""), suspected_violation: str = Form(""), on_site_action: str = Form(""), follow_up_action: str = Form(""), correction_due_date: str = Form(""), next_check_points: str = Form("")) -> HTMLResponse:
        repository = repository_factory()
        company = _company_or_none(repository, company_id)
        if company is None:
            return _render_inspection(request, repository, "", pd.DataFrame(), None, pd.DataFrame(), pd.DataFrame(), error="등록할 업체를 먼저 선택해 주세요.")
        inspections, dispositions = repository.get_inspections(company_id), repository.get_dispositions(company_id)
        values = {"inspection_date": inspection_date, "inspection_type": inspection_type, "inspection_result_status": inspection_result_status, "inspection_media": inspection_media, "inspection_purpose": inspection_purpose, "key_findings": key_findings, "suspected_violation": suspected_violation, "on_site_action": on_site_action, "follow_up_action": follow_up_action, "correction_due_date": correction_due_date, "next_check_points": next_check_points}
        try:
            record = build_inspection_record(company, values)
        except ValueError as error:
            return _render_inspection(request, repository, "", pd.DataFrame(), company, inspections, dispositions, error=str(error), values=values)
        duplicate_count = len(find_duplicate_inspections(inspections, company_id, record["inspection_date"], record["inspection_type"]))
        return _render_inspection(request, repository, "", pd.DataFrame(), company, inspections, dispositions, draft=_display_record(record), duplicate_count=duplicate_count, values=values)

    @app.post("/inspections/save", response_class=HTMLResponse, name="inspection_save")
    async def inspection_save(request: Request, record_json: str = Form(""), confirmed: str = Form("")) -> HTMLResponse:
        repository = repository_factory()
        try:
            record = json.loads(record_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="등록 내용을 읽을 수 없습니다.")
        company_id = str(record.get("company_id", ""))
        company = _company_or_404(repository, company_id)
        inspections, dispositions = repository.get_inspections(company_id), repository.get_dispositions(company_id)
        if DATA_BACKEND != "supabase":
            return _render_inspection(request, repository, "", pd.DataFrame(), company, inspections, dispositions, draft=_display_record(record), error="로컬 모드에서는 DB 저장이 지원되지 않습니다.")
        if confirmed != "on":
            return _render_inspection(request, repository, "", pd.DataFrame(), company, inspections, dispositions, draft=_display_record(record), error="등록 내용을 확인해 주세요.")
        return _render_inspection(request, repository, "", pd.DataFrame(), company, inspections, dispositions, saved=_display_record(repository.create_inspection(record)))

    @app.get("/inspection-guide", response_class=HTMLResponse, name="inspection_guide")
    async def inspection_guide(
        request: Request,
        query: str = "",
        category: str = "",
        verification_status: str = "",
        manual_id: str = "",
    ) -> HTMLResponse:
        repository = repository_factory()
        items = load_inspection_knowledge()
        checklist_state = _checklist_state(request)
        selected_item = get_inspection_knowledge_item(items, manual_id)
        dispositions = repository.load_all()["dispositions"]
        if selected_item:
            case_frame = find_similar_dispositions(dispositions, selected_item)
        elif query.strip():
            case_frame = find_similar_dispositions(dispositions, {"keywords": [query]})
        else:
            case_frame = _search_dispositions(dispositions, "").head(20)
        similar_cases = public_case_rows(case_frame)
        categories = sorted({str(item.get("category", "")) for item in items if item.get("category")})
        popular_categories = _popular_disposition_categories(dispositions)
        standards = load_disposition_standards()
        return render(
            request, "inspection_guide.html", query=query, category=category,
            verification_status=verification_status, verification_statuses=VERIFICATION_STATUSES,
            categories=categories, items=search_inspection_knowledge(items, query, category, verification_status),
            selected_item=selected_item, similar_cases=similar_cases, popular_categories=popular_categories,
            selected_manual_ids=checklist_state['selected_manual_ids'],
            disposition_standards=standards,
            disposition_categories=list(dict.fromkeys(item['category'] for item in standards)),
            disposition_general_rules=load_disposition_general_rules(),
            disposition_search_text=disposition_search_text,
            disposition_ai_available=is_openai_api_key_configured(),
        )

    @app.post('/inspection-guide/ai', name='disposition_ai')
    async def disposition_ai(request: Request, body: DispositionQuestion) -> JSONResponse:
        if not is_openai_api_key_configured():
            return JSONResponse({'error': AI_UNAVAILABLE}, status_code=503)
        try:
            def analyze():
                # 조회만 수행한다. 원본 사례나 질문을 세션·DB·로그에 저장하지 않는다.
                data = repository_factory().load_all()
                return answer_disposition_question(body.question, data['dispositions'])
            result = await run_in_threadpool(analyze)
            html = TEMPLATES.get_template('disposition_ai_result.html').render(result=result)
            return JSONResponse({'result_status': result['result_status'], 'html': html})
        except Exception:
            return JSONResponse({'error': AI_UNAVAILABLE}, status_code=503)

    @app.get('/inspection-checklist', response_class=HTMLResponse, name='inspection_checklist')
    async def inspection_checklist(request: Request) -> HTMLResponse:
        items = load_inspection_knowledge()
        checklist_state = _checklist_state(request)
        checklist_items = _checklist_items(items, checklist_state)
        return render(request, 'inspection_checklist.html', checklist_items=checklist_items, checklist_state=checklist_state, progress=_checklist_progress(checklist_items, checklist_state))

    @app.post('/inspection-checklist/items/{manual_id}', name='inspection_checklist_item')
    async def inspection_checklist_item(request: Request, manual_id: str, action: str = Form('add'), return_to: str = Form('/inspection-guide')) -> RedirectResponse:
        items = load_inspection_knowledge()
        if get_inspection_knowledge_item(items, manual_id) is None:
            raise HTTPException(status_code=404, detail='점검 매뉴얼을 찾을 수 없습니다.')
        checklist_state = _checklist_state(request)
        selected = checklist_state['selected_manual_ids']
        if action == 'remove':
            checklist_state['selected_manual_ids'] = [value for value in selected if value != manual_id]
            checklist_state['checked_field_items'].pop(manual_id, None)
            checklist_state['checked_evidence_items'].pop(manual_id, None)
            checklist_state['field_notes'].pop(manual_id, None)
        elif manual_id not in selected:
            selected.append(manual_id)
        return RedirectResponse(url=_safe_local_redirect(return_to), status_code=303)

    @app.post('/inspection-checklist/items/{manual_id}/progress', name='inspection_checklist_progress')
    async def inspection_checklist_progress(request: Request, manual_id: str, field_checked: list[str] = Form(default=[]), evidence_checked: list[str] = Form(default=[]), field_note: str = Form(''), return_to: str = Form('/inspection-checklist')) -> RedirectResponse:
        items = load_inspection_knowledge()
        item = get_inspection_knowledge_item(items, manual_id)
        checklist_state = _checklist_state(request)
        if item is None or manual_id not in checklist_state['selected_manual_ids']:
            raise HTTPException(status_code=404, detail='이번 점검 체크리스트에 담긴 항목이 아닙니다.')
        checklist_state['checked_field_items'][manual_id] = _checked_indexes(field_checked, item.get('field_checks', []))
        checklist_state['checked_evidence_items'][manual_id] = _checked_indexes(evidence_checked, item.get('evidence_items', []))
        checklist_state['field_notes'][manual_id] = field_note.strip()
        return RedirectResponse(url=_safe_local_redirect(return_to), status_code=303)

    @app.post('/inspection-checklist/common-note', name='inspection_checklist_common_note')
    async def inspection_checklist_common_note(request: Request, common_note: str = Form('')) -> RedirectResponse:
        _checklist_state(request)['common_note'] = common_note.strip()
        return RedirectResponse(url='/inspection-checklist', status_code=303)

    @app.get("/dispositions", response_class=HTMLResponse, name="dispositions")
    async def dispositions(request: Request, query: str = "", view: str = "recent") -> HTMLResponse:
        data = repository_factory().load_all()["dispositions"]
        results = _search_dispositions(data, query)
        show_all = view == "all" or bool(query.strip())
        displayed = results if show_all else results.head(20)
        return render(
            request, "dispositions.html", query=query, view=view, dispositions=_table_rows(displayed),
            result_count=len(results), total_count=len(data), show_all=show_all,
        )

    @app.get("/reports", response_class=HTMLResponse, name="reports")
    async def reports(request: Request, company_query: str = "") -> HTMLResponse:
        repository = repository_factory()
        candidates = search_companies(repository.list_companies(), repository.list_aliases(), company_query).head(10) if company_query.strip() else pd.DataFrame()
        return _render_reports(request, company_query, candidates)

    @app.post("/reports", response_class=HTMLResponse, name="report_upload")
    async def report_upload(request: Request, files: list[UploadFile] = File(default=[]), company_query: str = Form("")) -> HTMLResponse:
        uploaded_files = []
        for upload in files:
            uploaded_files.append((upload.filename or "", await upload.read()))
        processed = process_pdf_files(uploaded_files)
        state = _report_state(request)
        state.update(processed=processed, analyses=[], error="")
        repository = repository_factory()
        candidates = search_companies(repository.list_companies(), repository.list_aliases(), company_query).head(10) if company_query.strip() else pd.DataFrame()
        return _render_reports(request, company_query, candidates, processed)

    @app.post("/reports/analyze", response_class=HTMLResponse, name="report_analyze")
    async def report_analyze(request: Request) -> HTMLResponse:
        state = _report_state(request)
        state["error"] = ""
        ready = [item for item in state["processed"] if item.status == "텍스트 추출 완료" and item.text.strip()]
        if not is_openai_api_key_configured():
            state["error"] = "AI 연결 설정이 필요합니다."
        elif not ready:
            state["error"] = "PDF를 업로드하고 텍스트를 먼저 추출해 주세요."
        else:
            state["analyses"] = []
            for item in ready:
                try:
                    result = await run_in_threadpool(extract_report_with_ai, item.text)
                    state["analyses"].append({"filename": item.filename, "result": result, "error": ""})
                except AiReportApiError as error:
                    state["analyses"].append({"filename": item.filename, "result": None, "error": str(error)})
                except Exception:
                    state["analyses"].append({"filename": item.filename, "result": None, "error": "AI 분석을 완료하지 못했습니다. 다시 시도해 주세요."})
        return _render_reports(request, "", pd.DataFrame())

    @app.get("/dashboard", response_class=HTMLResponse, name="dashboard")
    async def dashboard(request: Request) -> HTMLResponse:
        repository = repository_factory()
        return render(request, "dashboard.html", counts=repository.get_counts(), district_counts=_table_rows(repository.get_district_counts()), industry_counts=_table_rows(repository.get_industry_counts()), target_count=repository.get_2026_target_count())

    @app.get("/exports/companies", name="export_companies")
    async def export_companies(query: str = "", district: str = "", industry: str = "", entity_type: str = "", is_2026_target: str = "", planned_inspection_type: str = "") -> Response:
        repository = repository_factory()
        filters = _filters(district, industry, entity_type, is_2026_target, planned_inspection_type)
        return _excel_response(build_search_results_excel(search_companies(repository.list_companies(), repository.list_aliases(), query, filters), query, filters), "검색결과.xlsx")

    @app.get("/exports/companies/{company_id}", name="export_company_history")
    async def export_company_history(company_id: str) -> Response:
        repository = repository_factory()
        company = _company_or_404(repository, company_id)
        return _excel_response(build_company_history_excel(company, repository.get_inspections(company_id), repository.get_dispositions(company_id)), company_history_filename(company.get("company_name")))

    @app.get("/exports/all", name="export_all")
    async def export_all() -> Response:
        return _excel_response(build_all_data_excel(repository_factory().load_all()), all_data_filename())

    return app


def _render_inspection(request: Request, repository: DataRepository, query: str, companies: pd.DataFrame, company: pd.Series | None, inspections: pd.DataFrame, dispositions: pd.DataFrame, *, error: str = "", draft: dict[str, str] | None = None, duplicate_count: int = 0, values: dict[str, str] | None = None, saved: dict[str, str] | None = None) -> HTMLResponse:
    options = {column: sorted(value for value in inspections_all(repository, column) if value) for column in ("inspection_type", "inspection_result_status", "inspection_media")}
    checklist_state = _checklist_state(request)
    checklist_items = _checklist_items(load_inspection_knowledge(), checklist_state)
    return TEMPLATES.TemplateResponse(request=request, name="inspection_form.html", context={"data_backend": DATA_BACKEND, "query": query, "companies": _company_rows(companies), "company": _display_record(company) if company is not None else None, "history": build_summary(inspections, dispositions) if company is not None else {}, "recent_inspections": _table_rows(inspections.head(3)), "options": options, "error": error, "draft": draft, "duplicate_count": duplicate_count, "values": values or {}, "saved": saved, "checklist_items": checklist_items})



def _checklist_state(request: Request) -> dict[str, Any]:
    key = request.session.get('inspection_checklist_key')
    if not isinstance(key, str) or not key:
        key = uuid4().hex
        request.session['inspection_checklist_key'] = key
    states: dict[str, dict[str, Any]] = request.app.state.inspection_checklists
    return states.setdefault(key, {
        'selected_manual_ids': [], 'checked_field_items': {}, 'checked_evidence_items': {},
        'field_notes': {}, 'common_note': '',
    })


def _checklist_items(items: list[dict[str, Any]], checklist_state: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {str(item.get('manual_id', '')): item for item in items}
    return [by_id[manual_id] for manual_id in checklist_state['selected_manual_ids'] if manual_id in by_id]


def _checked_indexes(values: list[str], source_items: list[Any]) -> list[str]:
    allowed = {str(index) for index in range(len(source_items))}
    return sorted({str(value) for value in values if str(value) in allowed}, key=int)


def _checklist_progress(items: list[dict[str, Any]], checklist_state: dict[str, Any]) -> dict[str, int]:
    field_total = sum(len(item.get('field_checks', [])) for item in items)
    evidence_total = sum(len(item.get('evidence_items', [])) for item in items)
    field_checked = sum(len(checklist_state['checked_field_items'].get(str(item.get('manual_id', '')), [])) for item in items)
    evidence_checked = sum(len(checklist_state['checked_evidence_items'].get(str(item.get('manual_id', '')), [])) for item in items)
    return {'selected_count': len(items), 'field_checked': field_checked, 'field_total': field_total, 'evidence_checked': evidence_checked, 'evidence_total': evidence_total}


def _safe_local_redirect(value: str) -> str:
    return value if value.startswith('/') and not value.startswith('//') else '/inspection-guide'

def _report_state(request: Request) -> dict[str, Any]:
    # 원문은 쿠키나 DB에 넣지 않고, 세션별 메모리에 한 시간 동안만 유지한다.
    states = request.app.state.report_sessions
    now = monotonic()
    for key in list(states):
        if now - states[key]["updated_at"] > 3600:
            states.pop(key)
    key = request.session.get("report_key")
    if not isinstance(key, str) or key not in states:
        if len(states) >= 100:
            states.pop(min(states, key=lambda value: states[value]["updated_at"]))
        key = uuid4().hex
        request.session["report_key"] = key
        states[key] = {"processed": [], "analyses": [], "error": ""}
    states[key]["updated_at"] = now
    return states[key]


def _render_reports(request: Request, company_query: str, candidates: pd.DataFrame, processed: list[Any] | None = None) -> HTMLResponse:
    state = _report_state(request)
    processed = state["processed"] if processed is None else processed
    rows = [{"filename": item.filename, "status": item.status, "page_count": item.result.page_count if item.result else "-", "size_kb": f"{item.result.size_bytes / 1024:.0f}" if item.result else "-", "preview_text": item.preview_text, "has_more_text": item.has_more_text, "error_message": item.error_message} for item in (processed or [])]
    return TEMPLATES.TemplateResponse(request=request, name="reports.html", context={"data_backend": DATA_BACKEND, "ai_available": is_openai_api_key_configured(), "text_ready": any(item.status == "텍스트 추출 완료" and item.text.strip() for item in processed), "analyses": state["analyses"], "error": state["error"], "company_query": company_query, "candidates": _company_rows(candidates), "processed": rows, "processing_counts": processing_counts(processed or [])})


def inspections_all(repository: DataRepository, column: str) -> list[str]:
    frame = repository.list_inspections()
    return frame.get(column, pd.Series(dtype=str)).fillna("").astype(str).str.strip().unique().tolist()


def _filters(district: str, industry: str, entity_type: str, is_2026_target: str, planned_inspection_type: str) -> dict[str, str]:
    return {"district": district, "industry": industry, "entity_type": entity_type, "is_2026_target": is_2026_target, "planned_inspection_type": planned_inspection_type}


def _filter_options(companies: pd.DataFrame) -> list[dict[str, Any]]:
    return [{"field": column, "label": FILTER_LABELS[column], "choices": [{"value": "", "label": "전체"}, *[{"value": value, "label": _filter_label(column, value)} for value in option_values(companies, column)], {"value": "미등록", "label": "미등록"}]} for column in FILTER_COLUMNS]


def _filter_label(column: str, value: str) -> str:
    return {"Y": "대상", "N": "비대상"}.get(value, value) if column == "is_2026_target" else value


def _company_or_none(repository: DataRepository, company_id: str) -> pd.Series | None:
    if not company_id.strip():
        return None
    frame = repository.get_company(company_id)
    return frame.iloc[0] if not frame.empty else None


def _company_or_404(repository: DataRepository, company_id: str) -> pd.Series:
    company = _company_or_none(repository, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="업체를 찾을 수 없습니다.")
    return company


def _search_dispositions(dispositions: pd.DataFrame, query: str) -> pd.DataFrame:
    text = query.strip().casefold()
    if not text:
        return dispositions.sort_values(["disposition_date", "disposition_id"], ascending=[False, True], kind="stable")
    mask = pd.Series(False, index=dispositions.index)
    for column in ("company_name", "violation_content", "violation_category", "administrative_disposition", "accusation", "penalty", "legal_basis"):
        if column in dispositions:
            mask |= dispositions[column].fillna("").astype(str).str.casefold().str.contains(text, regex=False)
    return dispositions.loc[mask].sort_values(["disposition_date", "disposition_id"], ascending=[False, True], kind="stable")


def _popular_disposition_categories(dispositions: pd.DataFrame) -> list[dict[str, str]]:
    if "violation_category" not in dispositions:
        return []
    values = dispositions["violation_category"].fillna("").astype(str).str.strip()
    return [
        {"label": str(label), "count": str(count)}
        for label, count in values.loc[values.ne("")].value_counts().head(8).items()
    ]


def _company_rows(companies: pd.DataFrame) -> list[dict[str, str]]:
    columns = ("company_id", "company_name", "permit_number", "address", "district", "industry", "entity_type", "is_2026_target", "planned_inspection_type")
    return [{column: _display_value(row.get(column)) for column in columns} for _, row in companies.iterrows()]


def _display_record(record: pd.Series | dict[str, object]) -> dict[str, str]:
    return {str(key): _display_value(value) for key, value in dict(record).items()}


def _table_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for _, source in frame.iterrows():
        values = _display_record(source)
        rows.append({"values": values, "columns": [{"key": key, "label": DISPLAY_COLUMNS.get(key, key), "value": value} for key, value in values.items()]})
    return rows


def _display_value(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return str(value).strip() or "-"


def _excel_response(content: bytes, filename: str) -> Response:
    return Response(content=content, media_type=EXCEL_MIME, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


app = create_web_app()

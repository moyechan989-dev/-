from __future__ import annotations

import pandas as pd
import streamlit as st

from src.company_service import build_summary, get_company_history
from src.config import DATA_BACKEND
from src.excel_export import (
    all_data_filename,
    build_all_data_excel,
    build_company_history_excel,
    build_search_results_excel,
    company_history_filename,
)
from src.inspection_service import build_inspection_record, find_duplicate_inspections
from src.inspection_final_save import get_final_save_state, save_final_inspection
from src.ai_analysis_state import analyze_selected_pdf, get_ai_result, get_ai_result_version
from src.company_linking import company_information_may_differ, confirm_company_link, recommend_company_candidates
from src.inspection_review_draft import (
    complete_review,
    get_review_state,
    inspection_draft_display_values,
    invalidate_review_for_new_ai_result,
    missing_required_draft_fields,
    review_matches_ai_result,
    save_review_values,
    start_review,
)
from src.ai_report_extractor import AiReportError, AiReportResult, extract_report_with_ai, is_openai_api_key_configured
from src.pdf_batch_processor import process_pdf_files, processing_counts
from src.repositories import create_repository
from src.search_service import FILTER_COLUMNS, option_values, search_companies
from src.ui_helpers import display_frame, display_value


st.set_page_config(page_title="폐기물처리업체 통합 이력관리", layout="wide")

st.markdown("""
<style>
    .stApp { font-size: 16px; }
    section.main > div.block-container { padding-top: 0.35rem; padding-bottom: 1.5rem; }
    h1 { font-size: 1.15rem !important; margin-bottom: 0.1rem !important; }
    h2 { font-size: 1.65rem !important; margin: 0 !important; }
    h3 { font-size: 1.25rem !important; margin-top: 0.75rem !important; }
    p, label, .stCaption { font-size: 1rem; }
    [data-testid="stMetric"] { border-left: 4px solid #1F4E78; padding-left: 0.75rem; }
    [data-testid="stMetricValue"] { font-size: 1.7rem; }
    [data-testid="stDataFrame"] { font-size: 0.94rem; }
    [data-testid="stSidebar"] { border-right: 1px solid #D9E2F3; }
    .step-guide { color: #1F4E78; font-weight: 600; font-size: 1rem; margin: 0.1rem 0 0.45rem; }
</style>
""", unsafe_allow_html=True)


def show_page_header(
    title: str,
    description: str = "",
    steps: str | None = None,
) -> None:
    st.header(title)
    if description:
        st.caption(description)
    if steps:
        st.markdown(f'<div class="step-guide">{steps}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner="자료를 읽고 있습니다.")
def load_cached_data():
    repository = create_repository()
    return {"companies": repository.list_companies(), "aliases": repository.list_aliases()}


@st.cache_resource
def get_repository():
    return create_repository()


@st.cache_data(show_spinner="점검유형과 결과 목록을 읽고 있습니다.")
def load_inspection_form_options() -> tuple[list[str], list[str], list[str]]:
    inspections = create_repository().list_inspections()
    return tuple(
        sorted(value for value in inspections[column].fillna("").astype(str).str.strip().unique() if value)
        for column in ("inspection_type", "inspection_result_status", "inspection_media")
    )


def show_company_detail(company, repository) -> None:
    st.markdown("#### ④ 업체 상세")
    st.subheader(display_value(company.get("company_name")))
    st.caption(f"업체 ID: {display_value(company.get('company_id'))}")
    st.markdown("##### 기본정보")
    basic_fields = {
        "permit_number": "인허가번호", "address": "주소", "district": "지역", "industry": "업종",
        "entity_type": "업체구분", "is_2026_target": "2026 점검대상 여부", "planned_inspection_type": "예정 점검유형",
    }
    columns = st.columns(3)
    for index, (field, label) in enumerate(basic_fields.items()):
        with columns[index % 3]:
            st.markdown(f"**{label}**  {display_value(company.get(field))}")

    inspections, dispositions = get_company_history(
        company["company_id"],
        repository.get_inspections(company["company_id"]),
        repository.get_dispositions(company["company_id"]),
    )
    summary = build_summary(inspections, dispositions)
    st.markdown("##### 주요 이력 현황")
    metric_fields = ["최근 지도점검일", "전체 지도점검 건수", "최근 행정처분일", "전체 행정처분 건수"]
    summary_columns = st.columns(4)
    for column, label in zip(summary_columns, metric_fields):
        with column:
            st.metric(label, summary[label])
    st.markdown("##### 점검 참고정보")
    st.caption(f"최근 지도점검 결과: {summary['최근 지도점검 결과']}  |  최근 행정처분 내용: {summary['최근 행정처분 내용']}")

    st.download_button(
        "업체별 통합이력 엑셀 다운로드",
        data=build_company_history_excel(company, inspections, dispositions),
        file_name=company_history_filename(company.get("company_name")),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"company_history_excel_{company['company_id']}",
    )

    inspection_tab, disposition_tab = st.tabs(["지도점검 이력", "행정처분 이력"])
    with inspection_tab:
        if inspections.empty:
            st.info("등록된 지도점검 이력이 없습니다.")
        else:
            st.dataframe(display_frame(inspections, {
                "inspection_date": "점검일", "inspection_media": "점검매체", "inspection_type": "점검유형",
                "inspection_result_status": "점검결과", "key_findings": "주요 점검내용", "suspected_violation": "위반 또는 지적내용",
            }), use_container_width=True, hide_index=True)
    with disposition_tab:
        if dispositions.empty:
            st.info("등록된 행정처분 이력이 없습니다.")
        else:
            st.dataframe(display_frame(dispositions, {
                "disposition_date": "처분일", "violation_content": "위반내용", "violation_category": "위반유형",
                "administrative_disposition": "행정처분 내용", "accusation": "고발내용", "penalty": "과태료 내용",
                "legal_basis": "관련 법령", "representative_alias": "대표자(가명)", "source_media": "매체",
            }), use_container_width=True, hide_index=True)


def show_search_page(data, repository) -> None:
    show_page_header("업체 조회")
    st.markdown("**① 업체 검색**")
    query = st.text_input("통합 검색", placeholder="업체명, 인허가번호, 주소를 입력하세요")
    st.markdown("**② 상세 필터**")
    filters = {}
    filter_labels = {
        "district": "지역", "industry": "업종", "entity_type": "업체구분",
        "is_2026_target": "2026 점검대상", "planned_inspection_type": "예정 점검유형",
    }
    filter_columns = st.columns(len(FILTER_COLUMNS))
    for ui_column, field in zip(filter_columns, FILTER_COLUMNS):
        choices = ["전체", *option_values(data["companies"], field), "미등록"]
        with ui_column:
            selected = st.selectbox(filter_labels[field], choices, key=f"filter_{field}")
        filters[field] = "" if selected == "전체" else selected
    results = search_companies(data["companies"], data["aliases"], query, filters)
    st.markdown(f"**③ 검색 결과 · {len(results):,}개 업체**")
    if results.empty:
        st.info("조건에 맞는 업체가 없습니다. 검색어 또는 필터를 확인하세요.")
        return
    preview = display_frame(results, {
        "company_name": "업체명", "permit_number": "인허가번호", "address": "주소", "district": "지역",
        "industry": "업종", "entity_type": "업체구분", "is_2026_target": "2026 점검대상", "planned_inspection_type": "예정 점검유형",
    })
    st.dataframe(preview, use_container_width=True, hide_index=True)
    st.download_button(
        "현재 검색결과 엑셀 다운로드",
        data=build_search_results_excel(results, query, filters),
        file_name=f"검색결과_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="search_results_excel",
    )
    ids = results["company_id"].tolist()
    selected_id = st.selectbox(
        "상세 조회할 업체", ids,
        format_func=lambda company_id: f"{display_value(results.loc[results['company_id'].eq(company_id), 'company_name'].iloc[0])} ({company_id})",
    )
    show_company_detail(results.loc[results["company_id"].eq(selected_id)].iloc[0], repository)


def show_inspection_registration(data, repository) -> None:
    show_page_header(
        "지도점검 등록",
        "기존 업체를 선택한 뒤 점검 내용을 확인하고 지도점검 이력에 등록합니다.",
        "① 업체 선택  →  ② 점검내용 입력  →  ③ 확인 및 저장",
    )
    if DATA_BACKEND != "supabase":
        st.info("지도점검 등록은 Supabase 모드에서 사용할 수 있습니다.")
        return

    st.markdown("#### ① 업체 선택")
    query = st.text_input("등록할 업체 검색", placeholder="업체명, 인허가번호, 주소 또는 업체별칭", key="registration_company_query")
    if not query.strip():
        st.info("먼저 업체명, 인허가번호, 주소 또는 업체별칭으로 업체를 검색하세요.")
        return
    results = search_companies(data["companies"], data["aliases"], query)
    if results.empty:
        st.warning("일치하는 업체가 없습니다. 기존 업체를 다시 검색하세요.")
        return
    selected_id = st.selectbox(
        "등록할 업체 선택",
        results["company_id"].tolist(),
        format_func=lambda company_id: f"{display_value(results.loc[results['company_id'].eq(company_id), 'company_name'].iloc[0])} ({company_id})",
        key="registration_company_id",
    )
    company = results.loc[results["company_id"].eq(selected_id)].iloc[0]
    st.markdown("##### 선택된 업체 정보")
    st.dataframe(display_frame(pd.DataFrame([company]), {
        "company_name": "업체명", "permit_number": "인허가번호", "address": "주소",
        "district": "지역", "industry": "업종", "company_id": "업체 ID",
    }), use_container_width=True, hide_index=True)

    inspections, dispositions = get_company_history(
        selected_id, repository.get_inspections(selected_id), repository.get_dispositions(selected_id)
    )
    st.markdown("##### 기존 이력 요약")
    summary = build_summary(inspections, dispositions)
    summary_columns = st.columns(3)
    for index, (label, value) in enumerate(summary.items()):
        with summary_columns[index % 3]:
            st.metric(label, value)
    if not inspections.empty:
        st.markdown("최근 지도점검 3건")
        st.dataframe(display_frame(inspections.head(3), {
            "inspection_date": "점검일", "inspection_type": "점검유형",
            "inspection_result_status": "점검결과", "key_findings": "주요 점검내용",
        }), use_container_width=True, hide_index=True)

    inspection_types, result_statuses, media_values = load_inspection_form_options()
    st.divider()
    st.markdown("#### ② 점검내용 입력")
    with st.form("inspection_registration_form"):
        st.markdown("##### 점검 기본정보")
        first_column, second_column = st.columns(2)
        with first_column:
            inspection_date = st.date_input("점검일 *", value=None)
            type_choice = st.selectbox("점검유형 *", ["선택하세요", *inspection_types, "기타"])
            custom_type = st.text_input("기타 점검유형", disabled=type_choice != "기타")
        with second_column:
            result_choice = st.selectbox("점검결과 *", ["선택하세요", *result_statuses, "기타"])
            custom_result = st.text_input("기타 점검결과", disabled=result_choice != "기타")
            media_choice = st.selectbox("점검매체", ["선택 안 함", *media_values])
        st.markdown("##### 점검 내용")
        inspection_purpose = st.text_area("점검목적")
        key_findings = st.text_area("주요 점검내용")
        suspected_violation = st.text_area("위반 또는 지적사항")
        st.markdown("##### 조치사항")
        on_site_action = st.text_area("현장조치")
        follow_up_action = st.text_area("후속조치")
        correction_due_date = st.date_input("시정기한", value=None)
        next_check_points = st.text_area("다음 점검 참고사항")
        submitted = st.form_submit_button("등록내용 확인")

    if submitted:
        inspection_type = custom_type.strip() if type_choice == "기타" else type_choice
        inspection_result = custom_result.strip() if result_choice == "기타" else result_choice
        try:
            record = build_inspection_record(company, {
                "inspection_date": inspection_date,
                "inspection_type": "" if inspection_type == "선택하세요" else inspection_type,
                "inspection_result_status": "" if inspection_result == "선택하세요" else inspection_result,
                "inspection_media": "" if media_choice == "선택 안 함" else media_choice,
                "inspection_purpose": inspection_purpose,
                "key_findings": key_findings,
                "suspected_violation": suspected_violation,
                "on_site_action": on_site_action,
                "follow_up_action": follow_up_action,
                "correction_due_date": correction_due_date,
                "next_check_points": next_check_points,
            })
        except ValueError as error:
            st.error(str(error))
        else:
            duplicates = find_duplicate_inspections(inspections, selected_id, record["inspection_date"], record["inspection_type"])
            st.session_state["inspection_draft"] = {
                "company_id": selected_id,
                "company_name": display_value(company.get("company_name")),
                "duplicate_count": len(duplicates),
                "record": record,
            }

    draft = st.session_state.get("inspection_draft")
    if not draft or draft["company_id"] != selected_id:
        return
    record = draft["record"]
    st.divider()
    st.markdown("#### ③ 확인 및 저장")
    if draft["duplicate_count"]:
        st.warning(f"같은 업체에 동일 날짜·점검유형의 점검이 이미 {draft['duplicate_count']}건 있습니다.")
    st.dataframe(display_frame(pd.DataFrame([record]), {
        "company_name": "업체명", "inspection_date": "점검일", "inspection_type": "점검유형",
        "inspection_result_status": "점검결과", "key_findings": "주요 점검내용",
        "suspected_violation": "위반 또는 지적사항", "follow_up_action": "후속조치",
    }), use_container_width=True, hide_index=True)
    confirmed = st.checkbox("위 내용을 확인했습니다", key="inspection_confirmed")
    duplicate_confirmed = True
    if draft["duplicate_count"]:
        duplicate_confirmed = st.checkbox("동일 날짜·점검유형의 별도 점검임을 확인했습니다", key="inspection_duplicate_confirmed")
    if st.button("지도점검 이력에 저장", disabled=not confirmed or not duplicate_confirmed):
        current_duplicates = find_duplicate_inspections(
            repository.get_inspections(selected_id), selected_id, record["inspection_date"], record["inspection_type"]
        )
        if len(current_duplicates) != draft["duplicate_count"]:
            draft["duplicate_count"] = len(current_duplicates)
            st.session_state["inspection_draft"] = draft
            st.warning("동일 업체·점검일·점검유형의 기존 이력이 변경되었습니다. 중복 여부를 다시 확인하세요.")
        else:
            try:
                saved = repository.create_inspection(record)
            except RuntimeError:
                st.error("지도점검 저장 중 오류가 발생했습니다.")
            else:
                load_cached_data.clear()
                load_inspection_form_options.clear()
                st.session_state.pop("inspection_draft", None)
                st.success("지도점검 이력이 등록되었습니다.")
                st.write(f"생성된 지도점검 ID: {display_value(saved.get('inspection_id'))}")
                st.write(f"업체명: {display_value(saved.get('company_name'))}")
                st.write(f"점검일: {display_value(saved.get('inspection_date'))}")
                refreshed = repository.get_inspections(selected_id)
                st.markdown("방금 반영된 최근 지도점검")
                st.dataframe(display_frame(refreshed.head(3), {
                    "inspection_date": "점검일", "inspection_type": "점검유형",
                    "inspection_result_status": "점검결과", "key_findings": "주요 점검내용",
                }), use_container_width=True, hide_index=True)


def show_status_page(data, repository) -> None:
    show_page_header("데이터 현황", "현재 등록된 업체와 이력 데이터의 현황을 확인합니다.")
    counts = repository.get_counts()
    metrics = st.columns(4)
    for column, (label, value) in zip(metrics, [
        ("등록 업체", counts["companies"]), ("지도점검", counts["inspections"]),
        ("행정처분", counts["dispositions"]), ("업체 별칭", counts["aliases"]),
    ]):
        with column:
            st.metric(label, value)
    st.markdown("#### 분류별 현황")
    for field, label in [("district", "지역별 업체 수"), ("industry", "업종별 업체 수"), ("is_2026_target", "2026 점검대상 업체 수")]:
        st.markdown(f"**{label}**")
        if field == "district":
            counts = repository.get_district_counts()
        elif field == "industry":
            counts = repository.get_industry_counts()
        else:
            counts = pd.DataFrame({label: ["Y"], "업체 수": [repository.get_2026_target_count()]})
        with st.expander(f"{label} 전체 보기", expanded=field == "district"):
            st.dataframe(counts, use_container_width=True, hide_index=True)
    st.download_button(
        "전체 데이터 엑셀 다운로드",
        data=build_all_data_excel(repository.load_all()),
        file_name=all_data_filename(),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="all_data_excel",
    )


def show_trip_report_upload(data, repository) -> None:
    show_page_header(
        "출장보고서 일괄 등록",
        "출장결과보고서 PDF의 텍스트를 한 화면에서 미리 확인합니다.",
        "① PDF 여러 건 선택  →  ② 전체 처리현황  →  ③ 파일별 텍스트 미리보기",
    )
    st.caption("텍스트 선택 PDF만 지원하며, 원본과 추출 텍스트는 저장하지 않습니다. 스캔 PDF는 현재 지원하지 않습니다.")
    st.markdown("#### ① PDF 여러 건 선택")
    uploaded_files = st.file_uploader(
        "출장결과보고서 PDF 선택",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if not uploaded_files:
        return
    processed_files = process_pdf_files(
        (uploaded_file.name, uploaded_file.getvalue()) for uploaded_file in uploaded_files
    )

    st.markdown("#### ② 전체 처리현황")
    counts = processing_counts(processed_files)
    summary_columns = st.columns(4)
    for column, (label, value) in zip(summary_columns, counts.items()):
        with column:
            st.metric(label, f"{value}건")

    st.markdown("#### ③ 파일별 텍스트 미리보기")
    for index, item in enumerate(processed_files, start=1):
        st.markdown(f"##### {index}. {item.filename}")
        if item.result:
            details = st.columns(3)
            details[0].metric("페이지", f"{item.result.page_count}쪽")
            details[1].metric("파일 크기", f"{item.result.size_bytes / 1024:.0f} KB")
            details[2].metric("상태", item.status)
        else:
            st.metric("상태", item.status)

        if item.status == "텍스트 추출 완료":
            st.text_area(
                "추출 텍스트 미리보기",
                item.preview_text,
                height=220,
                disabled=True,
                key=f"pdf_preview_{index}",
            )
            if item.has_more_text:
                with st.expander("전체 텍스트 보기"):
                    st.text_area(
                        "전체 추출 텍스트",
                        item.text,
                        height=360,
                        disabled=True,
                        key=f"pdf_full_text_{index}",
                    )
        elif item.status == "텍스트 없음":
            st.info("텍스트를 읽을 수 없는 PDF입니다. 스캔 문서일 수 있습니다.")
        else:
            st.error(item.error_message)
        saved_result = get_ai_result(st.session_state, item.filename, item.text)
        existing_review = get_review_state(st.session_state, item.filename, item.text)
        final_saved = bool(existing_review and existing_review.get("final_save", {}).get("status") == "saved")
        analysis_label = "AI 다시 분석" if saved_result else "AI 분석"
        analyze_clicked = st.button(
            analysis_label,
            key=f"pdf_ai_analysis_{index}",
            disabled=item.status != "텍스트 추출 완료" or not is_openai_api_key_configured() or final_saved,
        )
        if final_saved:
            st.caption("이미 저장된 PDF는 기존 저장 이력의 일관성을 위해 AI 재분석하지 않습니다.")
        if analyze_clicked:
            try:
                with st.spinner("AI가 출장보고서를 분석하고 있습니다..."):
                    result = analyze_selected_pdf(
                        st.session_state,
                        item.filename,
                        item.text,
                        extract_report_with_ai,
                    )
            except AiReportError as error:
                st.error(str(error))
            else:
                saved_result = result
                invalidation = invalidate_review_for_new_ai_result(
                    st.session_state,
                    item.filename,
                    item.text,
                    saved_result,
                    get_ai_result_version(st.session_state, item.filename, item.text),
                )
                if invalidation == "invalidated":
                    st.info("AI 분석 결과가 변경되었습니다. 검토 내용을 다시 확인해주세요.")
                elif invalidation == "saved_retained":
                    st.warning("새 AI 분석 결과가 생성되었습니다. 기존 저장 이력은 유지되며, 새 분석 결과는 별도로 검토해야 합니다.")
        if not is_openai_api_key_configured():
            st.caption("OpenAI API 키가 설정되어 있지 않아 AI 분석을 사용할 수 없습니다.")
        if saved_result:
            show_ai_report_result(saved_result, index)
            review_state = get_review_state(st.session_state, item.filename, item.text)
            ai_result_version = get_ai_result_version(st.session_state, item.filename, item.text)
            if review_state and not review_matches_ai_result(review_state, saved_result, ai_result_version):
                if review_state.get("final_save", {}).get("status") == "saved":
                    st.warning("AI 분석 결과가 변경되었습니다. 기존 저장 이력은 유지되며 새 분석 결과는 다시 검토해야 합니다.")
                    review_state = None
                else:
                    invalidate_review_for_new_ai_result(
                        st.session_state, item.filename, item.text, saved_result, ai_result_version
                    )
                    st.warning("AI 분석 결과가 변경되었습니다. 검토 내용을 다시 확인해주세요.")
                    review_state = None
            if st.button("검토 및 지도점검 초안 작성", key=f"pdf_review_{index}"):
                inspection_types, result_statuses, media_values = load_inspection_form_options()
                review_state = start_review(
                    st.session_state,
                    item.filename,
                    item.text,
                    saved_result,
                    ai_result_version,
                    inspection_types,
                    result_statuses,
                    media_values,
                )
            if review_state:
                show_inspection_review_form(review_state, item.filename, item.text, index)
                if review_state["status"] == "completed":
                    show_company_linking(review_state, item.filename, item.text, data, index)
                    latest_review = get_review_state(st.session_state, item.filename, item.text)
                    if latest_review and latest_review.get("company_link"):
                        show_final_inspection_save(
                            latest_review,
                            item.filename,
                            item.text,
                            data,
                            repository,
                            index,
                            saved_result,
                            ai_result_version,
                        )
        _show_pdf_progress(
            item.status,
            saved_result,
            get_review_state(st.session_state, item.filename, item.text),
            index,
        )
        if index < len(processed_files):
            st.divider()


def show_ai_report_result(result: AiReportResult, index: int) -> None:
    st.markdown("###### AI 출장보고서 분석")
    st.markdown("**기본 정보**")
    fields = [
        ("보고서명", result.report_title), ("업체명 후보", result.company_name_candidate),
        ("출장/점검일시", result.inspection_date_raw), ("장소", result.location),
        ("출장목적", result.inspection_purpose),
    ]
    columns = st.columns(2)
    for position, (label, value) in enumerate(fields):
        with columns[position % 2]:
            st.markdown(f"**{label}**")
            st.write(value or "-")
    st.markdown("**사업장 정보**")
    st.write(f"업종: {result.business_info.industry or '-'}")
    st.write(f"허가/신고번호: {', '.join(result.business_info.permit_numbers) or '-'}")
    st.markdown("**현장 확인내용**")
    if result.field_observations:
        for observation in result.field_observations:
            st.write(f"- {observation}")
    else:
        st.write("-")


def show_inspection_review_form(review_state, filename: str, text: str, index: int) -> None:
    values = review_state["values"]
    if review_state["status"] == "completed":
        st.success("담당자 검토 완료 · 지도점검 등록 초안이 메모리에 저장되었습니다.")
        _show_inspection_draft_preview(review_state["inspection_draft"])
        return

    inspection_types, result_statuses, media_values = load_inspection_form_options()
    st.markdown("###### 담당자 검토 및 지도점검 초안")
    st.caption("AI 원본 분석 결과는 유지되며, 아래 수정값만 별도의 임시 초안으로 관리합니다. 아직 DB에 저장되지 않습니다.")
    st.caption("AI/문서 기반 제안값이며 담당자가 최종 확인합니다.")
    with st.form(f"inspection_review_form_{index}"):
        st.markdown("**출장보고서 정보 검토**")
        first_column, second_column = st.columns(2)
        with first_column:
            company_name_candidate = st.text_input("업체명 후보", value=values["company_name_candidate"])
            inspection_date_raw = st.text_input("원문 출장/점검일시", value=values["inspection_date_raw"])
            location = st.text_input("장소", value=values["location"])
            industry = st.text_input("업종", value=values["industry"])
        with second_column:
            inspection_purpose = st.text_area("출장목적", value=values["inspection_purpose"], height=100)
            permit_numbers = st.text_area("허가/신고번호", value=values["permit_numbers"], height=100)
            violation_choice = st.selectbox(
                "문서상 위반사실 명시 여부",
                ["미확인", "명시됨", "명시되지 않음"],
                index={True: 1, False: 2}.get(values["confirmed_violation_mentioned"], 0),
            )
        field_observations = st.text_area("현장 확인내용", value=values["field_observations"], height=120)
        violation_content = st.text_area("문서상 위반사실 내용", value=values["confirmed_violation_content"], height=100)
        violation_legal_basis = st.text_area("관련 법령", value=values["confirmed_violation_legal_basis"], height=80)
        violation_evidence_document = st.text_input("위반확인 근거문서", value=values["confirmed_violation_evidence_document"])
        st.markdown("**보고서상 향후 계획**")
        st.caption("향후 계획은 확정 행정처분 또는 고발로 저장되지 않습니다.")
        planned_administrative_disposition = st.text_area("행정처분 계획", value=values["planned_administrative_disposition"], height=80)
        planned_accusation = st.text_area("고발 계획", value=values["planned_accusation"], height=80)

        st.markdown("**지도점검 등록 초안**")
        st.caption(f"원문 출장/점검일시 참고: {inspection_date_raw or '-'}")
        inspection_date = st.date_input("점검일", value=values["inspection_date"])
        inspection_type_options = ["선택하세요", *inspection_types]
        result_status_options = ["선택하세요", *result_statuses]
        media_options = ["선택 안 함", *media_values]
        inspection_type = st.selectbox("점검유형", inspection_type_options, index=_choice_index(inspection_type_options, values["inspection_type"]))
        inspection_result_status = st.selectbox("점검결과", result_status_options, index=_choice_index(result_status_options, values["inspection_result_status"]))
        inspection_media = st.selectbox("점검매체", media_options, index=_choice_index(media_options, values["inspection_media"]))
        key_findings = st.text_area("주요 점검내용", value=values["key_findings"], height=120)
        suspected_violation = st.text_area("위반 또는 지적사항", value=values["suspected_violation"], height=100)
        on_site_action = st.text_area("현장조치", value=values["on_site_action"], height=80)
        follow_up_action = st.text_area("후속조치", value=values["follow_up_action"], height=100)
        correction_due_date = st.date_input("시정기한", value=values["correction_due_date"])
        next_check_points = st.text_area("다음 점검 참고사항", value=values["next_check_points"], height=80)
        reviewed = st.checkbox("위 내용을 검토했습니다")
        saved = st.form_submit_button("검토 내용 반영")
        completed = st.form_submit_button("지도점검 등록 초안 확정")

    revised_values = {
        "company_name_candidate": company_name_candidate,
        "inspection_date_raw": inspection_date_raw,
        "location": location,
        "inspection_purpose": inspection_purpose,
        "industry": industry,
        "permit_numbers": permit_numbers,
        "field_observations": field_observations,
        "confirmed_violation_mentioned": {"명시됨": True, "명시되지 않음": False}.get(violation_choice),
        "confirmed_violation_content": violation_content,
        "confirmed_violation_legal_basis": violation_legal_basis,
        "confirmed_violation_evidence_document": violation_evidence_document,
        "planned_administrative_disposition": planned_administrative_disposition,
        "planned_accusation": planned_accusation,
        "inspection_date": inspection_date,
        "inspection_type": "" if inspection_type == "선택하세요" else inspection_type,
        "inspection_result_status": "" if inspection_result_status == "선택하세요" else inspection_result_status,
        "inspection_media": "" if inspection_media == "선택 안 함" else inspection_media,
        "key_findings": key_findings,
        "suspected_violation": suspected_violation,
        "on_site_action": on_site_action,
        "follow_up_action": follow_up_action,
        "correction_due_date": correction_due_date,
        "next_check_points": next_check_points,
    }
    if saved:
        save_review_values(st.session_state, filename, text, revised_values)
        st.success("검토 수정값을 임시 초안에 반영했습니다.")
    if completed:
        if not reviewed:
            st.warning("초안을 확정하려면 검토 확인을 선택해 주세요.")
        else:
            missing = missing_required_draft_fields(revised_values)
            if missing:
                st.warning(f"다음 필수항목을 확인해주세요: {', '.join(missing)}")
            else:
                complete_review(st.session_state, filename, text, revised_values)
                st.success("지도점검 등록 초안 검토가 완료되었습니다. 다음 단계에서 업체를 연결한 후 최종 저장할 수 있습니다.")


def _choice_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def show_company_linking(review_state, filename: str, text: str, data, index: int) -> None:
    values = review_state["values"]
    st.markdown("###### ④ 업체 연결")
    st.caption("AI 또는 시스템이 업체를 자동 확정하지 않습니다. 담당자가 기존 업체를 직접 선택하고 확인해야 합니다.")
    reference_columns = st.columns(3)
    reference_columns[0].write(f"AI 업체명 후보: {values['company_name_candidate'] or '-'}")
    reference_columns[1].write(f"보고서 장소: {values['location'] or '-'}")
    reference_columns[2].write(f"보고서 업종: {values['industry'] or '-'}")

    linked = review_state.get("company_link")
    if linked:
        company = data["companies"].loc[data["companies"]["company_id"].eq(linked["selected_company_id"])]
        st.success("업체 연결 완료 · 아직 DB에는 저장되지 않았습니다.")
        if not company.empty:
            _show_selected_company(company.iloc[0], values)
        return

    recommended = recommend_company_candidates(
        data["companies"], data["aliases"], values["company_name_candidate"], values["location"], values["industry"]
    )
    st.markdown("**추천 후보**")
    if recommended.empty:
        st.info("AI 업체명 후보로 찾은 등록업체가 없습니다. 아래에서 다른 업체를 검색해 주세요.")
    else:
        st.dataframe(display_frame(recommended, {
            "company_name": "업체명", "permit_number": "인허가번호", "address": "주소", "district": "지역",
            "industry": "업종", "company_id": "업체 ID", "candidate_reason": "추천 근거",
        }), use_container_width=True, hide_index=True)

    st.markdown("**다른 업체 검색**")
    manual_query = st.text_input("업체명, 인허가번호, 주소, 업체별칭으로 검색", key=f"company_link_query_{index}")
    manual_results = search_companies(data["companies"], data["aliases"], manual_query) if manual_query.strip() else data["companies"].iloc[0:0]
    if manual_query.strip():
        if manual_results.empty:
            st.info("수동 검색 결과가 없습니다.")
        else:
            st.dataframe(display_frame(manual_results, {
                "company_name": "업체명", "permit_number": "인허가번호", "address": "주소", "district": "지역",
                "industry": "업종", "company_id": "업체 ID",
            }), use_container_width=True, hide_index=True)

    choices = pd.concat([recommended, manual_results], ignore_index=True).drop_duplicates("company_id")
    company_ids = ["", *choices["company_id"].astype(str).tolist()]
    selected_id = st.selectbox(
        "연결할 업체 선택",
        company_ids,
        format_func=lambda company_id: "선택하세요" if not company_id else _company_option_label(choices, company_id),
        key=f"company_link_choice_{index}",
    )
    if not selected_id:
        return
    selected_company = choices.loc[choices["company_id"].astype(str).eq(selected_id)].iloc[0]
    _show_selected_company(selected_company, values)
    if company_information_may_differ(values["company_name_candidate"], values["location"], selected_company):
        st.warning("보고서의 업체 정보와 선택한 업체 정보가 다를 수 있습니다. 다시 확인해 주세요.")
    confirmed = st.checkbox("이 업체가 맞음을 확인했습니다", key=f"company_link_confirmed_{index}")
    if st.button("업체 연결 확정", key=f"company_link_confirm_{index}", disabled=not confirmed):
        try:
            confirm_company_link(st.session_state, filename, text, selected_company, confirmed=True)
        except ValueError as error:
            st.error(str(error))
        else:
            st.success("업체 연결을 확정했습니다. 아직 DB에는 저장되지 않았습니다.")


def show_final_inspection_save(
    review_state,
    filename: str,
    text: str,
    data,
    repository,
    index: int,
    current_ai_result: AiReportResult,
    current_ai_result_version: int | None,
) -> None:
    """검토 초안을 담당자가 최종 확인한 경우에만 기존 지도점검 저장 경로로 보낸다."""
    values = review_state["values"]
    draft = review_state["inspection_draft"]
    linked = review_state["company_link"]
    if not review_matches_ai_result(review_state, current_ai_result, current_ai_result_version):
        st.warning("AI 분석 결과가 변경되었습니다. 검토 내용을 다시 확인해주세요.")
        return
    company_rows = data["companies"].loc[
        data["companies"]["company_id"].astype(str).eq(str(linked["selected_company_id"]))
    ]
    st.markdown("###### ⑤ 최종 확인 및 지도점검 저장")
    if company_rows.empty:
        st.error("확정한 업체 정보를 현재 업체 목록에서 찾을 수 없습니다. 업체 연결을 다시 확인해 주세요.")
        return
    company = company_rows.iloc[0]
    saved_state = get_final_save_state(review_state)
    if saved_state and saved_state.get("status") == "saved":
        st.success("이 PDF의 지도점검 이력이 저장되었습니다.")
        st.write(f"지도점검 ID: {display_value(saved_state.get('inspection_id'))}")
        st.write(f"업체명: {display_value(saved_state.get('company_name'))}")
        st.write(f"점검일: {display_value(saved_state.get('inspection_date'))}")
        _show_recent_saved_inspections(repository, str(company["company_id"]), index)
        return

    st.markdown("**연결 업체**")
    st.dataframe(display_frame(pd.DataFrame([company]), {
        "company_name": "업체명", "company_id": "업체 ID", "permit_number": "인허가번호",
        "address": "주소", "district": "지역", "industry": "업종",
    }), use_container_width=True, hide_index=True)

    _show_inspection_draft_preview(draft, heading="지도점검 등록 내용")

    st.markdown("**보고서 참고정보 (지도점검 저장값 아님)**")
    st.caption(
        f"AI 업체명 후보: {values['company_name_candidate'] or '-'}  |  "
        f"원문 출장/점검 일시: {values['inspection_date_raw'] or '-'}"
    )
    st.write(f"보고서상 향후 행정처분 계획: {values['planned_administrative_disposition'] or '-'}")
    st.write(f"보고서상 향후 고발 계획: {values['planned_accusation'] or '-'}")
    st.caption("향후 계획은 확정 행정처분 또는 고발로 저장하지 않으며, 행정처분 데이터에는 아무것도 저장하지 않습니다.")

    if DATA_BACKEND != "supabase":
        st.info("지도점검 저장은 Supabase 모드에서만 사용할 수 있습니다.")
        return

    existing = repository.get_inspections(str(company["company_id"]))
    duplicates = find_duplicate_inspections(
        existing, str(company["company_id"]), draft.get("inspection_date"), str(draft.get("inspection_type") or "")
    )
    duplicate_count = len(duplicates)
    if duplicate_count:
        st.warning(f"같은 업체·점검일·점검유형의 기존 지도점검 이력이 {duplicate_count}건 있습니다.")
        st.dataframe(display_frame(duplicates.head(3), {
            "inspection_date": "점검일", "inspection_type": "점검유형",
            "inspection_result_status": "점검결과", "key_findings": "주요 점검내용",
        }), use_container_width=True, hide_index=True)

    final_confirmed = st.checkbox(
        "선택 업체와 지도점검 등록내용을 최종 확인했습니다.",
        key=f"pdf_final_save_confirmed_{index}",
    )
    duplicate_confirmed = True
    if duplicate_count:
        duplicate_confirmed = st.checkbox(
            "동일 업체·점검일·점검유형의 기존 이력을 확인했습니다.",
            key=f"pdf_final_save_duplicate_confirmed_{index}",
        )
    if st.button(
        "지도점검 이력 저장",
        key=f"pdf_final_save_{index}",
        disabled=not final_confirmed or not duplicate_confirmed,
    ):
        current_duplicates = find_duplicate_inspections(
            repository.get_inspections(str(company["company_id"])),
            str(company["company_id"]), draft.get("inspection_date"), str(draft.get("inspection_type") or ""),
        )
        if len(current_duplicates) != duplicate_count:
            st.warning("저장 직전에 동일 업체·점검일·점검유형의 기존 이력이 변경되었습니다. 중복 여부를 다시 확인해 주세요.")
            return
        try:
            saved, _ = save_final_inspection(
                st.session_state,
                filename,
                text,
                company,
                repository.create_inspection,
                current_ai_result,
                current_ai_result_version,
            )
        except (RuntimeError, ValueError):
            st.error("지도점검 이력 저장 중 오류가 발생했습니다. 검토 내용은 유지되어 다시 시도할 수 있습니다.")
        else:
            load_cached_data.clear()
            load_inspection_form_options.clear()
            st.success("지도점검 이력이 저장되었습니다.")
            st.write(f"지도점검 ID: {display_value(saved.get('inspection_id'))}")
            st.write(f"업체명: {display_value(saved.get('company_name'))}")
            st.write(f"점검일: {display_value(saved.get('inspection_date'))}")
            _show_recent_saved_inspections(repository, str(company["company_id"]), index)


def _show_recent_saved_inspections(repository, company_id: str, index: int) -> None:
    refreshed = repository.get_inspections(company_id)
    st.markdown("방금 반영한 업체의 최근 지도점검 3건")
    st.dataframe(display_frame(refreshed.head(3), {
        "inspection_date": "점검일", "inspection_type": "점검유형",
        "inspection_result_status": "점검결과", "key_findings": "주요 점검내용",
    }), use_container_width=True, hide_index=True, key=f"pdf_recent_inspections_{index}")


def _show_inspection_draft_preview(draft, heading: str = "지도점검 등록 초안") -> None:
    values = inspection_draft_display_values(draft)
    st.markdown(f"**{heading}**")
    compact_fields = ("점검일", "점검유형", "점검결과", "점검매체", "시정기한", "다음 점검 참고사항")
    columns = st.columns(3)
    for position, label in enumerate(compact_fields):
        with columns[position % 3]:
            st.markdown(f"**{label}**")
            st.write(values[label])
    for label in ("점검목적", "주요 점검내용", "위반·지적사항", "현장조치", "후속조치"):
        st.markdown(f"**{label}**")
        st.write(values[label])


def _show_selected_company(company, report_values) -> None:
    st.markdown("**선택한 업체**")
    st.dataframe(display_frame(pd.DataFrame([company]), {
        "company_name": "업체명", "permit_number": "인허가번호", "address": "주소", "district": "지역",
        "industry": "업종", "company_id": "업체 ID",
    }), use_container_width=True, hide_index=True)
    st.caption(
        f"보고서 업체명 후보: {report_values['company_name_candidate'] or '-'}  |  "
        f"보고서 장소: {report_values['location'] or '-'}  |  보고서 업종: {report_values['industry'] or '-'}"
    )


def _company_option_label(companies: pd.DataFrame, company_id: str) -> str:
    company = companies.loc[companies["company_id"].astype(str).eq(company_id)].iloc[0]
    return f"{company['company_name']} ({company_id})"


def _show_pdf_progress(pdf_status: str, result: AiReportResult | None, review_state, index: int) -> None:
    statuses = [f"① 텍스트 추출 {'완료' if pdf_status == '텍스트 추출 완료' else pdf_status}"]
    statuses.append(f"② AI 분석 {'완료' if result else '대기'}")
    if review_state:
        statuses.append("③ 담당자 검토 완료" if review_state["status"] == "completed" else "③ 담당자 검토 중")
        if review_state.get("company_link"):
            statuses.append("④ 업체 연결 완료")
        else:
            statuses.append("④ 업체 연결 대기")
        if get_final_save_state(review_state) and get_final_save_state(review_state).get("status") == "saved":
            statuses.append("⑤ 최종 확인 및 저장 완료")
        else:
            statuses.append("⑤ 최종 확인 및 저장 대기")
    else:
        statuses.extend(("③ 담당자 검토 대기", "④ 업체 연결 대기", "⑤ 최종 확인 및 저장 대기"))
    st.caption("진행 상태: " + " → ".join(statuses))
    if not result:
        return
    st.markdown("**문서에 명시된 위반사실**")
    mentioned = "명시됨" if result.confirmed_violation.mentioned is True else "명시되지 않음" if result.confirmed_violation.mentioned is False else "확인되지 않음"
    st.write(f"위반 명시 여부: {mentioned}")
    st.write(f"위반내용: {result.confirmed_violation.content or '-'}")
    st.write(f"관련 법령: {', '.join(result.confirmed_violation.legal_basis) or '-'}")
    st.write(f"위반확인 근거문서: {result.confirmed_violation.evidence_document or '-'}")
    st.markdown("**향후 계획**")
    st.caption("아래 내용은 보고서의 향후 계획이며, 확정 행정처분 또는 고발을 의미하지 않습니다.")
    st.write(f"행정처분 계획: {result.planned_actions.administrative_disposition or '-'}")
    st.write(f"고발 계획: {result.planned_actions.accusation or '-'}")
    st.markdown("**AI 요약**")
    st.write(result.summary or "-")
    st.markdown("**원문 근거**")
    evidence = pd.DataFrame([
        {"항목": item.field, "근거": item.excerpt, "페이지": item.page_hint or "-"}
        for item in result.evidence
    ])
    if evidence.empty:
        evidence = pd.DataFrame([{"항목": "-", "근거": "-", "페이지": "-"}])
    st.dataframe(evidence, use_container_width=True, hide_index=True, key=f"ai_evidence_{index}")
    st.markdown("**주의사항**")
    if result.warnings:
        for warning in result.warnings:
            st.warning(warning)
    else:
        st.write("-")


def main() -> None:
    try:
        repository = get_repository()
        data = load_cached_data()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        st.error(f"자료를 불러오지 못했습니다. {error}")
        if DATA_BACKEND == "supabase":
            st.info("로컬 CSV를 사용하려면 DATA_BACKEND=local로 변경한 뒤 다시 실행하세요.")
        st.stop()
    st.sidebar.markdown("### 업무 메뉴")
    st.sidebar.caption("폐기물처리업체 통합 이력관리")
    st.sidebar.caption(
        f"데이터 원본 · {'Supabase' if DATA_BACKEND == 'supabase' else '로컬 CSV'}"
    )
    menu = st.sidebar.radio("메뉴", ["업체 조회", "지도점검 등록", "출장보고서 등록", "데이터 현황"])
    if menu == "업체 조회":
        show_search_page(data, repository)
    elif menu == "지도점검 등록":
        show_inspection_registration(data, repository)
    elif menu == "출장보고서 등록":
        show_trip_report_upload(data, repository)
    else:
        show_status_page(data, repository)


if __name__ == "__main__":
    main()

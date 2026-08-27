from src.ai_analysis_state import (
    ai_result_fingerprint,
    ai_result_session_key,
    analyze_selected_pdf,
    get_ai_result,
    get_ai_result_version,
    save_ai_result,
)
from src.ai_report_extractor import AiReportResult, BusinessInfo, ConfirmedViolation, PlannedActions


def result() -> AiReportResult:
    return AiReportResult(
        report_title=None,
        company_name_candidate=None,
        inspection_date_raw=None,
        location=None,
        inspection_purpose=None,
        business_info=BusinessInfo(industry=None, permit_numbers=()),
        field_observations=(),
        confirmed_violation=ConfirmedViolation(mentioned=None, content=None, legal_basis=(), evidence_document=None),
        planned_actions=PlannedActions(administrative_disposition=None, accusation=None),
        summary=None,
        evidence=(),
        warnings=(),
    )


def test_results_are_kept_per_pdf_in_session_state():
    state: dict[str, object] = {}
    pdf_a = result()
    pdf_b = result()

    save_ai_result(state, "A.pdf", "A text", pdf_a)
    save_ai_result(state, "B.pdf", "B text", pdf_b)

    assert get_ai_result(state, "A.pdf", "A text") is pdf_a
    assert get_ai_result(state, "B.pdf", "B text") is pdf_b
    assert len(state) == 4


def test_rerun_reads_saved_result_without_another_analysis_call():
    state: dict[str, object] = {}
    saved = result()
    save_ai_result(state, "A.pdf", "A text", saved)

    assert get_ai_result(state, "A.pdf", "A text") is saved
    assert get_ai_result(state, "A.pdf", "A text") is saved


def test_same_filename_with_different_text_has_a_separate_result_key():
    assert ai_result_session_key("A.pdf", "first") != ai_result_session_key("A.pdf", "updated")


def test_only_the_selected_pdf_is_analyzed_and_saved():
    state: dict[str, object] = {}
    calls: list[str] = []
    expected = result()

    returned = analyze_selected_pdf(state, "A.pdf", "A text", lambda text: calls.append(text) or expected)

    assert returned is expected
    assert calls == ["A text"]
    assert get_ai_result(state, "A.pdf", "A text") is expected
    assert get_ai_result(state, "B.pdf", "B text") is None


def test_reanalysis_calls_analyzer_only_when_explicitly_requested():
    state: dict[str, object] = {}
    calls: list[str] = []

    analyze_selected_pdf(state, "A.pdf", "A text", lambda text: calls.append(text) or result())
    assert get_ai_result(state, "A.pdf", "A text") is not None
    assert calls == ["A text"]

    analyze_selected_pdf(state, "A.pdf", "A text", lambda text: calls.append(text) or result())
    assert calls == ["A text", "A text"]
    assert get_ai_result_version(state, "A.pdf", "A text") == 2


def test_ai_result_fingerprint_changes_when_structured_content_changes():
    first = result()
    changed = first.__class__(**{**first.__dict__, "summary": "다른 결과"})
    assert ai_result_fingerprint(first) != ai_result_fingerprint(changed)

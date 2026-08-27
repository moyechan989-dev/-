from __future__ import annotations

import inspect
from datetime import date

import pandas as pd

import app
from src.company_linking import confirm_company_link
from src.inspection_review_draft import complete_review, start_review
from tests.test_inspection_review_draft import report


def test_completed_review_return_is_immediately_usable_for_company_linking():
    state: dict[str, object] = {}
    review = start_review(state, "A.pdf", "A text", report())
    values = dict(review["values"])
    values.update({
        "inspection_date": date(2026, 8, 27),
        "inspection_type": "정기",
        "inspection_result_status": "적정",
        "inspection_media": "서면",
    })

    completed = complete_review(state, "A.pdf", "A text", values)

    assert completed["status"] == "completed"
    assert completed["inspection_draft"]["inspection_date"] == date(2026, 8, 27)
    linked = confirm_company_link(
        state,
        "A.pdf",
        "A text",
        pd.Series({"company_id": "COM-1", "company_name": "검증 업체"}),
        confirmed=True,
    )
    assert linked["company_link"]["selected_company_id"] == "COM-1"


def test_app_uses_completed_review_return_value_without_rerun_loop():
    upload_source = inspect.getsource(app.show_trip_report_upload)
    review_form_source = inspect.getsource(app.show_inspection_review_form)

    assert "review_state = show_inspection_review_form" in upload_source
    assert "return review_state" in review_form_source
    assert "st.rerun" not in review_form_source

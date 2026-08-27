from __future__ import annotations

import app

from src.ai_report_extractor import ConfirmedViolation
from tests.test_inspection_review_draft import report


class FakeStreamlit:
    def __init__(self):
        self.messages: list[str] = []

    def caption(self, value, **_kwargs):
        self.messages.append(str(value))

    def markdown(self, value, **_kwargs):
        self.messages.append(str(value))

    def write(self, value, **_kwargs):
        self.messages.append(str(value))

    def dataframe(self, *_args, **_kwargs):
        return None

    def warning(self, value, **_kwargs):
        self.messages.append(str(value))


def test_pdf_progress_without_ai_result_does_not_show_violation_or_raise(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(app, "st", fake_st)

    app._show_pdf_progress("텍스트 추출 완료", None, None, 1)

    assert any("② AI 분석 대기" in message for message in fake_st.messages)
    assert not any("위반사실" in message for message in fake_st.messages)


def test_pdf_progress_with_ai_result_uses_explicit_result_parameter(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(app, "st", fake_st)

    app._show_pdf_progress("텍스트 추출 완료", report(), {"status": "in_progress", "inspection_draft": None}, 1)

    assert any("AI 분석 완료" in message for message in fake_st.messages)
    assert any("위반 명시 여부: 명시됨" in message for message in fake_st.messages)


def test_pdf_progress_shows_unknown_when_confirmed_violation_is_null(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(app, "st", fake_st)
    ai_result = report().__class__(**{
        **report().__dict__,
        "confirmed_violation": ConfirmedViolation(None, None, (), None),
    })

    app._show_pdf_progress("텍스트 추출 완료", ai_result, {"status": "completed", "inspection_draft": {}}, 1)

    assert any("위반 명시 여부: 확인되지 않음" in message for message in fake_st.messages)

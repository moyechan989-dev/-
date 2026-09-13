from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

import web_app
from src import ai_report_extractor
from tests.test_ai_report_extractor import FakeClient, FailingClient, FakeApiFailure, payload
from tests.test_pdf_text_extractor import blank_pdf_bytes, text_pdf_bytes
from tests.test_web_app import make_client


class AnalyzeButton(HTMLParser):
    disabled = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "button" and attrs.get("id") == "analyze-button":
            self.disabled = "disabled" in attrs


def disabled(response):
    assert response.status_code == 200
    parser = AnalyzeButton()
    parser.feed(response.text)
    assert parser.disabled is not None
    return parser.disabled


@pytest.mark.parametrize("backend", ["local", "supabase"])
@pytest.mark.parametrize("key", [None, "", "   ", "test-key-not-for-display"])
def test_reports_requires_extracted_text_and_key_only(monkeypatch, backend, key):
    monkeypatch.setattr(web_app, "DATA_BACKEND", backend)
    if key is None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("OPENAI_API_KEY", key)
    monkeypatch.setattr(web_app, "extract_report_with_ai", lambda text: pytest.fail("업로드는 AI를 호출하면 안 됩니다"))
    client, _ = make_client()
    page = client.get("/reports")
    assert disabled(page)
    assert "출장결과보고서 AI 정리" in page.text
    assert "출장결과보고서 PDF를 업로드하면 AI가 주요 업무 항목으로 정리합니다." in page.text
    uploaded = client.post("/reports", files={"files": ("report.pdf", text_pdf_bytes(), "application/pdf")})
    assert "Hello PDF" in uploaded.text
    assert "텍스트 추출 완료" in uploaded.text
    assert disabled(uploaded) == (not bool(key and key.strip()))
    assert ("AI 연결 설정이 필요합니다." in uploaded.text) == (not bool(key and key.strip()))
    assert "test-key-not-for-display" not in uploaded.text


@pytest.mark.parametrize("backend", ["local", "supabase"])
def test_reports_calls_existing_responses_api_and_retains_review(monkeypatch, backend):
    monkeypatch.setattr(web_app, "DATA_BACKEND", backend)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake = FakeClient(payload(company_name_candidate="검증업체", inspection_date_raw="2026. 9. 14.",
                              field_observations=["보관시설 확인"], summary="<script>검증 요약</script>"))
    monkeypatch.setattr(ai_report_extractor, "_create_openai_client", lambda: fake)
    client, repository = make_client()
    full_text = "Report " + "full text " * 300
    client.post("/reports", files={"files": ("report.pdf", text_pdf_bytes(full_text), "application/pdf")})
    response = client.post("/reports/analyze")
    assert response.status_code == 200
    assert full_text.strip() == fake.responses.request["input"]
    assert fake.responses.request["store"] is False
    assert fake.responses.request["text"]["format"]["type"] == "json_schema"
    for value in ["검증업체", "2026. 9. 14.", "보관시설 확인", "위반내용 기재사항", "향후조치", "요약"]:
        assert value in response.text
    assert "<script>검증 요약</script>" not in response.text
    searched = client.get("/reports", params={"company_query": "가나다"})
    assert "검증업체" in searched.text and "가나다환경" in searched.text
    assert all(call in {"list_companies", "list_aliases"} for call in repository.calls)
    import base64
    import json
    cookie = json.loads(base64.b64decode(client.cookies["session"].split(".")[0]))
    assert set(cookie) == {"report_key"}
    # 같은 서버의 별도 브라우저도 원문/분석 결과를 공유하지 않는다.
    other = TestClient(client.app)
    assert "검증업체" not in other.get("/reports").text
    replaced = client.post("/reports", files={"files": ("new.pdf", text_pdf_bytes(), "application/pdf")})
    assert "검증업체" not in replaced.text


def test_reports_rejects_missing_text_and_key_at_route(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(web_app, "extract_report_with_ai", lambda text: pytest.fail("AI 호출 금지"))
    client, _ = make_client()
    assert "텍스트를 먼저 추출" in client.post("/reports/analyze").text
    for filename, content in [("blank.pdf", blank_pdf_bytes()), ("bad.pdf", b"invalid")]:
        assert disabled(client.post("/reports", files={"files": (filename, content, "application/pdf")}))
        assert "텍스트를 먼저 추출" in client.post("/reports/analyze").text
    client.post("/reports", files={"files": ("report.pdf", text_pdf_bytes(), "application/pdf")})
    monkeypatch.delenv("OPENAI_API_KEY")
    response = client.post("/reports/analyze")
    assert disabled(response)
    assert "AI 연결 설정이 필요합니다." in response.text


@pytest.mark.parametrize("status", [401, 429, 500])
def test_reports_api_failure_is_short_safe_and_retryable(monkeypatch, status):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake = FailingClient(FakeApiFailure("private-response-secret", status_code=status))
    monkeypatch.setattr(ai_report_extractor, "_create_openai_client", lambda: fake)
    client, _ = make_client()
    client.post("/reports", files={"files": ("report.pdf", text_pdf_bytes(), "application/pdf")})
    response = client.post("/reports/analyze")
    assert not disabled(response)
    assert 'role="alert"' in response.text
    assert "private-response-secret" not in response.text
    assert "Hello PDF" in response.text


def test_reports_expired_session_requests_reupload(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client, _ = make_client()
    client.post("/reports", files={"files": ("report.pdf", text_pdf_bytes(), "application/pdf")})
    for state in client.app.state.report_sessions.values():
        state["updated_at"] -= 3601
    assert "텍스트를 먼저 추출" in client.post("/reports/analyze").text

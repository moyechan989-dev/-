import inspect
import json

import pytest

from src.ai_report_extractor import AiReportApiError, AiReportError, DEFAULT_MODEL, OpenAiApiKeyMissingError, ai_report_schema, extract_report_with_ai, is_openai_api_key_configured
from src.pdf_batch_processor import process_pdf_files
from tests.test_pdf_text_extractor import text_pdf_bytes


def payload(**changes):
    data = {
        "report_title": None, "company_name_candidate": None, "inspection_date_raw": None, "location": None,
        "inspection_purpose": None, "business_info": {"industry": None, "permit_numbers": []},
        "field_observations": [], "confirmed_violation": {"mentioned": None, "content": None, "legal_basis": [], "evidence_document": None},
        "planned_actions": {"administrative_disposition": None, "accusation": None}, "summary": None, "evidence": [], "warnings": [],
    }
    data.update(changes)
    return data


class FakeResponses:
    def __init__(self, response_payload):
        self.response_payload = response_payload
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return type("Response", (), {"output_text": json.dumps(self.response_payload)})()


class FakeClient:
    def __init__(self, response_payload):
        self.responses = FakeResponses(response_payload)


class FakeApiFailure(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class FailingClient:
    def __init__(self, error):
        self.responses = type("Responses", (), {"create": lambda _self, **_kwargs: (_ for _ in ()).throw(error)})()


def test_trip_report_schema_has_expected_sections_and_no_company_id():
    schema = ai_report_schema()
    assert "company_id" not in schema["properties"]
    assert {"business_info", "confirmed_violation", "planned_actions", "evidence"}.issubset(schema["required"])
    assert schema["additionalProperties"] is False


def test_raw_date_with_time_and_weekday_is_preserved():
    result = extract_report_with_ai("본문", client=FakeClient(payload(inspection_date_raw="2025. 11. 11.(화) 14:00")))
    assert result.inspection_date_raw == "2025. 11. 11.(화) 14:00"


def test_permit_numbers_and_field_observations_are_arrays():
    result = extract_report_with_ai("본문", client=FakeClient(payload(
        business_info={"industry": "폐기물처리업", "permit_numbers": ["허가 1", "신고 2"]},
        field_observations=["보관시설 확인", "배출시설 확인"],
    )))
    assert result.business_info.permit_numbers == ("허가 1", "신고 2")
    assert result.field_observations == ("보관시설 확인", "배출시설 확인")


def test_violation_and_planned_actions_are_separate():
    result = extract_report_with_ai("본문", client=FakeClient(payload(
        confirmed_violation={"mentioned": True, "content": "문서 기재 위반사실", "legal_basis": ["법령 조항"], "evidence_document": "점검 사진"},
        planned_actions={"administrative_disposition": "행정처분 예정", "accusation": "고발 예정"},
    )))
    assert result.confirmed_violation.mentioned is True
    assert result.planned_actions.administrative_disposition == "행정처분 예정"


def test_evidence_can_include_only_documented_fields():
    result = extract_report_with_ai("본문", client=FakeClient(payload(evidence=[{"field": "inspection_purpose", "excerpt": "현장 확인", "page_hint": "1"}])))
    assert len(result.evidence) == 1
    assert result.evidence[0].field == "inspection_purpose"


def test_warnings_array_is_preserved():
    result = extract_report_with_ai("본문", client=FakeClient(payload(warnings=["일시가 불명확합니다."])))
    assert result.warnings == ("일시가 불명확합니다.",)


def test_rejects_company_id_and_unknown_fields():
    with pytest.raises(AiReportError, match="root"):
        extract_report_with_ai("본문", client=FakeClient(payload(company_id="C-001")))


def test_reports_validation_field_name_without_returning_raw_value():
    with pytest.raises(AiReportError, match="planned_actions.accusation") as captured:
        extract_report_with_ai("본문", client=FakeClient(payload(planned_actions={"administrative_disposition": None, "accusation": 123})))
    assert "123" not in str(captured.value)


def test_missing_api_key_never_creates_or_calls_a_live_client(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("src.ai_report_extractor._create_openai_client", lambda: pytest.fail("live client created"))
    with pytest.raises(OpenAiApiKeyMissingError):
        extract_report_with_ai("본문")


def test_empty_pdf_text_is_not_sent_to_any_client():
    client = FakeClient(payload())

    with pytest.raises(AiReportError, match="PDF 텍스트"):
        extract_report_with_ai("   ", client=client)
    assert client.responses.request is None


def test_api_key_configuration_is_detected(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert is_openai_api_key_configured() is True


@pytest.mark.parametrize(("error", "message"), [
    (FakeApiFailure("bad credentials", 401), "인증"), (FakeApiFailure("insufficient quota", 429), "사용 한도"),
    (FakeApiFailure("rate limit", 429), "요청 한도"), (ConnectionError("offline"), "연결"),
    (FakeApiFailure("unexpected"), "호출 중 오류"),
])
def test_api_failures_are_converted_to_safe_user_messages(error, message):
    with pytest.raises(AiReportApiError, match=message) as captured:
        extract_report_with_ai("본문", client=FailingClient(error))
    assert "secret" not in str(captured.value).lower()


def test_existing_pdf_text_processing_works_without_an_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = process_pdf_files([("report.pdf", text_pdf_bytes("existing PDF text"))])[0]
    assert result.status == "텍스트 추출 완료"
    assert "existing PDF text" in result.text


def test_ai_module_has_no_database_storage_dependency():
    import src.ai_report_extractor as extractor
    source = inspect.getsource(extractor).lower()
    assert "repository" not in source
    assert "supabase" not in source


def test_default_model_is_cost_efficient_luna():
    assert DEFAULT_MODEL == "gpt-5.6-luna"

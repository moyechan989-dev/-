from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol


DEFAULT_MODEL = "gpt-5.6-luna"


class AiReportError(ValueError):
    """AI 구조화 결과를 안전하게 처리할 수 없을 때 발생합니다."""


class OpenAiApiKeyMissingError(AiReportError):
    """OpenAI API 키가 없는 경우 발생합니다."""


class AiReportApiError(AiReportError):
    """사용자에게 안전하게 표시할 OpenAI API 호출 오류입니다."""


class AiReportValidationError(AiReportError):
    def __init__(self, field_name: str, validation_type: str):
        self.field_name = field_name
        self.validation_type = validation_type
        super().__init__(f"AI 응답 검증 실패: {field_name} ({validation_type})")


class StructuredOutputError(AiReportError):
    """Structured Output을 읽거나 검증할 수 없을 때 발생합니다."""


class ResponsesClient(Protocol):
    class responses(Protocol):
        @staticmethod
        def create(**kwargs: Any) -> Any: ...


def is_openai_api_key_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def ai_report_schema() -> dict[str, Any]:
    nullable_string = {"type": ["string", "null"]}
    evidence_item = {
        "type": "object",
        "properties": {"field": {"type": "string"}, "excerpt": {"type": "string"}, "page_hint": nullable_string},
        "required": ["field", "excerpt", "page_hint"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "report_title": nullable_string,
            "company_name_candidate": nullable_string,
            "inspection_date_raw": nullable_string,
            "location": nullable_string,
            "inspection_purpose": nullable_string,
            "business_info": {
                "type": "object",
                "properties": {"industry": nullable_string, "permit_numbers": {"type": "array", "items": {"type": "string"}}},
                "required": ["industry", "permit_numbers"],
                "additionalProperties": False,
            },
            "field_observations": {"type": "array", "items": {"type": "string"}},
            "confirmed_violation": {
                "type": "object",
                "properties": {
                    "mentioned": {"type": ["boolean", "null"]},
                    "content": nullable_string,
                    "legal_basis": {"type": "array", "items": {"type": "string"}},
                    "evidence_document": nullable_string,
                },
                "required": ["mentioned", "content", "legal_basis", "evidence_document"],
                "additionalProperties": False,
            },
            "planned_actions": {
                "type": "object",
                "properties": {"administrative_disposition": nullable_string, "accusation": nullable_string},
                "required": ["administrative_disposition", "accusation"],
                "additionalProperties": False,
            },
            "summary": nullable_string,
            "evidence": {"type": "array", "items": evidence_item},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "report_title", "company_name_candidate", "inspection_date_raw", "location", "inspection_purpose",
            "business_info", "field_observations", "confirmed_violation", "planned_actions", "summary", "evidence", "warnings",
        ],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class BusinessInfo:
    industry: str | None
    permit_numbers: tuple[str, ...]


@dataclass(frozen=True)
class ConfirmedViolation:
    mentioned: bool | None
    content: str | None
    legal_basis: tuple[str, ...]
    evidence_document: str | None


@dataclass(frozen=True)
class PlannedActions:
    administrative_disposition: str | None
    accusation: str | None


@dataclass(frozen=True)
class EvidenceItem:
    field: str
    excerpt: str
    page_hint: str | None


@dataclass(frozen=True)
class AiReportResult:
    report_title: str | None
    company_name_candidate: str | None
    inspection_date_raw: str | None
    location: str | None
    inspection_purpose: str | None
    business_info: BusinessInfo
    field_observations: tuple[str, ...]
    confirmed_violation: ConfirmedViolation
    planned_actions: PlannedActions
    summary: str | None
    evidence: tuple[EvidenceItem, ...]
    warnings: tuple[str, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AiReportResult":
        expected = set(ai_report_schema()["required"])
        _expect_exact_keys(payload, expected, "root")
        return cls(
            report_title=_nullable_string(payload["report_title"], "report_title"),
            company_name_candidate=_nullable_string(payload["company_name_candidate"], "company_name_candidate"),
            inspection_date_raw=_nullable_string(payload["inspection_date_raw"], "inspection_date_raw"),
            location=_nullable_string(payload["location"], "location"),
            inspection_purpose=_nullable_string(payload["inspection_purpose"], "inspection_purpose"),
            business_info=_business_info(payload["business_info"]),
            field_observations=_string_array(payload["field_observations"], "field_observations"),
            confirmed_violation=_confirmed_violation(payload["confirmed_violation"]),
            planned_actions=_planned_actions(payload["planned_actions"]),
            summary=_nullable_string(payload["summary"], "summary"),
            evidence=_evidence_items(payload["evidence"]),
            warnings=_string_array(payload["warnings"], "warnings"),
        )


def extract_report_with_ai(text: str, client: ResponsesClient | None = None) -> AiReportResult:
    if not text.strip():
        raise AiReportError("추출할 PDF 텍스트가 없습니다.")
    if client is None:
        if not is_openai_api_key_configured():
            raise OpenAiApiKeyMissingError("OpenAI API 키가 설정되어 있지 않아 AI 분석을 사용할 수 없습니다.")
        client = _create_openai_client()
    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            store=False,
            instructions=(
                "출장결과보고서의 원문에 명시된 사실만 1차 구조화하세요. company_id를 만들거나 업체를 자동 연결하지 마세요. "
                "inspection_date_raw에는 날짜·시간·요일을 포함한 원문 표현을 그대로 넣고 표준 날짜로 변환하지 마세요. "
                "field_observations는 현장 관찰·확인 내용, confirmed_violation은 문서에 위반사실이 명시된 경우만 분리하세요. "
                "planned_actions는 향후 계획일 뿐 확정 행정처분·고발이 아닙니다. 새로운 법적 판단을 만들지 마세요. "
                "근거가 있는 항목만 evidence 배열에 넣고, 문서에 없는 값은 null 또는 빈 배열로 두며 warnings에 불확실성을 기록하세요."
            ),
            input=text,
            text={"format": {"type": "json_schema", "name": "trip_report", "strict": True, "schema": ai_report_schema()}},
        )
    except Exception as error:
        raise _friendly_api_error(error) from error
    try:
        payload = json.loads(response.output_text)
    except (AttributeError, TypeError, json.JSONDecodeError) as error:
        raise StructuredOutputError("AI 구조화 응답을 읽을 수 없습니다. 다시 분석해 주세요.") from error
    try:
        return AiReportResult.from_dict(payload)
    except AiReportValidationError as error:
        raise StructuredOutputError(str(error)) from error
    except AiReportError as error:
        raise StructuredOutputError("AI 응답 검증 실패: root (형식 오류)") from error


def _create_openai_client() -> ResponsesClient:
    try:
        from openai import OpenAI
    except ImportError as error:
        raise AiReportError("OpenAI 라이브러리가 설치되어 있지 않습니다.") from error
    return OpenAI()


def _nullable_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AiReportValidationError(field_name, "문자열 또는 null 필요")
    return value.strip() or None


def _string_array(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AiReportValidationError(field_name, "문자열 배열 필요")
    return tuple(item.strip() for item in value if item.strip())


def _expect_exact_keys(value: Any, expected: set[str], field_name: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise AiReportValidationError(field_name, "필드 구성 오류")


def _business_info(value: Any) -> BusinessInfo:
    _expect_exact_keys(value, {"industry", "permit_numbers"}, "business_info")
    return BusinessInfo(_nullable_string(value["industry"], "business_info.industry"), _string_array(value["permit_numbers"], "business_info.permit_numbers"))


def _confirmed_violation(value: Any) -> ConfirmedViolation:
    _expect_exact_keys(value, {"mentioned", "content", "legal_basis", "evidence_document"}, "confirmed_violation")
    mentioned = value["mentioned"]
    if mentioned is not None and not isinstance(mentioned, bool):
        raise AiReportValidationError("confirmed_violation.mentioned", "boolean 또는 null 필요")
    return ConfirmedViolation(
        mentioned,
        _nullable_string(value["content"], "confirmed_violation.content"),
        _string_array(value["legal_basis"], "confirmed_violation.legal_basis"),
        _nullable_string(value["evidence_document"], "confirmed_violation.evidence_document"),
    )


def _planned_actions(value: Any) -> PlannedActions:
    _expect_exact_keys(value, {"administrative_disposition", "accusation"}, "planned_actions")
    return PlannedActions(
        _nullable_string(value["administrative_disposition"], "planned_actions.administrative_disposition"),
        _nullable_string(value["accusation"], "planned_actions.accusation"),
    )


def _evidence_items(value: Any) -> tuple[EvidenceItem, ...]:
    if not isinstance(value, list):
        raise AiReportValidationError("evidence", "배열 필요")
    items = []
    for index, item in enumerate(value):
        field_name = f"evidence[{index}]"
        _expect_exact_keys(item, {"field", "excerpt", "page_hint"}, field_name)
        field = item["field"]
        excerpt = item["excerpt"]
        if not isinstance(field, str) or not field.strip() or not isinstance(excerpt, str) or not excerpt.strip():
            raise AiReportValidationError(field_name, "field와 excerpt는 비어 있지 않은 문자열 필요")
        items.append(EvidenceItem(field.strip(), excerpt.strip(), _nullable_string(item["page_hint"], f"{field_name}.page_hint")))
    return tuple(items)


def _friendly_api_error(error: Exception) -> AiReportApiError:
    error_name = type(error).__name__.lower()
    message = str(error).lower()
    status_code = getattr(error, "status_code", None)
    if status_code == 401 or "authentication" in error_name or "api key" in message:
        return AiReportApiError("OpenAI API 인증에 실패했습니다. API 키 설정을 확인해 주세요.")
    if any(word in message for word in ("billing", "credit", "quota", "insufficient_quota", "usage limit")):
        return AiReportApiError("OpenAI API 사용 한도 또는 결제 상태를 확인해 주세요.")
    if status_code == 429 or "ratelimit" in error_name or "rate limit" in message:
        return AiReportApiError("OpenAI API 요청 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.")
    if "connection" in error_name or "network" in error_name or isinstance(error, OSError):
        return AiReportApiError("OpenAI API 연결에 실패했습니다. 네트워크 상태를 확인해 주세요.")
    return AiReportApiError("OpenAI API 호출 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")

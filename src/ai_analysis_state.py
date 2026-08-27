from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, MutableMapping
from dataclasses import asdict

from src.ai_report_extractor import AiReportResult


def ai_result_session_key(filename: str, text: str) -> str:
    digest = hashlib.sha256(f"{filename}\0{text}".encode("utf-8")).hexdigest()[:16]
    return f"ai_report_result_{digest}"


def ai_result_version_session_key(filename: str, text: str) -> str:
    digest = hashlib.sha256(f"{filename}\0{text}".encode("utf-8")).hexdigest()[:16]
    return f"ai_report_version_{digest}"


def ai_result_fingerprint(result: AiReportResult) -> str:
    payload = json.dumps(asdict(result), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_ai_result(state: MutableMapping[str, object], filename: str, text: str) -> AiReportResult | None:
    value = state.get(ai_result_session_key(filename, text))
    return value if isinstance(value, AiReportResult) else None


def get_ai_result_version(state: MutableMapping[str, object], filename: str, text: str) -> int | None:
    value = state.get(ai_result_version_session_key(filename, text))
    return value if isinstance(value, int) else None


def save_ai_result(state: MutableMapping[str, object], filename: str, text: str, result: AiReportResult) -> int:
    state[ai_result_session_key(filename, text)] = result
    version = (get_ai_result_version(state, filename, text) or 0) + 1
    state[ai_result_version_session_key(filename, text)] = version
    return version


def analyze_selected_pdf(
    state: MutableMapping[str, object],
    filename: str,
    text: str,
    analyzer: Callable[[str], AiReportResult],
) -> AiReportResult:
    """버튼으로 명시적으로 선택된 PDF 한 건만 분석하고 결과를 보관합니다."""
    result = analyzer(text)
    save_ai_result(state, filename, text, result)
    return result

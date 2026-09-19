"""PDF로 확인한 공개 기준의 조회·검색. 사건별 처분을 계산하거나 저장하지 않는다."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

STANDARDS_FILE = Path(__file__).resolve().parents[1] / 'data/reference/disposition_standards.json'


def _payload(path: Path = STANDARDS_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def load_disposition_standards(path: Path = STANDARDS_FILE) -> list[dict[str, Any]]:
    """호출마다 독립된 자료를 반환하여 호출자의 수정이 다른 조회에 전파되지 않는다."""
    return sorted(_payload(path)['standards'], key=lambda item: (item['priority'], item['id']))


def load_disposition_general_rules() -> list[dict[str, Any]]:
    return _payload()['general_rules']


def _text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for child in value.values() for text in _text_values(child)]
    if isinstance(value, list):
        return [text for child in value for text in _text_values(child)]
    return []


def disposition_search_text(item: dict[str, Any]) -> str:
    """UI와 후속 검색 서비스가 동일한 검색 범위를 사용한다."""
    return ' '.join(text for key in ('title', 'short_summary', 'keywords', 'category', 'legal_basis')
                    for text in _text_values(item.get(key))) + ' ' + ' '.join(
        text for variant in item['variants'] for key in ('title', 'conditions', 'legal_basis')
        for text in _text_values(variant.get(key)))


def _normalize(value: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value).lower())


def search_disposition_standards(query: str = '', category: str | None = None) -> list[dict[str, Any]]:
    terms = [_normalize(term) for term in query.split()]
    return [item for item in load_disposition_standards()
            if (not category or item['category'] == category)
            and all(term in _normalize(disposition_search_text(item)) for term in terms)]


def get_disposition_standard(standard_id: str) -> dict[str, Any] | None:
    return next((item for item in load_disposition_standards() if item['id'] == standard_id), None)


def search_disposition_question(question: str, limit: int = 3) -> list[dict[str, Any]]:
    """자연어의 등록 키워드·별칭으로 후보를 찾는다. 사실·위반 여부는 판단하지 않는다."""
    normalized = _normalize(question)
    exact_ids = {item['id'] for item in search_disposition_standards(question)} if question.strip() else set()
    ranked = []
    for item in load_disposition_standards():
        aliases = [term for term in item.get('question_aliases', []) if _normalize(term) in normalized]
        keywords = [term for term in item['keywords'] if len(term) >= 2 and _normalize(term) in normalized]
        score = 10 * len(aliases) + len(keywords) + (3 if item['id'] in exact_ids else 0)
        if score:
            # 조건 후보도 검색 순위를 제공하되, 제외조건까지 함께 전달한다.
            item['variants'] = sorted(item['variants'], key=lambda v: -sum(
                _normalize(term) in normalized for term in v.get('question_aliases', [])))
            ranked.append((score, item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]['priority']))
    return [item for _, item in ranked[:limit]]

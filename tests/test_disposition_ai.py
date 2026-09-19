import json
from types import SimpleNamespace

import pandas as pd
import pytest

import web_app
from src import disposition_ai as ai
from src.ai_report_extractor import AiReportApiError
from src.disposition_standards import STANDARDS_FILE, load_disposition_standards, search_disposition_question
from tests.test_web_app import make_client


class MockResponses:
    def __init__(self, ref='DS-03|16)다)(2):retention', status='needs_more_information', fail=False):
        self.ref = ref
        self.status = status
        self.fail = fail
        self.calls = []
        self.responses = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError('api-key-secret must not be returned')
        return SimpleNamespace(output_text=json.dumps({
            'result_status': self.status, 'condition_refs': [self.ref], 'missing_check_refs': [],
        }))


def sample_cases():
    return pd.DataFrame([{
        'company_id': f'PRIVATE-ID-{i}', 'company_name': '초비밀산업', 'address': '경기도 화성시 비밀로 123',
        'disposition_id': f'PRIVATE-DSP-{i}', 'phone': '010-1234-5678',
        'violation_content': '초비밀산업 담당자 홍비밀 010-1234-5678 경기도 화성시 비밀로 123 CCTV 영상정보 60일 보관 위반',
        'legal_basis': '초비밀산업 PRIVATE-ID 폐기물관리법 제25조제9항',
        'administrative_disposition': '영업정지 1개월 (초비밀산업 담당자 홍비밀)',
        'penalty': '개인 연락처 010-1234-5678', 'disposition_date': f'2026-09-{i+1:02}',
    } for i in range(7)])


def test_supplement_review_preserves_counts_and_links_all_six_documents():
    payload = json.loads(STANDARDS_FILE.read_text(encoding='utf-8'))
    review = payload['supplement_review']
    assert len(review['documents']) == 6
    assert not review['sanctions_changed'] and not review['fine_amounts_changed']
    items = load_disposition_standards()
    assert len(items) == 15 and sum(len(i['variants']) for i in items) == 33
    rules = [r for item in items for r in item.get('supporting_rules', [])]
    assert len(rules) == 12 and all(r['source']['page'] > 0 for r in rules)
    assert any('장애복구 후 10일' in r['text'] for r in rules)
    assert any('90일' in r['text'] and '배출자' in r['text'] for r in rules)
    assert any('2026-08-31' == r['source']['source_date'] for r in rules)
    assert any('시행' in r.get('applicability_note', '') for r in rules)


@pytest.mark.parametrize('question, first_id', [
    ('CCTV가 한 달치밖에 없어', 'DS-03'), ('올바로 안 했어', 'DS-02'),
    ('폐기물을 너무 많이 쌓아놨어', 'DS-01'), ('시설 바꿨는데 신고 안 했어', 'DS-04'),
    ('장부가 없어', 'DS-05'), ('처리시설 검사를 안 받았어요', 'DS-09'),
])
def test_natural_language_candidates(question, first_id):
    assert search_disposition_question(question)[0]['id'] == first_id


def test_cctv_condition_search_prioritizes_retention_over_missing_camera():
    candidates = search_disposition_question('CCTV 영상이 30일치밖에 없습니다.')
    assert candidates[0]['variants'][0]['id'] == '16)다)(2):retention'
    # 검색용 정렬이 저장된 대표조건을 변경하지 않는다.
    assert load_disposition_standards()[2]['variants'][0]['id'] == '16)다)(1)'


def test_no_match_skips_openai_even_with_injected_client():
    client = MockResponses()
    answer = ai.answer_disposition_question('점심 메뉴 추천해줘', pd.DataFrame(), client)
    assert answer['result_status'] == 'no_match' and not answer['matches']
    assert not client.calls


def test_ambiguous_storage_never_confirms_even_when_model_returns_matched():
    client = MockResponses('DS-01|16)가)(1)', status='matched')
    answer = ai.answer_disposition_question('폐기물을 너무 많이 쌓아놨어', pd.DataFrame(), client)
    assert answer['result_status'] == 'needs_more_information'
    assert answer['field_checks'] == ['허가상 허용보관량', '실제 보관량', '보관기간', '허가·승인된 보관장소', '누출·유출 여부 및 사업장 밖·토양·공공수역 해당 여부']


@pytest.mark.parametrize('question, ref, first_sanction', [
    ('CCTV가 한 달치밖에 없어', 'DS-03|16)다)(2):retention', '경고'),
    ('올바로 안 했어', 'DS-02|10)', '경고'),
    ('시설 바꿨는데 신고 안 했어', 'DS-04|18)다)', '경고'),
    ('장부가 없어', 'DS-05|27)', '경고'),
])
def test_grounded_mock_answers(question, ref, first_sanction):
    client = MockResponses(ref)
    answer = ai.answer_disposition_question(question, pd.DataFrame(), client)
    assert answer['matches'][0]['sanctions'][0] == first_sanction
    assert answer['matches'][0]['ref'] == ref
    call = client.calls[0]
    assert call['store'] is False and call['text']['format']['strict'] is True
    assert 'tools' not in call
    context = json.loads(call['input'])
    assert context['manuals'] and context['legal_references']
    assert 'question_signals' in context and 'question' not in context


def test_case_and_question_privacy_in_context_and_answer():
    question = '처음보는비밀업체 홍비밀 010-1234-5678 경기도 화성시 비밀로 123 PRIVATE-ID CCTV 영상이 30일치밖에 없습니다.'
    client = MockResponses()
    answer = ai.answer_disposition_question(question, sample_cases(), client)
    context = json.loads(client.calls[0]['input'])
    assert len(context['similar_cases']) == 3
    assert context['similar_cases'][0]['disposition_date'] == '2026-09-07'
    assert all(set(c) == {'violation_content','legal_basis','administrative_disposition','disposition_date'} for c in context['similar_cases'])
    serialized = json.dumps(context, ensure_ascii=False) + json.dumps(answer, ensure_ascii=False)
    for private in ('처음보는비밀업체', '초비밀산업', '홍비밀', '010-1234-5678', '비밀로', 'PRIVATE-ID', 'PRIVATE-DSP', 'company_id', 'company_name', 'address'):
        assert private not in serialized
    assert '30일' in serialized and '영업정지 1개월' in serialized


@pytest.mark.parametrize('payload', [
    {'result_status':'matched','condition_refs':['DS-99|invented'],'missing_check_refs':[]},
    {'result_status':'matched','condition_refs':[],'missing_check_refs':[]},
    {'result_status':'matched','condition_refs':['DS-03|16)다)(1)'],'missing_check_refs':[], 'fine':99999},
    {'result_status':'no_match','condition_refs':['DS-03|16)다)(1)'],'missing_check_refs':[]},
    {'result_status':'confirmed','condition_refs':['DS-03|16)다)(1)'],'missing_check_refs':[]},
])
def test_invalid_or_unretrieved_output_is_rejected(payload):
    client = MockResponses()
    client.create = lambda **_: SimpleNamespace(output_text=json.dumps(payload))
    with pytest.raises(AiReportApiError, match='아래 행정처분 기준'):
        ai.answer_disposition_question('CCTV 설치 안 했어', pd.DataFrame(), client)


def test_refusal_and_api_error_are_safe():
    client = MockResponses()
    client.create = lambda **_: SimpleNamespace(output_text='')
    for candidate in (client, MockResponses(fail=True)):
        with pytest.raises(AiReportApiError) as error:
            ai.answer_disposition_question('CCTV', pd.DataFrame(), candidate)
        assert str(error.value) == ai.AI_UNAVAILABLE


def test_route_no_key_preserves_static_guide(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(ai, '_shared_client', lambda: pytest.fail('키 없이 클라이언트를 생성하면 안 됨'))
    client, _ = make_client()
    response = client.post('/inspection-guide/ai', json={'question':'CCTV'})
    assert response.status_code == 503 and response.json()['error'] == ai.AI_UNAVAILABLE
    page = client.get('/inspection-guide?tab=standards')
    assert page.status_code == 200 and page.text.count('data-standard-id=') == 15
    assert 'id="guide-ai-result" aria-live="polite" hidden' in page.text
    assert ai.AI_UNAVAILABLE in page.text


@pytest.mark.parametrize('backend', ['local', 'supabase'])
def test_route_returns_one_result_and_keeps_static_ui(monkeypatch, backend):
    monkeypatch.setenv('OPENAI_API_KEY', 'mock-only')
    monkeypatch.setattr(web_app, 'DATA_BACKEND', backend)
    monkeypatch.setattr(ai, '_shared_client', lambda: MockResponses())
    client, _ = make_client()
    result = client.post('/inspection-guide/ai', json={'question':'CCTV 영상이 30일치밖에 없습니다.'})
    assert result.status_code == 200
    html = result.json()['html']
    assert html.count('guide-ai-result-card') == 1
    assert '영상정보 60일 저장·보관 미준수' in html and '영업정지 6개월' in html
    assert 'guide-ai-fine' not in html
    page = client.get('/inspection-guide?tab=standards')
    assert page.text.count('data-standard-id=') == 15
    assert 'guide-ai-result-card' not in page.text


def test_route_api_error_and_input_limits(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'mock-only')
    monkeypatch.setattr(ai, '_shared_client', lambda: MockResponses(fail=True))
    client, _ = make_client()
    response = client.post('/inspection-guide/ai', json={'question':'CCTV'})
    assert response.status_code == 503 and response.json() == {'error':ai.AI_UNAVAILABLE}
    assert 'api-key-secret' not in response.text
    assert client.post('/inspection-guide/ai', json={'question':'가'*1001}).status_code == 422
    assert client.get('/inspection-guide?tab=standards').status_code == 200


def test_route_no_match_and_fines(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'mock-only')
    client, _ = make_client()
    mock = MockResponses('DS-04|18)다)')
    monkeypatch.setattr(ai, '_shared_client', lambda: mock)
    response = client.post('/inspection-guide/ai', json={'question':'날씨 알려줘'})
    assert response.json()['result_status'] == 'no_match' and not mock.calls
    response = client.post('/inspection-guide/ai', json={'question':'변경신고 안 했어'})
    assert '관련 과태료' in response.json()['html']
    assert '300만원' in response.json()['html']

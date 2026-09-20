from types import SimpleNamespace
import pytest
from app.services.usage_service import normalize_usage, price_usage, pricing_snapshot, metered_call, usage_summary
from app.agent import session_store
from app.persistence.sqlite_store import SQLiteSessionStore
from app.models import SubmissionRequest


def test_native_thinking_is_added_and_langchain_thinking_is_not_doubled():
    native = normalize_usage(SimpleNamespace(usage_metadata={'prompt_token_count': 100, 'candidates_token_count': 200, 'thoughts_token_count': 50, 'cached_content_token_count': 30}))
    lc = normalize_usage(SimpleNamespace(usage_metadata={'input_tokens': 100, 'output_tokens': 250, 'output_token_details': {'reasoning': 50}, 'input_token_details': {'cache_read': 30}}))
    assert native['output_tokens'] == lc['output_tokens'] == 250
    assert native['cached_tokens'] == lc['cached_tokens'] == 30
    assert price_usage(native, pricing_snapshot('gemini-3.8-flash')) == pytest.approx((70*.75+30*.075+250*3.75)/1e6)


def test_image_and_text_output_have_distinct_prices():
    usage = normalize_usage(SimpleNamespace(usage_metadata={'prompt_token_count': 100, 'candidates_token_count': 1685,
        'thoughts_token_count': 20, 'candidates_tokens_details': [{'modality': 'IMAGE', 'token_count': 1680}, {'modality': 'TEXT', 'token_count': 5}]}))
    assert price_usage(usage, pricing_snapshot('gemini-3.1-flash-image')) == pytest.approx((100*.5+25*3+1680*60)/1e6)
    usage['output_modalities_reported'] = False
    assert price_usage(usage, pricing_snapshot('gemini-3.1-flash-image')) is None


def test_unknown_usage_and_model_are_not_fabricated_as_zero():
    assert normalize_usage(SimpleNamespace()) is None
    assert pricing_snapshot('unknown-model') is None
    assert price_usage(None, pricing_snapshot('gemini-3.8-flash')) is None
    assert normalize_usage(SimpleNamespace(usage_metadata={'input_tokens': 12})) is None


def test_long_context_threshold_is_per_request():
    assert pricing_snapshot('gemini-3.1-pro-preview', 200_000)['rates']['input'] == 2
    assert pricing_snapshot('gemini-3.1-pro-preview', 200_001)['rates']['input'] == 4


@pytest.mark.asyncio
async def test_failed_attempts_and_mixed_models_remain_in_ledger(tmp_path, monkeypatch):
    store = SQLiteSessionStore(tmp_path / 'db.sqlite3')
    store.create_session('book', SubmissionRequest(plot='Trama', llm_model='gemini-3.8-flash'), [])
    monkeypatch.setattr(session_store, '_session_store', store)
    async def success():
        return SimpleNamespace(usage_metadata={'input_tokens': 1000, 'output_tokens': 1000})
    for model in ['gemini-3.8-flash', 'gemini-3.5-flash-lite']:
        await metered_call(success, session_id='book', model=model, phase='draft')
    async def timeout():
        raise TimeoutError()
    with pytest.raises(TimeoutError):
        await metered_call(timeout, session_id='book', model='gemini-3.8-flash', phase='draft')
    events = store.usage_events('book')
    report = usage_summary(store.get_session('book'), events)
    assert report['calls'] == 3 and report['unquantified_calls'] == 1
    assert not report['coverage_complete']
    assert report['cost_usd'] == pytest.approx(.0045+.0028)
    assert events[0]['pricing']['verified_at'] == '2026-09-20'


@pytest.mark.asyncio
async def test_semantically_rejected_response_is_still_charged(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    from app.llm import invoke_chat_model
    store = SQLiteSessionStore(tmp_path / 'db.sqlite3')
    store.create_session('book', SubmissionRequest(plot='Trama', llm_model='gemini-3.8-flash'), [])
    monkeypatch.setattr(session_store, '_session_store', store)
    response = SimpleNamespace(content='Testo inutilizzabile', usage_metadata={'input_tokens': 1000, 'output_tokens': 1000})
    llm = SimpleNamespace(ainvoke=AsyncMock(return_value=response))
    def reject(text):
        raise ValueError('Contenuto troppo breve')
    with pytest.raises(ValueError):
        await invoke_chat_model(llm=llm, messages=[], model_name='gemini-3.8-flash', stage='chapters',
            request_label='invalid', session_id='book', max_retries=1, response_validator=reject)
    assert store.usage_events('book')[0]['cost_usd'] == pytest.approx(.0045)


@pytest.mark.asyncio
@pytest.mark.parametrize('failed', [False, True])
async def test_question_endpoint_persists_session_before_metered_call(tmp_path, monkeypatch, failed):
    from app.api.routers import questions
    from app.models import QuestionGenerationRequest, QuestionsResponse
    from fastapi import HTTPException
    store = SQLiteSessionStore(tmp_path / 'db.sqlite3')
    monkeypatch.setattr(session_store, '_session_store', store)
    async def generate(form, api_key=None, session_id=None):
        assert store.get_session(session_id) is not None
        async def provider():
            if failed:
                raise TimeoutError('provider timeout')
            return SimpleNamespace(usage_metadata={'input_tokens': 1000, 'output_tokens': 1000})
        await metered_call(provider, session_id=session_id, model='gemini-3.8-flash', phase='questions')
        return QuestionsResponse(success=True, session_id=session_id, questions=[]), {
            'input_tokens': 1000, 'output_tokens': 1000, 'model': 'gemini-3.8-flash'}
    monkeypatch.setattr(questions, 'generate_questions', generate)
    request = QuestionGenerationRequest(form_data=SubmissionRequest(plot='Trama', llm_model='gemini-3.8-flash'))
    if failed:
        with pytest.raises(HTTPException):
            await questions.generate_questions_endpoint(request)
    else:
        await questions.generate_questions_endpoint(request)
    saved, = store.get_all_sessions().values()
    event, = store.usage_events(saved.session_id)
    assert event['status'] == ('unknown' if failed else 'measured')
    report = usage_summary(saved, [event])
    assert report['coverage_complete'] is not failed
    assert report['cost_usd'] == (None if failed else pytest.approx(.0045))


def test_old_questions_without_ledger_prevent_complete_cost_claim():
    session = SimpleNamespace(token_usage={'questions': {'input_tokens': 270, 'output_tokens': 1243}})
    events = [{'phase': 'draft', 'cost_usd': .02, 'usd_to_eur': .92}]
    report = usage_summary(session, events)
    assert not report['coverage_complete'] and report['historical_unverifiable']
    session.token_usage['questions'] = {'input_tokens': 0, 'output_tokens': 0, 'model': 'skipped'}
    assert usage_summary(session, events)['coverage_complete']

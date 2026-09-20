import pytest
import json
from pydantic import ValidationError
from langchain_core.output_parsers import PydanticOutputParser
from app.agent.narrative_memory import ChapterMemory, Fact, Contradiction, grounded_payload, relevant_facts, merge_chapter_memory, content_hash


def fact(**kwargs):
    return {'id': 'old', 'subject': 'Anna', 'predicate': 'conosce', 'value': 'il codice', 'kind': 'knowledge',
            'certainty': 'explicit', 'evidence': 'Anna conosce il codice.', 'section_index': 0, **kwargs}


def test_distant_entity_facts_survive_recent_window():
    memory = {'facts': [fact()] + [fact(id=str(i), subject='Altri', section_index=i) for i in range(1, 80)]}
    selected = relevant_facts(memory, 'Anna ritorna al laboratorio', 80, limit=5)
    assert selected[0]['id'] == 'old'


def test_superseded_states_are_not_presented_as_current():
    memory = {'facts': [fact(), fact(id='new', value='il nuovo codice', section_index=1, supersedes=['old'])]}
    assert [f['id'] for f in relevant_facts(memory, 'Anna', 2)] == ['new']
    assert [f['id'] for f in relevant_facts(memory, 'Anna', 1)] == ['old']


def test_fabricated_evidence_and_inferred_contradictions_are_rejected():
    payload = ChapterMemory(facts=[Fact(subject='Anna', predicate='sa', value='il codice', kind='knowledge', evidence='Una frase inventata.')])
    with pytest.raises(ValueError, match='testualmente'):
        grounded_payload(payload, 'Anna conosce il codice.', [])
    payload = ChapterMemory(contradictions=[Contradiction(fact_id='old', evidence='Anna non sa nulla.', explanation='Non sa il codice')])
    with pytest.raises(ValueError, match='deduzione'):
        grounded_payload(payload, 'Anna non sa nulla.', [fact(certainty='inferred')])


def test_saved_evidence_offsets_and_revisions_are_precise():
    chapter = {'title': 'Uno', 'section_index': 0, 'content': 'Inizia qui. Anna conosce il codice. Fine.'}
    payload = ChapterMemory(facts=[Fact(subject='Anna', predicate='sa', value='il codice', kind='knowledge', evidence='Anna conosce il codice.')])
    memory = merge_chapter_memory({'facts': [fact(section_index=3)], 'checks': [], 'chapters': {'3': 'stale'}}, payload, chapter)
    saved = memory['facts'][0]
    assert chapter['content'][saved['start']:saved['end']] == saved['evidence']
    assert memory['chapters'] == {'0': content_hash(chapter['content'])}
    assert len(memory['facts']) == 1


def test_memory_wire_schema_is_simple_but_response_bounds_are_enforced():
    schema = json.dumps(ChapterMemory.model_json_schema())
    for unsupported in ('maxItems', 'minLength', 'maxLength', 'default'):
        assert unsupported not in schema
    assert 'knowledge' in schema and 'evidence' in schema
    parser = PydanticOutputParser(pydantic_object=ChapterMemory)
    valid = dict(subject='Anna', predicate='sa', value='il codice', kind='knowledge', evidence='Anna sa il codice.')
    assert len(parser.parse(json.dumps({'facts': [valid]})).facts) == 1
    with pytest.raises(Exception, match='at most 40'):
        parser.parse(json.dumps({'facts': [valid] * 41}))
    with pytest.raises(ValidationError):
        ChapterMemory(facts=[valid | {'subject': 'x' * 121}])


def test_formatted_evidence_is_anchored_to_original_source():
    text = '«Anna  conosce il *codice*». Poi parte.'
    payload = ChapterMemory(facts=[Fact(subject='Anna', predicate='sa', value='codice', kind='knowledge', evidence='Anna conosce il codice.')])
    grounded = grounded_payload(payload, text, [])
    assert grounded.facts[0].evidence == 'Anna  conosce il *codice*».'
    saved = merge_chapter_memory({}, grounded, {'section_index': 0, 'title': 'Uno', 'content': text})['facts'][0]
    assert text[saved['start']:saved['end']] == saved['evidence']


@pytest.mark.parametrize('evidence', ['Anna conosce il codice.', 'Anna non conosce il codice 22.'])
def test_evidence_never_fuzzy_matches_changed_words_or_numbers(evidence):
    payload = ChapterMemory(facts=[Fact(subject='Anna', predicate='sa', value='codice', kind='knowledge', evidence=evidence)])
    with pytest.raises(ValueError, match='testualmente'):
        grounded_payload(payload, 'Anna non conosce il codice 12.', [])


@pytest.mark.asyncio
async def test_corrective_revision_invalidates_exports_and_commits_new_evidence(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    from app.agent import narrative_memory
    from app.persistence.sqlite_store import SQLiteSessionStore
    from app.models import SubmissionRequest
    store = SQLiteSessionStore(tmp_path / 'db.sqlite3')
    store.create_session('book', SubmissionRequest(plot='Trama', llm_model='gemini-3.8-flash'), [])
    store.update_book_chapter('book', 'Primo', 'Anna non sa nulla. ' * 200, 0)
    session = store.get_session('book')
    session.pdf_path = 'stale.pdf'
    session.literary_critique = {'summary': 'Vecchia valutazione'}
    store.save_session(session)
    conflict = ChapterMemory(contradictions=[Contradiction(fact_id='old', evidence='Anna non sa nulla.', explanation='Contraddizione')])
    corrected = 'Anna conosce il codice. ' * 200
    monkeypatch.setattr(narrative_memory, 'extract_chapter_memory', AsyncMock(side_effect=[conflict, ChapterMemory()]))
    monkeypatch.setattr(narrative_memory, 'build_google_chat_model', lambda **kwargs: object())
    monkeypatch.setattr(narrative_memory, 'invoke_chat_model', AsyncMock(return_value=(corrected, {})))
    await narrative_memory.ensure_narrative_memory(store, store.get_session('book'))
    saved = store.get_session('book')
    assert saved.pdf_path is None and saved.literary_critique is None
    assert saved.narrative_memory['chapters']['0'] == content_hash(corrected.strip())
    assert len(store.chapter_revisions('book', 0)) == 2

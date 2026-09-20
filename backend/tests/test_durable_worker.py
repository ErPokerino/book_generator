import asyncio
from unittest.mock import AsyncMock
import pytest
from app.models import SubmissionRequest
from app.persistence.sqlite_store import SQLiteSessionStore
from app.services.durable_worker import DurableWorker, dispatch_job
from app.services.process_job_service import begin_process_job_async, mark_process_completed_async


@pytest.fixture
def store(tmp_path):
    value = SQLiteSessionStore(tmp_path / 'db.sqlite3')
    value.create_session('book', SubmissionRequest(plot='Trama', llm_model='gemini-3.8-flash'), [])
    return value


@pytest.mark.asyncio
async def test_queued_job_survives_store_restart(store):
    await begin_process_job_async(store, 'book', 'book', total_steps=2)
    restarted = SQLiteSessionStore(store.db_path)
    async def handler(job, repo):
        repo.update_book_chapter('book', 'Primo', 'Salvato', 0)
        await mark_process_completed_async(repo, 'book', 'book', is_complete=True)
    assert await DurableWorker(restarted, handler).run_once()
    assert restarted.list_jobs('book')[0]['status'] == 'completed'
    assert restarted.get_session('book').book_chapters[0]['content'] == 'Salvato'
    assert not await DurableWorker(store, handler).run_once()


@pytest.mark.asyncio
async def test_shutdown_requeues_and_second_worker_resumes(store):
    await begin_process_job_async(store, 'book', 'book', total_steps=2)
    started = asyncio.Event()
    async def interrupted(job, repo):
        repo.update_book_chapter('book', 'Primo', 'Checkpoint', 0)
        started.set()
        await asyncio.Future()
    task = asyncio.create_task(DurableWorker(store, interrupted).run_once())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert store.list_jobs('book')[0]['status'] == 'pending'
    async def resumed(job, repo):
        assert job['attempt'] == 2
        assert len(repo.get_session('book').book_chapters) == 1
        await mark_process_completed_async(repo, 'book', 'book', is_complete=True)
    await DurableWorker(store, resumed).run_once()
    assert store.list_jobs('book')[0]['status'] == 'completed'


@pytest.mark.asyncio
async def test_crash_recovery_dispatches_saved_book_to_resume(store, monkeypatch):
    from app.services import book_generation_service
    store.update_book_chapter('book', 'Primo', 'Checkpoint', 0)
    await begin_process_job_async(store, 'book', 'book', total_steps=2)
    resume = AsyncMock()
    monkeypatch.setattr(book_generation_service, 'background_resume_book_generation', resume)
    await dispatch_job({'session_id': 'book', 'kind': 'book', 'attempt': 2}, store)
    resume.assert_awaited_once()


@pytest.mark.asyncio
async def test_lost_lease_does_not_kill_the_worker(store, monkeypatch):
    await begin_process_job_async(store, 'book', 'book', total_steps=2)
    async def waiting(job, repo):
        await asyncio.Future()
    monkeypatch.setattr(store, 'heartbeat', lambda *args: False)
    worker = DurableWorker(store, waiting, heartbeat_seconds=.001)
    assert await asyncio.wait_for(worker.run_once(), timeout=2)
    assert store.list_jobs('book')[0]['status'] == 'pending'


@pytest.mark.asyncio
async def test_saved_outline_is_not_generated_again_after_crash(store, monkeypatch):
    from app.services import generation_service
    await begin_process_job_async(store, 'book', 'outline')
    store.update_outline('book', '## Capitolo 1: Il ritorno\nAnna torna.')
    generate = AsyncMock()
    monkeypatch.setattr(generation_service, 'background_generate_outline', generate)
    await dispatch_job({'session_id': 'book', 'kind': 'outline', 'attempt': 2}, store)
    generate.assert_not_awaited()
    assert store.get_session('book').outline_progress['status'] == 'completed'


@pytest.mark.asyncio
async def test_real_worker_resumes_book_and_commits_grounded_memory(store, monkeypatch):
    from app.agent import session_store, narrative_memory
    from app.agent.writer import book_orchestrator
    from app.services import book_generation_service
    from app.agent.narrative_memory import ChapterMemory, Fact
    monkeypatch.setattr(session_store, '_session_store', store)
    session = store.get_session('book')
    session.current_draft = 'Anna torna al paese.'
    session.current_outline = '## Capitolo 1: Il ritorno\nAnna torna.\n\n## Capitolo 2: Il ponte\nAnna attraversa.'
    session.validated = True
    store.save_session(session)
    text = 'Anna attraversa il ponte. ' * 200
    store.update_writing_progress('book', 0, 2)
    store.update_book_chapter('book', 'Il ritorno', text, 0)
    generate = AsyncMock(return_value=(text, {'input_tokens': 100, 'output_tokens': 100}))
    monkeypatch.setattr(book_orchestrator, 'generate_chapter', generate)
    extract = AsyncMock(return_value=ChapterMemory(facts=[Fact(subject='Anna', predicate='attraversa', value='il ponte', kind='location', evidence='Anna attraversa il ponte.')]))
    monkeypatch.setattr(narrative_memory, 'extract_chapter_memory', extract)
    monkeypatch.setattr(book_generation_service, '_generate_cover_artifact', AsyncMock())
    monkeypatch.setattr(book_generation_service, '_generate_critique_artifact', AsyncMock())
    await begin_process_job_async(store, 'book', 'book', total_steps=2)
    assert await DurableWorker(store).run_once()
    saved = store.get_session('book')
    assert store.list_jobs('book')[0]['status'] == 'completed'
    assert saved.writing_progress['is_complete']
    assert len(saved.book_chapters) == len(saved.narrative_memory['facts']) == 2
    assert generate.await_count == 1
    assert extract.await_count == 2

import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.models import SubmissionRequest
from app.agent.session_store import FileSessionStore
from app.persistence.sqlite_store import SQLiteSessionStore, ConcurrentUpdateError, job_lease
from app.agent.narrative_memory import content_hash


@pytest.fixture
def store(tmp_path):
    store = SQLiteSessionStore(tmp_path / 'test.sqlite3')
    store.create_session('book', SubmissionRequest(plot='Un racconto', llm_model='gemini-3.8-flash'), [])
    return store


def test_migration_is_idempotent_and_preserves_original(tmp_path):
    legacy = tmp_path / '.sessions.json'
    old = FileSessionStore(legacy)
    old.create_session('one', SubmissionRequest(plot='Un libro', llm_model='gemini-3.8-flash'), [])
    old.update_book_chapter('one', 'Primo', 'Testo originale', 0)
    original = legacy.read_bytes()
    db = tmp_path / 'test.sqlite3'
    migrated = SQLiteSessionStore(db, legacy)
    assert migrated.get_session('one').book_chapters[0]['content'] == 'Testo originale'
    migrated.edit_chapter('one', 0, 'Testo corretto', content_hash('Testo originale'))
    assert SQLiteSessionStore(db, legacy).get_session('one').book_chapters[0]['content'] == 'Testo corretto'
    assert legacy.read_bytes() == original == (tmp_path / '.sessions.json.pre-sqlite.bak').read_bytes()


def test_corrupt_migration_never_partially_imports(tmp_path):
    path = tmp_path / '.sessions.json'
    path.write_text('{invalid', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        SQLiteSessionStore(tmp_path / 'test.sqlite3', path)
    assert path.read_text() == '{invalid'
    with sqlite3.connect(tmp_path / 'test.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0


def test_detached_reads_merge_unrelated_fields_and_reject_conflicts(store):
    a, b = store.get_session('book'), store.get_session('book')
    a.current_title = 'Titolo'
    store.save_session(a)
    b.current_draft = 'Trama'
    store.save_session(b)
    assert store.get_session('book').current_title == 'Titolo'
    a.current_title = 'Altro'
    store.save_session(a)
    b.current_title = 'Conflitto'
    with pytest.raises(ConcurrentUpdateError):
        store.save_session(b)
    assert store.get_session('book').current_title == 'Altro'


def test_chapter_checkpoint_revision_and_rollback_are_atomic(store, monkeypatch):
    store.update_writing_progress('book', 0, 3)
    store.update_book_chapter('book', 'Primo', 'Uno', 0)
    assert store.get_session('book').writing_progress['current_step'] == 1
    write = store._write
    def fail_after_write(*args):
        write(*args)
        raise RuntimeError('disk failure')
    monkeypatch.setattr(store, '_write', fail_after_write)
    with pytest.raises(RuntimeError):
        store.update_book_chapter('book', 'Secondo', 'Due', 1)
    recovered = store.get_session('book')
    assert len(recovered.book_chapters) == 1
    assert recovered.writing_progress['current_step'] == 1
    assert not store.chapter_revisions('book', 1)


def test_atomic_duplicate_start_exclusive_claim_and_expired_fencing(store):
    def enqueue(_):
        return store.enqueue_job('book', 'book', {'status': 'pending'})[0]
    with ThreadPoolExecutor(2) as workers:
        assert sorted(workers.map(enqueue, range(2))) == [False, True]
    job = store.claim_job('first', lease_seconds=-1)
    replacement = store.claim_job('second')
    assert job['id'] == replacement['id']
    assert store.claim_job('third') is None
    assert not store.heartbeat(job['id'], 'first')
    token = job_lease.set((job['id'], 'first'))
    try:
        with pytest.raises(ConcurrentUpdateError):
            store.update_book_chapter('book', 'Wrong owner', 'Bad', 0)
    finally:
        job_lease.reset(token)


def test_editor_keeps_history_and_invalidates_dependent_memory(store):
    store.update_book_chapter('book', 'Primo', 'Originale', 0)
    session = store.get_session('book')
    session.narrative_memory = {'facts': [{'section_index': 0}, {'section_index': 1}], 'checks': [], 'chapters': {'0': 'old'}}
    session.pdf_path = 'cached.pdf'
    store.save_session(session)
    edited = store.edit_chapter('book', 0, 'Revisione', content_hash('Originale'))
    assert not edited.narrative_memory['facts']
    assert edited.pdf_path is None
    assert [r['content'] for r in store.chapter_revisions('book', 0)] == ['Revisione', 'Originale']
    with pytest.raises(ConcurrentUpdateError):
        store.edit_chapter('book', 0, 'Overwrite', content_hash('Originale'))


def test_active_job_blocks_edit_and_delete(store):
    store.update_book_chapter('book', 'Primo', 'Originale', 0)
    store.enqueue_job('book', 'book', {'status': 'pending'})
    with pytest.raises(ConcurrentUpdateError):
        store.edit_chapter('book', 0, 'Revisione', content_hash('Originale'))
    with pytest.raises(ConcurrentUpdateError):
        store.delete_session('book')


def test_removed_and_readded_chapter_preserves_revision_sequence(store):
    store.update_book_chapter('book', 'Primo', 'Originale', 0)
    session = store.get_session('book')
    session.book_chapters = []
    store.save_session(session)
    store.update_book_chapter('book', 'Primo', 'Nuovo', 0)
    assert [r['revision'] for r in store.chapter_revisions('book', 0)] == [2, 1]


def test_consistent_backup_and_legacy_export(store, tmp_path):
    from app.persistence.archive import archive_database
    store.update_book_chapter('book', 'Primo', 'Originale', 0)
    store.edit_chapter('book', 0, 'Corretto', content_hash('Originale'))
    backup, exported = tmp_path / 'backup.sqlite3', tmp_path / 'export.json'
    archive_database(store.db_path, backup)
    assert len(SQLiteSessionStore(backup).chapter_revisions('book', 0)) == 2
    archive_database(store.db_path, exported, export_json=True)
    assert FileSessionStore(exported).get_session('book').book_chapters[0]['content'] == 'Corretto'
    with pytest.raises(FileExistsError):
        archive_database(store.db_path, backup)

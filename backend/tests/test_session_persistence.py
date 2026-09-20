import json
from unittest.mock import patch

import pytest

from app.agent.session_store import FileSessionStore


def test_failed_replace_preserves_disk_and_rolls_back_memory(tmp_path, submission_request):
    path = tmp_path / "sessions.json"
    store = FileSessionStore(path)
    store.create_session("book", submission_request, [])
    store.update_draft("book", "Bozza salvata")
    original = path.read_bytes()

    with patch("app.agent.session_store.os.replace", side_effect=PermissionError("Disco non disponibile")):
        with pytest.raises(PermissionError):
            store.update_draft("book", "Modifica non salvata")

    assert path.read_bytes() == original
    assert store.get_session("book").current_draft == "Bozza salvata"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("content", ['{broken', '{"bad": {"session_id": "bad"}}'])
def test_invalid_archive_is_never_loaded_as_empty(tmp_path, content):
    path = tmp_path / "sessions.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(RuntimeError, match="preservato"):
        FileSessionStore(path)
    assert path.read_text(encoding="utf-8") == content


def test_pause_and_resume_write_once_and_survive_reload(tmp_path, submission_request):
    path = tmp_path / "nested" / "sessions.json"
    store = FileSessionStore(path)
    store.create_session("book", submission_request, [])
    store.update_outline("book", "## Capitolo 1\nTrama", version=4)
    with patch.object(store, "_save_sessions", wraps=store._save_sessions) as save:
        store.pause_writing("book", 1, 3, "Capitolo 2", "Riprova")
        assert save.call_count == 1
        store.resume_writing("book")
        assert save.call_count == 2

    restored = FileSessionStore(path).get_session("book")
    assert restored.outline_version == 4
    assert restored.writing_progress["status"] == "running"
    assert restored.writing_progress["is_paused"] is False
    assert json.loads(path.read_text(encoding="utf-8"))["book"]["writing_progress"]["current_step"] == 1

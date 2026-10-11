from pathlib import Path
import runpy

import pytest

from app.essay.models import EssayBrief
from app.essay.store import EssayStore

import_archive = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/import-saggia.py"))["import_archive"]


def test_import_preserves_source_revisions_and_assets_and_pauses_jobs(tmp_path):
    source = tmp_path / "original"
    store = EssayStore(source / "saggia.sqlite3")
    session = store.create_session("E1", EssayBrief(topic="Le ragioni del confronto"))
    (source / "covers").mkdir()
    cover = source / "covers/E1.png"
    cover.write_bytes(b"cover-content")
    session.cover_image_path = str(cover)
    store.save_session(session)
    store.enqueue("E1", "questions")
    target = tmp_path / "integrated"
    assert import_archive(source, target) == 1
    imported = EssayStore(target / "saggia.sqlite3")
    migrated = imported.get_session("E1")
    assert migrated.cover_image_path == str(target / "covers/E1.png")
    assert (target / "covers/E1.png").read_bytes() == b"cover-content"
    assert imported.list_jobs("E1")[0]["status"] == "failed"
    assert migrated.questions_progress["status"] == "paused"
    assert store.list_jobs("E1")[0]["status"] == "pending"
    assert store.get_session("E1").cover_image_path == str(cover)
    with pytest.raises(ValueError, match="già dati"):
        import_archive(source, target)
    assert migrated.form_data.topic == "Le ragioni del confronto"

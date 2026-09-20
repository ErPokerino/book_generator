from io import BytesIO
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.agent.session_store import SessionData
from app.api.routers import book, files, library
from app.services import library_service, pdf_service, stats_service
from app.services.storage_service import StorageService


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    storage = StorageService()
    storage.local_base_path = tmp_path
    for module in (pdf_service, library_service, stats_service, files, library):
        monkeypatch.setattr(module, "get_storage_service", lambda: storage)
    return storage


def complete_session(session_id, submission_request):
    session = SessionData(session_id, submission_request, [])
    session.current_title = "La città 月"
    session.book_chapters = [{"title": "Capitolo 1", "content": "Una storia nella città. " * 30, "section_index": 0}]
    session.writing_progress = {"is_complete": True, "status": "completed"}
    return session


@pytest.mark.asyncio
async def test_pdf_download_preserves_unicode_and_separates_same_titles(local_storage, session_store, submission_request, monkeypatch):
    one = complete_session("book-one", submission_request)
    two = complete_session("book-two", submission_request)
    session_store.save_session(one)
    session_store.save_session(two)
    monkeypatch.setattr(book, "get_session_store", lambda: session_store)
    monkeypatch.setattr(library_service, "get_session_store", lambda: session_store)

    first = await book.generate_book_pdf(one.session_id)
    second = await book.generate_book_pdf(two.session_id)
    assert first.body.startswith(b"%PDF") and second.body.startswith(b"%PDF")
    assert len(PdfReader(BytesIO(first.body)).pages) >= 1
    assert one.pdf_filename != two.pdf_filename
    assert Path(one.pdf_path).exists() and Path(two.pdf_path).exists()
    assert "filename*=UTF-8''" in first.headers["content-disposition"]
    assert "%E6%9C%88" in first.headers["content-disposition"]
    assert stats_service._build_book_pdf_info(one, "complete")[1] == one.pdf_filename
    assert {entry.session_id for entry in library_service.scan_pdf_directory()} == {"book-one", "book-two"}


def test_file_routes_use_actual_storage_root_and_reject_traversal(local_storage):
    (local_storage.local_base_path / "secret.txt").write_text("private")
    local_storage.upload_file(b"%PDF-test", "books/prova.pdf")
    app = FastAPI()
    app.include_router(files.router)
    app.include_router(library.router)
    client = TestClient(app)
    assert client.get("/api/library/pdf/prova.pdf").content == b"%PDF-test"
    assert client.get("/api/files/books/prova.pdf").status_code == 200
    assert client.get("/api/files/books/..%5Csecret.txt").status_code == 403
    assert client.get("/api/library/pdf/..%5Csecret.txt").status_code in {403, 404}


def test_delete_artifacts_does_not_guess_by_title_or_remove_shared_files(local_storage, submission_request):
    one = complete_session("one", submission_request)
    two = complete_session("two", submission_request)
    one.pdf_path = local_storage.upload_file(b"one", "books/one.pdf")
    two.pdf_path = local_storage.upload_file(b"two", "books/two.pdf")
    shared_cover = local_storage.upload_file(b"cover", "covers/shared.png")
    one.cover_image_path = two.cover_image_path = shared_cover
    unrelated = local_storage.upload_file(b"legacy", "books/La_città.pdf")
    deleted = library_service.delete_session_artifacts(one, [one, two])
    assert deleted == ["one.pdf"]
    assert Path(two.pdf_path).exists() and Path(shared_cover).exists() and Path(unrelated).exists()

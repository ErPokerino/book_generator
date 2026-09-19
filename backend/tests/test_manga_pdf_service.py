from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image as PILImage

import app.services.pdf_service as pdf_service


class FakeStorage:
    def __init__(self, downloads=None, upload_result="gs://bucket/books/manga.pdf"):
        self.downloads = downloads or {}
        self.upload_result = upload_result
        self.upload_calls = []

    def download_file(self, path: str) -> bytes:
        result = self.downloads[path]
        if isinstance(result, Exception):
            raise result
        return result

    def upload_file(self, data: bytes, destination_path: str, content_type: str, user_id=None) -> str:
        self.upload_calls.append(
            {
                "data": data,
                "destination_path": destination_path,
                "content_type": content_type,
                "user_id": user_id,
            }
        )
        return self.upload_result


def _make_png_bytes(color: str) -> bytes:
    image = PILImage.new("RGB", (128, 192), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_download_manga_pdf_images_preserves_order_and_skips_optional_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(
        cover_image_path="cover.png",
        back_cover_image_path="back-cover.png",
        manga_pages=[
            {"page_number": 2, "image_path": "page-2.png"},
            {"page_number": 1, "image_path": "page-1.png"},
        ],
    )
    storage = FakeStorage(
        downloads={
            "cover.png": FileNotFoundError("missing cover"),
            "page-1.png": b"page-1",
            "page-2.png": b"page-2",
            "back-cover.png": b"back-cover",
        }
    )
    monkeypatch.setattr(pdf_service, "get_storage_service", lambda: storage)

    ordered_images = pdf_service._download_manga_pdf_images(session)

    assert ordered_images == [b"page-1", b"page-2", b"back-cover"]


def test_cache_manga_pdf_updates_session_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(
        user_id="user-1",
        pdf_path=None,
        pdf_filename=None,
        session_id="session-1",
        created_at=datetime.utcnow(),
    )
    storage = FakeStorage(upload_result="gs://bucket/books/generated.pdf")
    monkeypatch.setattr(pdf_service, "get_storage_service", lambda: storage)

    cached_path = pdf_service.cache_manga_pdf(session, b"%PDF-1.4", "generated.pdf")

    assert cached_path == "gs://bucket/books/generated.pdf"
    assert session.pdf_path == "gs://bucket/books/generated.pdf"
    assert session.pdf_filename == "generated.pdf"
    assert storage.upload_calls == [
        {
            "data": b"%PDF-1.4",
            "destination_path": "books/generated.pdf",
            "content_type": "application/pdf",
            "user_id": "user-1",
        }
    ]


def test_generate_manga_pdf_returns_pdf_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(
        session_id="session-1",
        current_title="Cronache di Akira",
        cover_image_path="cover.png",
        back_cover_image_path="back-cover.png",
        manga_pages=[
            {"page_number": 2, "image_path": "page-2.png"},
            {"page_number": 1, "image_path": "page-1.png"},
        ],
        created_at=datetime.utcnow(),
    )
    storage = FakeStorage(
        downloads={
            "cover.png": _make_png_bytes("red"),
            "page-1.png": _make_png_bytes("blue"),
            "page-2.png": _make_png_bytes("green"),
            "back-cover.png": _make_png_bytes("yellow"),
        }
    )
    monkeypatch.setattr(pdf_service, "get_storage_service", lambda: storage)

    pdf_bytes, filename = pdf_service.generate_manga_pdf(session)

    assert pdf_bytes.startswith(b"%PDF")
    assert filename.endswith(".pdf")

"""Servizio per la gestione della libreria e file system."""
from pathlib import Path
from datetime import datetime
from typing import Optional
from app.agent.session_store import SessionData, get_session_store
from app.services.pdf_service import get_model_abbreviation, calculate_page_count
from app.core.config import get_app_config
from app.services.storage_service import get_storage_service
import math


def scan_pdf_directory() -> list:
    """Scansiona la directory books/ e restituisce lista di PDF disponibili."""
    from app.models import PdfEntry
    
    books_dir = get_storage_service().local_base_path / "books"
    pdf_entries = []
    
    if not books_dir.exists():
        return pdf_entries
    
    session_store = get_session_store()
    
    for pdf_file in sorted(books_dir.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            # Prova a parsare il nome file: YYYY-MM-DD_g3p_TitoloLibro.pdf
            filename = pdf_file.name
            stem = pdf_file.stem
            
            # Estrai data (prima parte prima di _)
            parts = stem.split('_', 2)
            created_date = None
            if len(parts) >= 1:
                try:
                    created_date = datetime.strptime(parts[0], "%Y-%m-%d")
                except:
                    pass
            
            # Cerca session_id corrispondente (potrebbe essere nel nome o cercando per titolo)
            session_id = None
            title = None
            author = None
            
            # Prova a cercare nelle sessioni per matchare il PDF
            for sid, session in session_store.get_all_sessions().items():
                # Genera il nome file atteso per questa sessione
                if session.pdf_path and Path(session.pdf_path).resolve() == pdf_file.resolve():
                    session_id, title, author = sid, session.current_title, session.form_data.user_name
                    break
                if session.current_title:
                    date_prefix = session.created_at.strftime("%Y-%m-%d")
                    model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                    title_sanitized = "".join(c for c in session.current_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    title_sanitized = title_sanitized.replace(" ", "_")
                    expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                    
                    if filename == expected_filename:
                        session_id = sid
                        title = session.current_title
                        author = session.form_data.user_name
                        break
            
            # Se non trovato, prova a estrarre titolo dal nome file
            if not title and len(parts) >= 3:
                title = parts[2].replace('_', ' ')
            
            size_bytes = pdf_file.stat().st_size
            
            pdf_entries.append(PdfEntry(
                filename=filename,
                session_id=session_id,
                title=title,
                author=author,
                created_date=created_date,
                size_bytes=size_bytes,
            ))
        except Exception as e:
            print(f"[SCAN PDF] Errore nel processare {pdf_file.name}: {e}")
            continue
    
    return pdf_entries


def _artifact_paths(session: SessionData) -> set[Path]:
    """Solo file esplicitamente associati alla sessione; mai ricerche per titolo."""
    storage = get_storage_service()
    paths = [session.pdf_path, session.cover_image_path, session.back_cover_image_path]
    paths.extend(page.get("image_path") for page in session.manga_pages)
    return {storage._resolve_path(path).resolve() for path in paths if path}


def delete_session_artifacts(session: SessionData, sessions) -> list[str]:
    storage = get_storage_service()
    roots = [(storage.local_base_path / folder).resolve() for folder in ("books", "sessions", "covers", "manga")]
    shared = set()
    for other in sessions:
        if other.session_id != session.session_id:
            shared.update(_artifact_paths(other))
    deleted = []
    for path in _artifact_paths(session) - shared:
        if any(path.is_relative_to(root) for root in roots) and path.is_file():
            path.unlink()
            deleted.append(path.name)
    return deleted

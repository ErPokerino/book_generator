"""Servizio per la gestione della libreria e file system."""
from pathlib import Path
from datetime import datetime
from typing import Optional
from app.agent.session_store import SessionData, get_session_store
from app.services.pdf_service import get_model_abbreviation, calculate_page_count
from app.core.config import get_app_config
import math


def scan_pdf_directory() -> list:
    """Scansiona la directory books/ e restituisce lista di PDF disponibili."""
    from app.models import PdfEntry
    
    books_dir = Path(__file__).parent.parent.parent / "books"
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
            for sid, session in session_store._sessions.items():
                # Genera il nome file atteso per questa sessione
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

#!/usr/bin/env python3
"""
Script di migrazione per ottimizzare le performance della libreria.

Questo script aggiunge i campi pre-calcolati (total_pages, completed_chapters_count)
al writing_progress di tutti i libri completati che non li hanno ancora.

Questo evita di dover caricare book_chapters per ogni richiesta alla libreria.

Uso:
    cd backend
    uv run python scripts/migrate_library_performance.py
"""
import asyncio
import os
import sys
import math

# Aggiungi il path del backend per importare i moduli
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env"))

from app.agent.session_store import get_session_store
from app.services.pdf_service import calculate_page_count
from app.core.config import get_app_config


async def migrate_sessions():
    """Migra tutti i libri completati aggiungendo campi pre-calcolati."""
    session_store = get_session_store()
    
    # Connetti se è MongoSessionStore
    if hasattr(session_store, 'connect'):
        await session_store.connect()
    
    print("[MIGRAZIONE] Inizio migrazione per ottimizzazione performance libreria...")
    
    # Recupera tutte le sessioni (senza proiezione per avere tutti i dati)
    if hasattr(session_store, 'get_all_sessions'):
        all_sessions = await session_store.get_all_sessions()
    else:
        all_sessions = session_store._sessions
    
    print(f"[MIGRAZIONE] Trovate {len(all_sessions)} sessioni totali")
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    for session_id, session in all_sessions.items():
        try:
            # Verifica se è un libro completato
            if not session.writing_progress:
                skipped_count += 1
                continue
            
            if not session.writing_progress.get('is_complete', False):
                skipped_count += 1
                continue
            
            # Verifica se ha già i campi pre-calcolati
            has_total_pages = session.writing_progress.get('total_pages') is not None
            has_chapters_count = session.writing_progress.get('completed_chapters_count') is not None
            
            if has_total_pages and has_chapters_count:
                print(f"[MIGRAZIONE] {session_id}: già migrato, skip")
                skipped_count += 1
                continue
            
            # Calcola i valori
            if not session.book_chapters:
                print(f"[MIGRAZIONE] {session_id}: nessun capitolo trovato, skip")
                skipped_count += 1
                continue
            
            completed_chapters_count = len(session.book_chapters)
            
            # Calcola total_pages
            chapters_pages = sum(calculate_page_count(ch.get('content', '')) for ch in session.book_chapters)
            cover_pages = 1
            app_config = get_app_config()
            toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
            toc_pages = math.ceil(completed_chapters_count / toc_chapters_per_page) if completed_chapters_count else 0
            total_pages = chapters_pages + cover_pages + toc_pages
            
            # Aggiorna writing_progress
            session.writing_progress['total_pages'] = total_pages
            session.writing_progress['completed_chapters_count'] = completed_chapters_count
            
            # Salva la sessione
            if hasattr(session_store, 'save_session'):
                await session_store.save_session(session)
            elif hasattr(session_store, '_save_sessions'):
                session_store._save_sessions()
            
            print(f"[MIGRAZIONE] {session_id}: migrato - {total_pages} pagine, {completed_chapters_count} capitoli")
            updated_count += 1
            
        except Exception as e:
            print(f"[MIGRAZIONE] ERRORE per {session_id}: {e}")
            error_count += 1
    
    print(f"\n[MIGRAZIONE] Completata!")
    print(f"  - Aggiornate: {updated_count}")
    print(f"  - Saltate: {skipped_count}")
    print(f"  - Errori: {error_count}")
    
    # Disconnetti se necessario
    if hasattr(session_store, 'disconnect'):
        await session_store.disconnect()


if __name__ == "__main__":
    asyncio.run(migrate_sessions())

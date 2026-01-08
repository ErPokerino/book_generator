#!/usr/bin/env python3
"""
Script per eliminare tutti i libri generati con Gemini 2.5 Flash e Pro.
Esegue la stessa logica dell'endpoint /api/admin/books/gemini-2.5/delete
senza richiedere autenticazione.
"""
import asyncio
import sys
from pathlib import Path
from collections import defaultdict
from typing import Optional

# Aggiungi il path del backend al PYTHONPATH
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_all_sessions_async, delete_session_async
from app.services.storage_service import get_storage_service
from app.main import is_gemini_2_5, session_to_library_entry, get_model_abbreviation


async def delete_gemini_2_5_books(dry_run: bool = False):
    """
    Elimina tutti i libri generati con Gemini 2.5.
    
    Args:
        dry_run: Se True, simula l'eliminazione senza eliminare realmente
    """
    print("=" * 80)
    print("ELIMINAZIONE LIBRI GEMINI 2.5")
    print("=" * 80)
    if dry_run:
        print("[DRY RUN] MODALITA DRY RUN - Nessuna eliminazione verra eseguita")
    else:
        print("[ATTENZIONE] Questa operazione e IRREVERSIBILE!")
    print("=" * 80)
    print()
    
    try:
        # Inizializza session store e storage service
        session_store = get_session_store()
        storage_service = get_storage_service()
        
        # Se è MongoSessionStore, connetti
        if hasattr(session_store, 'connect'):
            await session_store.connect()
        
        # Ottieni tutte le sessioni
        print("[INFO] Caricamento sessioni...")
        all_sessions = await get_all_sessions_async(session_store, user_id=None)
        print(f"   Trovate {len(all_sessions)} sessioni totali")
        
        # Filtra sessioni con modelli 2.5
        gemini_2_5_sessions = {}
        for session_id, session in all_sessions.items():
            if session.form_data and is_gemini_2_5(session.form_data.llm_model):
                gemini_2_5_sessions[session_id] = session
        
        print(f"   Trovate {len(gemini_2_5_sessions)} sessioni con Gemini 2.5")
        print()
        
        if len(gemini_2_5_sessions) == 0:
            print("[OK] Nessun libro Gemini 2.5 trovato. Niente da eliminare.")
            return
        
        # Raggruppa per modello per statistiche
        by_model = defaultdict(int)
        for session in gemini_2_5_sessions.values():
            model = session.form_data.llm_model
            by_model[model] += 1
        
        print("[STATISTICHE] Libri Gemini 2.5:")
        for model, count in by_model.items():
            print(f"   - {model}: {count} libri")
        print()
        
        # Chiedi conferma se non è dry_run
        if not dry_run:
            response = input("[CONFERMA] Sei sicuro di voler eliminare TUTTI questi libri? (scrivi 'ELIMINA' per confermare): ")
            if response != "ELIMINA":
                print("[ANNULLATO] Operazione annullata.")
                return
        
        # Procedi con l'eliminazione
        deleted_sessions = 0
        deleted_pdfs = 0
        deleted_covers = 0
        errors = []
        details = []
        
        books_dir = backend_dir.parent / "books"
        
        print()
        print("[ELIMINAZIONE] Inizio eliminazione...")
        print()
        
        for idx, (session_id, session) in enumerate(gemini_2_5_sessions.items(), 1):
            try:
                entry = session_to_library_entry(session, skip_cost_calculation=True)
                print(f"[{idx}/{len(gemini_2_5_sessions)}] {entry.title} ({session.form_data.llm_model})")
                
                detail = {
                    "session_id": session_id,
                    "title": entry.title,
                    "model": session.form_data.llm_model,
                    "status": entry.status,
                    "pdf_deleted": False,
                    "cover_deleted": False,
                    "session_deleted": False,
                }
                
                if not dry_run:
                    # Elimina PDF
                    pdf_deleted = False
                    try:
                        if entry.pdf_path:
                            if entry.pdf_path.startswith("gs://"):
                                # Elimina da GCS
                                try:
                                    storage_service.delete_file(entry.pdf_path)
                                    pdf_deleted = True
                                    print(f"   [OK] PDF eliminato da GCS: {entry.pdf_path}")
                                except Exception as e:
                                    error_msg = f"Errore eliminazione PDF GCS {entry.pdf_path}: {e}"
                                    errors.append(error_msg)
                                    print(f"   [ERR] {error_msg}")
                            else:
                                # Elimina locale
                                pdf_path = Path(entry.pdf_path)
                                if pdf_path.exists():
                                    pdf_path.unlink()
                                    pdf_deleted = True
                                    print(f"   [OK] PDF eliminato: {pdf_path}")
                        elif entry.status == "complete" and books_dir.exists():
                            # Cerca PDF locale
                            date_prefix = session.created_at.strftime("%Y-%m-%d")
                            model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                            title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            title_sanitized = title_sanitized.replace(" ", "_")
                            if not title_sanitized:
                                title_sanitized = f"Libro_{session.session_id[:8]}"
                            expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                            expected_path = books_dir / expected_filename
                            
                            if expected_path.exists():
                                expected_path.unlink()
                                pdf_deleted = True
                                print(f"   [OK] PDF eliminato: {expected_path}")
                            else:
                                # Cerca qualsiasi PDF che potrebbe corrispondere
                                for pdf_file in books_dir.glob("*.pdf"):
                                    if session.session_id[:8] in pdf_file.stem or (title_sanitized and title_sanitized.lower() in pdf_file.stem.lower()):
                                        pdf_file.unlink()
                                        pdf_deleted = True
                                        print(f"   [OK] PDF eliminato (match parziale): {pdf_file}")
                                        break
                        
                        if pdf_deleted:
                            deleted_pdfs += 1
                            detail["pdf_deleted"] = True
                    except Exception as e:
                        error_msg = f"Errore eliminazione PDF per {entry.title}: {e}"
                        errors.append(error_msg)
                        print(f"   [ERR] {error_msg}")
                    
                    # Elimina copertina
                    cover_deleted = False
                    try:
                        if session.cover_image_path:
                            if session.cover_image_path.startswith("gs://"):
                                # Elimina da GCS
                                try:
                                    storage_service.delete_file(session.cover_image_path)
                                    cover_deleted = True
                                    print(f"   [OK] Copertina eliminata da GCS: {session.cover_image_path}")
                                except Exception as e:
                                    error_msg = f"Errore eliminazione copertina GCS {session.cover_image_path}: {e}"
                                    errors.append(error_msg)
                                    print(f"   [ERR] {error_msg}")
                            else:
                                # Elimina locale
                                cover_path = Path(session.cover_image_path)
                                if cover_path.exists():
                                    cover_path.unlink()
                                    cover_deleted = True
                                    print(f"   [OK] Copertina eliminata: {cover_path}")
                            
                            if cover_deleted:
                                deleted_covers += 1
                                detail["cover_deleted"] = True
                    except Exception as e:
                        error_msg = f"Errore eliminazione copertina per {entry.title}: {e}"
                        errors.append(error_msg)
                        print(f"   [ERR] {error_msg}")
                    
                    # Elimina sessione
                    if await delete_session_async(session_store, session_id):
                        deleted_sessions += 1
                        detail["session_deleted"] = True
                        print(f"   [OK] Sessione eliminata: {session_id}")
                    else:
                        error_msg = f"Errore eliminazione sessione {session_id}"
                        errors.append(error_msg)
                        print(f"   [ERR] {error_msg}")
                else:
                    # Dry run: simula eliminazione
                    detail["pdf_deleted"] = entry.pdf_path is not None or (entry.status == "complete" and books_dir.exists())
                    detail["cover_deleted"] = session.cover_image_path is not None
                    detail["session_deleted"] = True
                    print(f"   [DRY RUN] Verrebbe eliminato: PDF={detail['pdf_deleted']}, Cover={detail['cover_deleted']}, Session=True")
                
                details.append(detail)
            except Exception as e:
                error_msg = f"Errore durante eliminazione {session_id}: {e}"
                errors.append(error_msg)
                print(f"   ❌ {error_msg}")
                import traceback
                traceback.print_exc()
        
        # Riepilogo finale
        print()
        print("=" * 80)
        print("RIEPILOGO ELIMINAZIONE")
        print("=" * 80)
        print(f"[TOTALE] Libri trovati: {len(gemini_2_5_sessions)}")
        if not dry_run:
            print(f"[OK] Sessioni eliminate: {deleted_sessions}")
            print(f"[OK] PDF eliminati: {deleted_pdfs}")
            print(f"[OK] Copertine eliminate: {deleted_covers}")
        else:
            print(f"[SIMULAZIONE] PDF che verrebbero eliminati: {sum(1 for d in details if d['pdf_deleted'])}")
            print(f"[SIMULAZIONE] Copertine che verrebbero eliminate: {sum(1 for d in details if d['cover_deleted'])}")
            print(f"[SIMULAZIONE] Sessioni che verrebbero eliminate: {len(gemini_2_5_sessions)}")
        
        if errors:
            print()
            print(f"[ATTENZIONE] Errori riscontrati: {len(errors)}")
            for error in errors[:10]:  # Mostra solo i primi 10 errori
                print(f"   - {error}")
            if len(errors) > 10:
                print(f"   ... e altri {len(errors) - 10} errori")
        
        print("=" * 80)
        
        if not dry_run:
            print("[OK] Eliminazione completata!")
        else:
            print("[OK] Simulazione completata!")
        
    except Exception as e:
        print(f"[ERRORE FATALE] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Elimina tutti i libri generati con Gemini 2.5")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula l'eliminazione senza eliminare realmente"
    )
    
    args = parser.parse_args()
    
    asyncio.run(delete_gemini_2_5_books(dry_run=args.dry_run))

"""Router per gli endpoint amministrativi."""
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from app.models import UsersStats, UserBookCount
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_all_sessions_async, delete_session_async
from app.agent.user_store import get_user_store
from app.agent.book_share_store import get_book_share_store
from app.middleware.auth import require_admin
from app.services.stats_service import (
    get_cached_stats,
    set_cached_stats,
    session_to_library_entry,
    get_model_abbreviation,
)
from app.services.storage_service import get_storage_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


def is_gemini_2_5(model_name: Optional[str]) -> bool:
    """Verifica se un modello è una versione 2.5 di Gemini."""
    if not model_name:
        return False
    return "gemini-2.5" in model_name.lower()


@router.get("/users/stats", response_model=UsersStats)
async def get_users_stats_endpoint(
    current_user = Depends(require_admin),
):
    """Restituisce statistiche sugli utenti: totale utenti e conteggio libri per utente (solo admin)."""
    try:
        cache_key = "admin_users_stats"
        cached = get_cached_stats(cache_key)
        if cached is not None:
            if isinstance(cached, dict):
                return UsersStats(**cached)
            return cached
        
        session_store = get_session_store()
        user_store = get_user_store()
        
        if user_store.client is None or user_store.users_collection is None:
            await user_store.connect()
        
        try:
            all_users = await user_store.get_all_users(skip=0, limit=10000)
            total_users = len(all_users)
        except Exception as e:
            print(f"[USERS STATS] Errore nel recupero utenti: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Errore nel recupero degli utenti: {str(e)}"
            )
        
        books_per_user = defaultdict(int)
        
        mongo_uri = os.getenv("MONGODB_URI")
        if mongo_uri:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(mongo_uri)
            try:
                db = client["narrai"]
                sessions_collection = db["sessions"]
                
                pipeline = [
                    {"$match": {"user_id": {"$ne": None, "$exists": True}}},
                    {"$group": {
                        "_id": "$user_id",
                        "count": {"$sum": 1}
                    }}
                ]
                
                async for result in sessions_collection.aggregate(pipeline):
                    user_id = result["_id"]
                    count = result["count"]
                    books_per_user[user_id] = count
                
                print(f"[USERS STATS] Contati {sum(books_per_user.values())} libri totali da aggregazione MongoDB", file=sys.stderr)
            except Exception as e:
                print(f"[USERS STATS] Errore nell'aggregazione MongoDB: {e}")
                import traceback
                traceback.print_exc()
            finally:
                client.close()
        else:
            print(f"[USERS STATS] WARNING: MONGODB_URI non configurato, uso fallback")
            all_sessions = await get_all_sessions_async(session_store, user_id=None)
            for session in all_sessions.values():
                if session.user_id:
                    books_per_user[session.user_id] += 1
            print(f"[USERS STATS] Contati {len(all_sessions)} sessioni totali (fallback)")
        
        users_with_books = []
        for user in all_users:
            try:
                books_count = books_per_user.get(user.id, 0)
                users_with_books.append({
                    "user_id": str(user.id) if user.id else "N/A",
                    "name": str(user.name) if user.name else "N/A",
                    "email": str(user.email) if user.email else "N/A",
                    "books_count": int(books_count) if books_count else 0,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                })
            except Exception as e:
                print(f"[USERS STATS] Errore nel processare utente {getattr(user, 'id', 'unknown')}: {e}", file=sys.stderr)
                continue
        
        if "__unassigned__" in books_per_user:
            unassigned_count = books_per_user["__unassigned__"]
            print(f"[USERS STATS] Sessioni senza user_id (non assegnate): {unassigned_count}")
        
        users_with_books.sort(key=lambda x: x["books_count"], reverse=True)
        
        try:
            result = UsersStats(
                total_users=int(total_users),
                users_with_books=[UserBookCount(**user) for user in users_with_books],
            )
        except Exception as e:
            print(f"[USERS STATS] Errore nella creazione UsersStats: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Errore nella serializzazione dei dati: {str(e)}"
            )
        
        try:
            set_cached_stats(cache_key, result.model_dump())
        except Exception as e:
            print(f"[USERS STATS] Errore nel salvare cache: {e}", file=sys.stderr)
        
        return result
    except HTTPException:
        # Mantieni status code originali (es. 401/403) invece di convertirli in 500
        raise
    except Exception as e:
        print(f"[USERS STATS] Errore nel calcolo statistiche utenti: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel calcolo delle statistiche utenti: {str(e)}"
        )


@router.delete("/users/{email}")
async def delete_user_endpoint(
    email: str,
    current_user = Depends(require_admin),
):
    """Elimina un utente per email (solo admin). Elimina anche i libri non condivisi."""
    try:
        user_store = get_user_store()

        if user_store.client is None or user_store.users_collection is None:
            await user_store.connect()

        # Non permettere di eliminare se stessi
        if current_user.email.lower() == email.lower():
            raise HTTPException(
                status_code=400,
                detail="Non puoi eliminare il tuo stesso account"
            )

        # 1. Trova l'utente per ottenere l'ID
        user = await user_store.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"Utente con email {email} non trovato"
            )

        # 2. Trova tutti i libri dell'utente
        session_store = get_session_store()
        user_sessions = await get_all_sessions_async(session_store, user_id=user.id)
        
        # 3. Per ogni libro, verifica se è condiviso e elimina solo quelli non condivisi
        book_share_store = get_book_share_store()
        await book_share_store.connect()
        
        deleted_books = 0
        kept_books = 0
        
        for session_id in user_sessions.keys():
            shares = await book_share_store.get_shares_by_book(session_id)
            if not shares:  # Nessuna condivisione attiva
                await delete_session_async(session_store, session_id)
                deleted_books += 1
            else:
                kept_books += 1
                print(f"[DELETE USER] Libro {session_id} mantenuto: condiviso con {len(shares)} utenti", file=sys.stderr)

        # 4. Elimina l'utente
        deleted = await user_store.delete_user_by_email(email)

        if not deleted:
            raise HTTPException(
                status_code=500,
                detail=f"Errore nell'eliminazione dell'utente {email}"
            )

        # Invalida la cache delle statistiche utenti
        set_cached_stats("admin_users_stats", None)

        message = f"Utente {email} eliminato con successo. Libri eliminati: {deleted_books}"
        if kept_books > 0:
            message += f", libri mantenuti (condivisi): {kept_books}"
        
        return {"success": True, "message": message, "deleted_books": deleted_books, "kept_books": kept_books}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[DELETE USER] Errore: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'eliminazione dell'utente: {str(e)}"
        )


@router.get("/books/gemini-2.5/stats")
async def get_gemini_2_5_stats_endpoint(
    current_user = Depends(require_admin),
):
    """Restituisce statistiche sui libri generati con Gemini 2.5 (solo admin)."""
    try:
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store, user_id=None)
        
        gemini_2_5_sessions = {}
        for session_id, session in all_sessions.items():
            if session.form_data and is_gemini_2_5(session.form_data.llm_model):
                gemini_2_5_sessions[session_id] = session
        
        by_model = defaultdict(int)
        by_status = defaultdict(int)
        with_pdf = 0
        with_cover = 0
        books_list = []
        
        books_dir = Path(__file__).parent.parent.parent / "books"
        
        for session_id, session in gemini_2_5_sessions.items():
            model = session.form_data.llm_model
            by_model[model] += 1
            
            try:
                entry = session_to_library_entry(session, skip_cost_calculation=True)
                status = entry.status
                by_status[status] += 1
                
                has_pdf = False
                if entry.pdf_filename:
                    has_pdf = True
                elif status == "complete" and books_dir.exists():
                    date_prefix = session.created_at.strftime("%Y-%m-%d")
                    model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                    title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    title_sanitized = title_sanitized.replace(" ", "_")
                    if not title_sanitized:
                        title_sanitized = f"Libro_{session.session_id[:8]}"
                    expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                    expected_path = books_dir / expected_filename
                    if expected_path.exists():
                        has_pdf = True
                    elif entry.pdf_path and entry.pdf_path.startswith("gs://"):
                        has_pdf = True
                
                if has_pdf:
                    with_pdf += 1
                
                has_cover = False
                if session.cover_image_path:
                    if session.cover_image_path.startswith("gs://"):
                        has_cover = True
                    else:
                        cover_path = Path(session.cover_image_path)
                        if cover_path.exists():
                            has_cover = True
                
                if has_cover:
                    with_cover += 1
                
                books_list.append({
                    "session_id": session_id,
                    "title": entry.title,
                    "model": model,
                    "status": status,
                    "has_pdf": has_pdf,
                    "has_cover": has_cover,
                    "created_at": session.created_at.isoformat(),
                })
            except Exception as e:
                print(f"[GEMINI-2.5-STATS] Errore nel processare sessione {session_id}: {e}")
                continue
        
        return {
            "total_books": len(gemini_2_5_sessions),
            "by_model": dict(by_model),
            "by_status": dict(by_status),
            "with_pdf": with_pdf,
            "with_cover": with_cover,
            "books": books_list,
        }
    
    except Exception as e:
        print(f"[GEMINI-2.5-STATS] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel calcolo delle statistiche Gemini 2.5: {str(e)}"
        )


@router.get("/books/gemini-2.5/preview")
async def preview_gemini_2_5_books_endpoint(
    current_user = Depends(require_admin),
):
    """Restituisce lista dettagliata di tutti i libri Gemini 2.5 da eliminare (solo admin)."""
    try:
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store, user_id=None)
        
        gemini_2_5_books = []
        books_dir = Path(__file__).parent.parent.parent / "books"
        
        for session_id, session in all_sessions.items():
            if session.form_data and is_gemini_2_5(session.form_data.llm_model):
                try:
                    entry = session_to_library_entry(session, skip_cost_calculation=True)
                    
                    pdf_path = None
                    cover_path = None
                    
                    if entry.pdf_path:
                        pdf_path = entry.pdf_path
                    elif entry.status == "complete" and books_dir.exists():
                        date_prefix = session.created_at.strftime("%Y-%m-%d")
                        model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                        title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        title_sanitized = title_sanitized.replace(" ", "_")
                        if not title_sanitized:
                            title_sanitized = f"Libro_{session.session_id[:8]}"
                        expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                        expected_path = books_dir / expected_filename
                        if expected_path.exists():
                            pdf_path = str(expected_path)
                    
                    if session.cover_image_path:
                        cover_path = session.cover_image_path
                    
                    gemini_2_5_books.append({
                        "session_id": session_id,
                        "title": entry.title,
                        "author": entry.author,
                        "model": session.form_data.llm_model,
                        "status": entry.status,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "pdf_path": pdf_path,
                        "cover_path": cover_path,
                        "has_pdf": pdf_path is not None,
                        "has_cover": cover_path is not None,
                    })
                except Exception as e:
                    print(f"[GEMINI-2.5-PREVIEW] Errore nel processare sessione {session_id}: {e}")
                    continue
        
        return {
            "total_books": len(gemini_2_5_books),
            "books": gemini_2_5_books,
        }
    
    except Exception as e:
        print(f"[GEMINI-2.5-PREVIEW] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel preview dei libri Gemini 2.5: {str(e)}"
        )


@router.post("/books/gemini-2.5/delete")
async def delete_gemini_2_5_books_endpoint(
    dry_run: bool = False,
    model_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user = Depends(require_admin),
):
    """
    Elimina tutti i libri generati con Gemini 2.5 (solo admin).
    
    Args:
        dry_run: Se True, simula l'eliminazione senza eliminare realmente
        model_filter: Filtra per modello specifico ("gemini-2.5-flash" o "gemini-2.5-pro")
        status_filter: Filtra per stato specifico (draft, outline, writing, paused, complete)
    """
    try:
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store, user_id=None)
        
        gemini_2_5_sessions = {}
        for session_id, session in all_sessions.items():
            if session.form_data and is_gemini_2_5(session.form_data.llm_model):
                if model_filter and session.form_data.llm_model != model_filter:
                    continue
                if status_filter:
                    entry = session_to_library_entry(session, skip_cost_calculation=True)
                    if entry.status != status_filter:
                        continue
                gemini_2_5_sessions[session_id] = session
        
        deleted_sessions = 0
        deleted_pdfs = 0
        deleted_covers = 0
        errors = []
        details = []
        
        books_dir = Path(__file__).parent.parent.parent / "books"
        storage_service = get_storage_service()
        
        for session_id, session in gemini_2_5_sessions.items():
            try:
                entry = session_to_library_entry(session, skip_cost_calculation=True)
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
                    pdf_deleted = False
                    try:
                        if entry.pdf_path:
                            if entry.pdf_path.startswith("gs://"):
                                try:
                                    storage_service.delete_file(entry.pdf_path)
                                    pdf_deleted = True
                                except Exception as e:
                                    errors.append(f"Errore eliminazione PDF GCS {entry.pdf_path}: {e}")
                            else:
                                pdf_path = Path(entry.pdf_path)
                                if pdf_path.exists():
                                    pdf_path.unlink()
                                    pdf_deleted = True
                        elif entry.status == "complete" and books_dir.exists():
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
                            else:
                                for pdf_file in books_dir.glob("*.pdf"):
                                    if session.session_id[:8] in pdf_file.stem or (title_sanitized and title_sanitized.lower() in pdf_file.stem.lower()):
                                        pdf_file.unlink()
                                        pdf_deleted = True
                                        break
                        
                        if pdf_deleted:
                            deleted_pdfs += 1
                            detail["pdf_deleted"] = True
                    except Exception as e:
                        errors.append(f"Errore eliminazione PDF per {entry.title}: {e}")
                    
                    cover_deleted = False
                    try:
                        if session.cover_image_path:
                            if session.cover_image_path.startswith("gs://"):
                                try:
                                    storage_service.delete_file(session.cover_image_path)
                                    cover_deleted = True
                                except Exception as e:
                                    errors.append(f"Errore eliminazione copertina GCS {session.cover_image_path}: {e}")
                            else:
                                cover_path = Path(session.cover_image_path)
                                if cover_path.exists():
                                    cover_path.unlink()
                                    cover_deleted = True
                            
                            if cover_deleted:
                                deleted_covers += 1
                                detail["cover_deleted"] = True
                    except Exception as e:
                        errors.append(f"Errore eliminazione copertina per {entry.title}: {e}")
                    
                    if await delete_session_async(session_store, session_id):
                        deleted_sessions += 1
                        detail["session_deleted"] = True
                    else:
                        errors.append(f"Errore eliminazione sessione {session_id}")
                else:
                    detail["pdf_deleted"] = entry.pdf_path is not None or (entry.status == "complete" and books_dir.exists())
                    detail["cover_deleted"] = session.cover_image_path is not None
                    detail["session_deleted"] = True
                
                details.append(detail)
            except Exception as e:
                errors.append(f"Errore durante eliminazione {session_id}: {e}")
                print(f"[GEMINI-2.5-DELETE] Errore eliminando {session_id}: {e}")
                import traceback
                traceback.print_exc()
        
        return {
            "success": True,
            "dry_run": dry_run,
            "total_found": len(gemini_2_5_sessions),
            "deleted_sessions": deleted_sessions if not dry_run else len(gemini_2_5_sessions),
            "deleted_pdfs": deleted_pdfs if not dry_run else sum(1 for d in details if d["pdf_deleted"]),
            "deleted_covers": deleted_covers if not dry_run else sum(1 for d in details if d["cover_deleted"]),
            "errors": errors if errors else None,
            "details": details,
        }
    
    except Exception as e:
        print(f"[GEMINI-2.5-DELETE] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'eliminazione dei libri Gemini 2.5: {str(e)}"
        )


@router.get("/books/pending")
async def get_pending_books_endpoint(
    current_user = Depends(require_admin),
):
    """Restituisce lista di libri in fase di generazione (draft, outline, writing, paused) con info utente (solo admin)."""
    try:
        session_store = get_session_store()
        user_store = get_user_store()
        
        if user_store.client is None or user_store.users_collection is None:
            await user_store.connect()
        
        # Recupera tutte le sessioni
        all_sessions = await get_all_sessions_async(session_store, user_id=None)
        
        # Stati che indicano generazione in corso
        in_progress_states = ["draft", "outline", "writing", "paused"]
        
        # Filtra solo quelle in stato di generazione
        pending_books = []
        
        for session_id, session in all_sessions.items():
            status = session.get_status()
            if status in in_progress_states:
                # Recupera info utente
                user_email = "Unknown"
                user_name = "Unknown"
                if session.user_id:
                    user = await user_store.get_user_by_id(session.user_id)
                    if user:
                        user_email = user.email
                        user_name = user.name
                
                # Info libro
                title = session.current_title or "Senza titolo"
                model = session.form_data.llm_model if session.form_data else "unknown"
                
                writing_progress = session.writing_progress or {}
                current_phase = writing_progress.get("current_phase", "unknown")
                current_chapter = writing_progress.get("current_chapter", 0)
                total_chapters = writing_progress.get("total_chapters", 0)
                error = writing_progress.get("error")
                is_paused = writing_progress.get("is_paused", False)
                is_complete = writing_progress.get("is_complete", False)
                
                pending_books.append({
                    "session_id": session_id,
                    "user_email": user_email,
                    "user_name": user_name,
                    "title": title,
                    "status": status,
                    "model": model,
                    "phase": current_phase,
                    "current_chapter": current_chapter,
                    "total_chapters": total_chapters,
                    "is_paused": is_paused,
                    "is_complete": is_complete,
                    "error": error,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                })
        
        # Raggruppa per utente
        by_user = defaultdict(list)
        for book in pending_books:
            by_user[book["user_email"]].append(book)
        
        return {
            "total": len(pending_books),
            "by_user": {
                email: {
                    "name": books[0]["user_name"] if books else "Unknown",
                    "count": len(books),
                    "books": books
                }
                for email, books in by_user.items()
            },
            "by_status": {
                status: len([b for b in pending_books if b["status"] == status])
                for status in in_progress_states
            },
            "with_errors": len([b for b in pending_books if b["error"]]),
        }
    
    except Exception as e:
        print(f"[PENDING BOOKS] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero libri in sospeso: {str(e)}"
        )


@router.post("/retention/cleanup")
async def run_retention_cleanup(
    current_user = Depends(require_admin),
):
    """
    Esegue manualmente il job di pulizia dati secondo le policy di retention GDPR.
    
    Elimina:
    - Notifiche lette più vecchie di 90 giorni
    - Referral pendenti scaduti (>30 giorni)
    - Sessioni incomplete più vecchie di 1 anno
    - Token scaduti (password reset, verifica email)
    - Anonimizza IP nei log di audit >90 giorni
    - Elimina log di audit >2 anni
    
    Solo admin.
    """
    from app.services.retention_service import get_retention_service
    
    try:
        service = get_retention_service()
        results = await service.run_cleanup()
        
        return {
            "success": True,
            "message": "Pulizia completata con successo",
            "results": results
        }
    except Exception as e:
        print(f"[RETENTION CLEANUP] Errore: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore durante la pulizia: {str(e)}"
        )

import asyncio
import os
import sys
from datetime import datetime

# Aggiungi il path del backend per importare i moduli
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_all_sessions_async
from app.agent.user_store import get_user_store

async def main():
    session_store = get_session_store()
    user_store = get_user_store()
    
    # Stati che indicano generazione in corso o sospesa
    in_progress_states = ["draft", "outline", "writing", "paused"]
    
    print("=== Libri in fase di generazione ===\n")
    
    # Recupera tutte le sessioni
    all_sessions = await get_all_sessions_async(session_store, user_id=None)
    
    # Filtra solo quelle in stato di generazione
    in_progress_sessions = {}
    for session_id, session in all_sessions.items():
        status = session.get_status()
        if status in in_progress_states:
            in_progress_sessions[session_id] = session
    
    if not in_progress_sessions:
        print("Nessun libro in fase di generazione trovato.")
        return
    
    # Raggruppa per utente
    by_user = {}
    
    for session_id, session in in_progress_sessions.items():
        user_id = session.user_id
        if not user_id:
            continue
            
        # Recupera info utente
        user = await user_store.get_user_by_id(user_id)
        user_email = user.email if user else "Unknown"
        user_name = user.name if user else "Unknown"
        
        if user_email not in by_user:
            by_user[user_email] = {
                "name": user_name,
                "books": []
            }
        
        # Info libro
        title = session.current_title or (session.form_data.book_title if session.form_data else None) or "Senza titolo"
        status = session.get_status()
        model = session.form_data.llm_model if session.form_data else "unknown"
        
        writing_progress = session.writing_progress or {}
        current_phase = writing_progress.get("current_phase", "unknown")
        current_chapter = writing_progress.get("current_chapter", 0)
        total_chapters = writing_progress.get("total_chapters", 0)
        error = writing_progress.get("error")
        
        created_at = session.created_at
        updated_at = session.updated_at
        
        by_user[user_email]["books"].append({
            "session_id": session_id,
            "title": title,
            "status": status,
            "model": model,
            "phase": current_phase,
            "chapter": f"{current_chapter}/{total_chapters}" if total_chapters > 0 else "N/A",
            "error": error,
            "created": created_at.isoformat() if created_at else "N/A",
            "updated": updated_at.isoformat() if updated_at else "N/A",
        })
    
    # Stampa risultati
    total_books = sum(len(user_data["books"]) for user_data in by_user.values())
    print(f"Trovati {total_books} libri in fase di generazione per {len(by_user)} utenti:\n")
    
    for email, user_data in sorted(by_user.items()):
        print(f"📧 {user_data['name']} ({email})")
        print(f"   Libri in corso: {len(user_data['books'])}")
        for book in user_data["books"]:
            print(f"   └─ {book['title']}")
            print(f"      Status: {book['status']} | Fase: {book['phase']} | Capitolo: {book['chapter']}")
            print(f"      Modello: {book['model']}")
            if book['error']:
                print(f"      ⚠️  ERRORE: {book['error']}")
            print(f"      Creato: {book['created']}")
            print(f"      Ultimo aggiornamento: {book['updated']}")
            print(f"      Session ID: {book['session_id']}")
            print()
        print()
    
    # Riepilogo per stato
    print("\n=== Riepilogo per stato ===")
    status_counts = {}
    for user_data in by_user.values():
        for book in user_data["books"]:
            status = book["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
    
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    
    # Riepilogo per fase
    print("\n=== Riepilogo per fase ===")
    phase_counts = {}
    for user_data in by_user.values():
        for book in user_data["books"]:
            phase = book["phase"]
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
    
    for phase, count in sorted(phase_counts.items()):
        print(f"  {phase}: {count}")
    
    # Libri con errori
    books_with_errors = []
    for user_data in by_user.values():
        for book in user_data["books"]:
            if book["error"]:
                books_with_errors.append(book)
    
    if books_with_errors:
        print(f"\n⚠️  {len(books_with_errors)} libri con errori:")
        for book in books_with_errors:
            print(f"  - {book['title']} ({book['status']}): {book['error']}")
    
    # Chiudi connessioni
    if hasattr(session_store, 'close'):
        await session_store.close()
    if hasattr(user_store, 'close'):
        await user_store.close()

if __name__ == "__main__":
    asyncio.run(main())

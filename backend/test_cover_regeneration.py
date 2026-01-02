"""
Script per testare la rigenerazione delle copertine.
Testa prima su un libro con copertina esistente, poi su quello problematico.
"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Carica variabili d'ambiente dal file .env
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()  # Fallback nella directory corrente

# Aggiungi il path del backend al sys.path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.agent.session_store import get_session_store


async def test_regenerate_cover(session_id: str):
    """Testa la rigenerazione di una copertina."""
    print(f"\n{'='*60}")
    print(f"TEST RIGENERAZIONE COPERTINA")
    print(f"Session ID: {session_id}")
    print(f"{'='*60}\n")
    
    session_store = get_session_store()
    session = session_store.get_session(session_id)
    
    if not session:
        print(f"[X] ERRORE: Sessione {session_id} non trovata!")
        return False
    
    print(f"[OK] Sessione trovata")
    print(f"  - Titolo: {session.current_title}")
    print(f"  - Autore: {session.form_data.user_name}")
    print(f"  - Stato: {session.get_status()}")
    print(f"  - Copertina esistente: {session.cover_image_path}")
    
    if session.get_status() != "complete":
        print(f"[X] ERRORE: Il libro deve essere completato!")
        return False
    
    # Importa la funzione di generazione
    from app.agent.cover_generator import generate_book_cover
    import os
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[X] ERRORE: GOOGLE_API_KEY non configurata!")
        return False
    
    print(f"\n[>>] Avvio rigenerazione copertina...")
    print(f"   (Controlla i log del backend per dettagli)\n")
    
    try:
        cover_path = await generate_book_cover(
            session_id=session_id,
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            plot=session.current_draft or "",
            api_key=api_key,
            cover_style=session.form_data.cover_style,
        )
        print(f"\n[OK] SUCCESSO! Copertina generata: {cover_path}")
        session_store.update_cover_image_path(session_id, cover_path)
        session_store._save_sessions()
        return True
    except Exception as e:
        print(f"\n[X] ERRORE durante la generazione:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def find_sessions_with_covers():
    """Trova sessioni con copertine esistenti."""
    session_store = get_session_store()
    sessions_with_covers = []
    
    for session_id, session in session_store._sessions.items():
        if session.get_status() == "complete" and session.cover_image_path:
            cover_path = Path(session.cover_image_path)
            if cover_path.exists():
                sessions_with_covers.append({
                    'session_id': session_id,
                    'title': session.current_title or "N/A",
                    'cover_path': session.cover_image_path
                })
    
    return sessions_with_covers


def find_sessions_without_covers():
    """Trova sessioni completate senza copertine."""
    session_store = get_session_store()
    sessions_without_covers = []
    
    for session_id, session in session_store._sessions.items():
        if session.get_status() == "complete":
            has_cover = False
            if session.cover_image_path:
                cover_path = Path(session.cover_image_path)
                if cover_path.exists():
                    has_cover = True
            
            if not has_cover:
                sessions_without_covers.append({
                    'session_id': session_id,
                    'title': session.current_title or "N/A"
                })
    
    return sessions_without_covers


async def main():
    print("\n" + "="*60)
    print("DIAGNOSI GENERAZIONE COPERTINE")
    print("="*60)
    
    # Trova sessioni con copertine
    print("\n[+] Libri CON copertina:")
    sessions_with_covers = find_sessions_with_covers()
    if sessions_with_covers:
        for i, sess in enumerate(sessions_with_covers[:5], 1):  # Mostra solo i primi 5
            print(f"  {i}. {sess['title']} ({sess['session_id'][:8]}...)")
        if len(sessions_with_covers) > 5:
            print(f"  ... e altri {len(sessions_with_covers) - 5}")
    else:
        print("  Nessuno trovato")
    
    # Trova sessioni senza copertine
    print("\n[-] Libri SENZA copertina:")
    sessions_without_covers = find_sessions_without_covers()
    if sessions_without_covers:
        for i, sess in enumerate(sessions_without_covers, 1):
            print(f"  {i}. {sess['title']} ({sess['session_id']})")
    else:
        print("  Nessuno trovato")
    
    # Test 1: Rigenera una copertina esistente
    if sessions_with_covers:
        print(f"\n{'='*60}")
        print("TEST 1: Rigenerazione copertina ESISTENTE")
        print(f"{'='*60}")
        test_session_id = sessions_with_covers[0]['session_id']
        success1 = await test_regenerate_cover(test_session_id)
        
        if success1:
            print("\n[OK] Test 1 PASSATO: La rigenerazione funziona su libri esistenti")
        else:
            print("\n[X] Test 1 FALLITO: Problema generale con la generazione copertine")
            return
    else:
        print("\n[!] Nessun libro con copertina trovato, salto Test 1")
        success1 = False
    
    # Test 2: Prova a generare copertina mancante
    if sessions_without_covers:
        print(f"\n{'='*60}")
        print("TEST 2: Generazione copertina MANCANTE")
        print(f"{'='*60}")
        test_session_id = sessions_without_covers[0]['session_id']
        success2 = await test_regenerate_cover(test_session_id)
        
        if success2:
            print("\n[OK] Test 2 PASSATO: La generazione funziona anche per libri senza copertina")
        else:
            print("\n[X] Test 2 FALLITO: Problema specifico con questo libro")
            print("   Controlla i log sopra per dettagli sull'errore")
    else:
        print("\n[!] Nessun libro senza copertina trovato, salto Test 2")
    
    print(f"\n{'='*60}")
    print("DIAGNOSI COMPLETATA")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())

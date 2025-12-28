#!/usr/bin/env python3
"""
Script di test semplice per la generazione dell'immagine di copertina.
Eseguire con: python test_cover_simple.py
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Aggiungi il path del backend per gli import
sys.path.insert(0, str(Path(__file__).parent))

# Carica variabili d'ambiente dal file .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"[TEST] Caricato .env da: {env_path}")
else:
    load_dotenv()
    print(f"[TEST] Tentativo caricamento .env dalla directory corrente")

from app.agent.cover_generator import generate_book_cover

async def test_cover_generation():
    """Testa la generazione dell'immagine di copertina."""
    
    # Ottieni API key da variabile d'ambiente
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERRORE: GOOGLE_API_KEY non trovata nelle variabili d'ambiente")
        print("Verifica che il file .env nella root del progetto contenga GOOGLE_API_KEY=...")
        return
    
    print("=" * 80)
    print("TEST GENERAZIONE IMMAGINE COPERTINA")
    print("=" * 80)
    
    # Dati di test
    session_id = "test_cover_001"
    title = "Il Mistero della Biblioteca Perduta"
    author = "Test Author"
    plot = """Un giovane bibliotecario scopre un antico manoscritto nascosto tra i volumi di una biblioteca abbandonata. 
Il manoscritto contiene mappe e indizi che portano a un tesoro leggendario. 
Mentre segue le tracce, si ritrova coinvolto in una cospirazione che risale a secoli fa, 
dove antichi ordini segreti combattono per il controllo di un potere che potrebbe cambiare il mondo.
Il protagonista dovrà decifrare enigmi, sfuggire a pericoli mortali e fare scelte difficili 
che determineranno non solo il suo destino, ma quello dell'intera umanità."""
    
    print(f"\n[TEST] Dati di test:")
    print(f"  Session ID: {session_id}")
    print(f"  Titolo: {title}")
    print(f"  Autore: {author}")
    print(f"  Plot: {len(plot)} caratteri (completo, senza limiti)")
    
    try:
        print(f"\n[TEST] Chiamata a generate_book_cover()...")
        cover_path = await generate_book_cover(
            session_id=session_id,
            title=title,
            author=author,
            plot=plot,
            api_key=api_key,
        )
        
        print(f"\n[TEST] SUCCESSO!")
        print(f"[TEST] Immagine copertina generata: {cover_path}")
        
        # Verifica che il file esista
        cover_file = Path(cover_path)
        if cover_file.exists():
            file_size = cover_file.stat().st_size
            print(f"[TEST] File esiste: {cover_file.absolute()}")
            print(f"[TEST] Dimensione file: {file_size} bytes")
            
            # Verifica che sia un'immagine valida
            from PIL import Image as PILImage
            try:
                img = PILImage.open(cover_path)
                print(f"[TEST] Immagine valida: {img.size[0]}x{img.size[1]} pixels")
                print(f"[TEST] Mode: {img.mode}")
                img.close()
            except Exception as e:
                print(f"[TEST] WARNING: Errore nell'apertura immagine: {e}")
        else:
            print(f"[TEST] ERRORE: File non trovato: {cover_path}")
            
    except Exception as e:
        print(f"\n[TEST] ERRORE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_cover_generation())


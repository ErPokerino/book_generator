#!/usr/bin/env python3
"""
Script di test standalone per debuggare la generazione dell'immagine di copertina.
Eseguire con: python test_cover_generation.py
"""

import os
import sys
from pathlib import Path
from io import BytesIO
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image as PILImage

# Aggiungi il path del backend per gli import
sys.path.insert(0, str(Path(__file__).parent))

# Carica variabili d'ambiente dal file .env
# Il file .env è nella root del progetto (un livello sopra backend)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"[TEST] Caricato .env da: {env_path}")
else:
    # Prova anche nella directory corrente
    load_dotenv()
    print(f"[TEST] Tentativo caricamento .env dalla directory corrente")

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
    
    # Inizializza il client
    print("\n[TEST] Inizializzazione client...")
    client = genai.Client(api_key=api_key)
    print("[TEST] Client inizializzato con successo")
    
    # Prompt di test semplice
    test_prompt = """Crea una copertina professionale per un libro con le seguenti informazioni:

**Titolo del libro:** Test Book
**Autore:** Test Author
**Trama:** Un libro di test per verificare la generazione dell'immagine di copertina.

La copertina deve includere:
1. Il titolo del libro in modo prominente e leggibile
2. Il nome dell'autore
3. Un'immagine visiva che rappresenti la storia"""
    
    # Lista dei modelli da testare
    models_to_test = [
        {
            'name': 'gemini-2.5-flash-image',
            'type': 'fallback',
            'config': None  # Prova prima senza config
        },
        {
            'name': 'gemini-3-pro-image-preview',
            'type': 'primario',
            'config': None  # Prova prima senza config
        },
    ]
    
    # Directory per salvare le immagini di test
    test_dir = Path(__file__).parent / "test_images"
    test_dir.mkdir(exist_ok=True)
    
    for model_config in models_to_test:
        model_name = model_config['name']
        model_type = model_config['type']
        
        print(f"\n{'=' * 80}")
        print(f"[TEST] Test con modello: {model_name} ({model_type})")
        print(f"{'=' * 80}")
        
        try:
            # Chiamata API
            print(f"[TEST] Chiamata API per {model_name}...")
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=[test_prompt]
                )
            except Exception as api_error:
                print(f"[TEST] ERRORE nella chiamata API: {api_error}")
                import traceback
                traceback.print_exc()
                continue
            
            print(f"[TEST] Risposta ricevuta da {model_name}")
            
            # Verifica response
            print(f"[TEST] Tipo response: {type(response)}")
            print(f"[TEST] Attributi response: {[a for a in dir(response) if not a.startswith('_')]}")
            
            # Verifica parts
            if not hasattr(response, 'parts'):
                print(f"[TEST] ERRORE: response non ha attributo 'parts'")
                print(f"[TEST] Attributi disponibili: {dir(response)}")
                continue
            
            if not response.parts:
                print(f"[TEST] ERRORE: Nessuna part nella risposta")
                continue
            
            print(f"[TEST] Numero di parts: {len(response.parts)}")
            
            # Estrai l'immagine
            pil_image = None
            extraction_method = None
            
            for idx, part in enumerate(response.parts):
                print(f"\n[TEST] Analizzando part {idx}:")
                print(f"  Tipo: {type(part).__name__}")
                print(f"  Attributi: {[a for a in dir(part) if not a.startswith('_')]}")
                
                # Metodo 1: part.as_image()
                if hasattr(part, 'as_image'):
                    print(f"  [TEST] Metodo as_image() disponibile")
                    if hasattr(part, 'inline_data') and part.inline_data is not None:
                        print(f"  [TEST] inline_data presente, provo as_image()...")
                        try:
                            pil_image = part.as_image()
                            print(f"  [TEST] OK: as_image() funziona!")
                            print(f"  [TEST] Tipo risultato: {type(pil_image)}")
                            if isinstance(pil_image, PILImage.Image):
                                print(f"  [TEST] OK: E' un oggetto PIL Image valido")
                                print(f"  [TEST] Dimensioni: {pil_image.size}")
                                print(f"  [TEST] Mode: {pil_image.mode}")
                                extraction_method = "as_image()"
                                break
                        except Exception as e:
                            print(f"  [TEST] ERRORE con as_image(): {e}")
                            import traceback
                            traceback.print_exc()
                
                # Metodo 2: inline_data.data
                if hasattr(part, 'inline_data') and part.inline_data is not None:
                    print(f"  [TEST] inline_data presente")
                    print(f"  [TEST] Tipo inline_data: {type(part.inline_data)}")
                    print(f"  [TEST] Attributi inline_data: {[a for a in dir(part.inline_data) if not a.startswith('_')]}")
                    
                    if hasattr(part.inline_data, 'data'):
                        data = part.inline_data.data
                        print(f"  [TEST] data presente, tipo: {type(data)}")
                        print(f"  [TEST] lunghezza data: {len(data) if hasattr(data, '__len__') else 'N/A'}")
                        
                        # Prova a decodificare come bytes
                        try:
                            if isinstance(data, bytes):
                                print(f"  [TEST] data è già bytes")
                                image_bytes = data
                            elif isinstance(data, str):
                                print(f"  [TEST] data è stringa, provo base64 decode...")
                                import base64
                                image_bytes = base64.b64decode(data)
                            else:
                                print(f"  [TEST] data è di tipo sconosciuto: {type(data)}")
                                continue
                            
                            print(f"  [TEST] Carico bytes come PIL Image...")
                            pil_image = PILImage.open(BytesIO(image_bytes))
                            print(f"  [TEST] OK: Immagine caricata da bytes!")
                            print(f"  [TEST] Dimensioni: {pil_image.size}")
                            print(f"  [TEST] Mode: {pil_image.mode}")
                            extraction_method = "inline_data.data"
                            break
                        except Exception as e:
                            print(f"  [TEST] ERRORE nel caricamento da bytes: {e}")
                            import traceback
                            traceback.print_exc()
                
                # Metodo 3: text (potrebbe contenere data URI)
                if hasattr(part, 'text') and part.text:
                    text_preview = part.text[:200] if len(part.text) > 200 else part.text
                    print(f"  [TEST] text presente (primi 200 caratteri): {text_preview}")
                    if part.text.startswith('data:image'):
                        print(f"  [TEST] text contiene data URI, provo a estrarre...")
                        try:
                            import base64
                            header, encoded = part.text.split(',', 1)
                            image_bytes = base64.b64decode(encoded)
                            pil_image = PILImage.open(BytesIO(image_bytes))
                            print(f"  [TEST] OK: Immagine estratta da data URI!")
                            extraction_method = "text data URI"
                            break
                        except Exception as e:
                            print(f"  [TEST] ERRORE con data URI: {e}")
            
            if pil_image is None:
                print(f"\n[TEST] ERRORE: Impossibile estrarre immagine da {model_name}")
                continue
            
            print(f"\n[TEST] OK: Immagine estratta con metodo: {extraction_method}")
            print(f"[TEST] Tipo: {type(pil_image)}")
            print(f"[TEST] Dimensioni: {pil_image.size}")
            print(f"[TEST] Mode: {pil_image.mode}")
            
            # Converti in RGB se necessario
            if pil_image.mode != 'RGB':
                print(f"[TEST] Conversione da {pil_image.mode} a RGB...")
                pil_image = pil_image.convert('RGB')
                print(f"[TEST] OK: Convertito in RGB")
            
            # Salva l'immagine
            test_image_path = test_dir / f"test_cover_{model_name.replace('-', '_')}.png"
            print(f"\n[TEST] Salvataggio immagine in: {test_image_path}")
            
            try:
                pil_image.save(test_image_path, "PNG")
                print(f"[TEST] OK: Immagine salvata")
            except Exception as e:
                print(f"[TEST] ERRORE nel salvataggio: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # Verifica file salvato
            if not test_image_path.exists():
                print(f"[TEST] ERRORE: File non creato")
                continue
            
            file_size = test_image_path.stat().st_size
            print(f"[TEST] Dimensione file: {file_size} bytes")
            
            if file_size == 0:
                print(f"[TEST] ERRORE: File vuoto")
                continue
            
            # Verifica che il file sia un PNG valido
            print(f"\n[TEST] Verifica file PNG...")
            try:
                # NON usare verify() perché chiude il file
                verify_image = PILImage.open(test_image_path)
                print(f"[TEST] OK: File aperto con successo")
                print(f"[TEST] Dimensioni verificate: {verify_image.size}")
                print(f"[TEST] Mode verificato: {verify_image.mode}")
                verify_image.close()
                print(f"[TEST] OK: File PNG valido e leggibile!")
            except Exception as verify_error:
                print(f"[TEST] ERRORE: File non è un PNG valido: {verify_error}")
                import traceback
                traceback.print_exc()
                continue
            
            print(f"\n[TEST] SUCCESSO con {model_name}!")
            print(f"[TEST] Immagine salvata in: {test_image_path}")
            print(f"[TEST] Puoi aprirla per verificare visivamente")
            
        except Exception as e:
            print(f"\n[TEST] ERRORE GENERALE con {model_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'=' * 80}")
    print("TEST COMPLETATO")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    asyncio.run(test_cover_generation())


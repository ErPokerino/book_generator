import os
import base64
from pathlib import Path
from typing import Optional
from io import BytesIO
import asyncio
from google import genai
from google.genai import types
from PIL import Image as PILImage
from app.core.config import get_app_config


async def generate_book_cover(
    session_id: str,
    title: str,
    author: str,
    plot: str,
    api_key: str,
    cover_style: Optional[str] = None,
) -> str:
    """
    Genera la copertina completa del libro (con titolo, autore e immagine) usando gemini-3-pro-image-preview.
    Se fallisce, prova con gemini-2.5-flash-image come fallback.
    
    Args:
        session_id: ID della sessione
        title: Titolo del libro
        author: Nome dell'autore (user_name, non autore di riferimento)
        plot: Trama estesa del libro
        api_key: API key per Gemini
    
    Returns:
        Path del file immagine salvato
    """
    # Inizializza il client con la nuova API
    client = genai.Client(api_key=api_key)
    
    # Leggi la configurazione per l'aspect ratio
    app_config = get_app_config()
    cover_config = app_config.get("cover_generation", {})
    aspect_ratio = cover_config.get("aspect_ratio", "2:3")
    
    # Prepara il prompt completo per la generazione della copertina
    # Usa il plot completo senza limiti
    plot_summary = plot
    
    # Mappa degli stili per il prompt
    style_descriptions = {
        "illustrato": "Stile illustrato: usa disegni artistici o pittorici, orientato all'atmosfera. L'immagine deve essere pittorica, evocativa e artistica.",
        "fotografico": "Stile fotografico: usa foto reali o rielaborate per un effetto realistico. L'immagine deve sembrare una fotografia professionale.",
        "tipografico": "Stile tipografico / Minimal: centralità del testo e della composizione grafica. L'immagine deve essere minimale, con focus sulla tipografia e composizione grafica elegante.",
        "simbolico": "Stile simbolico: usa un'immagine o segno metaforico che rappresenta il tema. L'immagine deve essere metaforica e concettuale.",
        "cartoon": "Stile cartoon: illustrazione stilizzata, tono leggero o ironico. L'immagine deve essere un'illustrazione stilizzata, vivace e moderna."
    }
    
    style_instruction = ""
    if cover_style and cover_style in style_descriptions:
        style_instruction = f"\n\n**Stile richiesto:** {style_descriptions[cover_style]}"
    
    image_prompt = f"""Crea una copertina professionale per un libro con le seguenti informazioni:

**Titolo del libro:** {title}
**Autore:** {author}
**Trama:** {plot_summary}{style_instruction}

La copertina deve includere:
1. Il titolo del libro in modo prominente e leggibile, ben visibile e con un font professionale
2. Il nome dell'autore, posizionato in modo appropriato (tipicamente in basso)
3. Un'immagine visiva che rappresenti la storia, basata sulla trama fornita

La copertina deve essere:
- Professionale e di alta qualità, adatta a un romanzo pubblicato
- Visivamente accattivante e memorabile
- Coerente con il genere e l'atmosfera della storia descritta nella trama
- Con una composizione equilibrata tra testo (titolo e autore) e immagine visiva
- Il testo deve essere chiaramente leggibile e ben integrato con l'immagine di sfondo
- Stile tipografico professionale per titolo e autore"""
    
    # Lista dei modelli da provare (primario e fallback)
    # Per ogni modello, specifichiamo anche la configurazione dell'immagine
    models_to_try = [
        {
            'name': 'gemini-3-pro-image-preview',
            'type': 'primario',
            'config': {
                'image_config': {
                    'aspect_ratio': aspect_ratio,  # Ratio configurabile (default: 2:3 per PDF A4)
                    'image_size': '2K'  # Alta risoluzione per copertina professionale
                }
            }
        },
        {
            'name': 'gemini-2.5-flash-image',
            'type': 'fallback',
            'config': {
                'image_config': {
                    'aspect_ratio': aspect_ratio  # Ratio configurabile (default: 2:3 per PDF A4)
                }
            }
        },
    ]
    
    sessions_dir = Path(__file__).parent.parent.parent / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    cover_path = sessions_dir / f"{session_id}_cover.png"
    
    last_error = None
    
    for model_config in models_to_try:
        model_name = model_config['name']
        model_type = model_config['type']
        config = model_config['config']
        
        try:
            print(f"[COVER GENERATOR] Tentativo generazione copertina con {model_name} ({model_type})...")
            
            # Genera l'immagine usando la nuova API asincrona
            print(f"[COVER GENERATOR] Chiamata API per {model_name}...")
            # Usa asyncio.to_thread per eseguire la chiamata sincrona in modo asincrono
            # Prova prima con config, se fallisce prova senza
            try:
                # Prova con types.GenerateContentConfig se disponibile
                if hasattr(types, 'GenerateContentConfig'):
                    config_obj = types.GenerateContentConfig(**config)
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=[image_prompt],
                        config=config_obj
                    )
                else:
                    # Fallback: passa config come dizionario
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=[image_prompt],
                        config=config
                    )
            except (TypeError, AttributeError) as e:
                # Se la sintassi con config non funziona, prova senza config
                print(f"[COVER GENERATOR] Config non supportata ({e}), provo senza config...")
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=[image_prompt]
                )
            print(f"[COVER GENERATOR] Risposta ricevuta da {model_name}")
            
            # DEBUG: Log completo della risposta
            print(f"[COVER GENERATOR] DEBUG - Tipo risposta: {type(response)}")
            print(f"[COVER GENERATOR] DEBUG - Attributi risposta: {[a for a in dir(response) if not a.startswith('_')]}")
            
            # Verifica candidates per blocchi di sicurezza
            if hasattr(response, 'candidates') and response.candidates:
                for idx, candidate in enumerate(response.candidates):
                    print(f"[COVER GENERATOR] DEBUG - Candidate {idx}:")
                    if hasattr(candidate, 'finish_reason'):
                        print(f"  finish_reason: {candidate.finish_reason}")
                    if hasattr(candidate, 'safety_ratings'):
                        print(f"  safety_ratings: {candidate.safety_ratings}")
            elif hasattr(response, 'candidates'):
                print(f"[COVER GENERATOR] DEBUG - candidates è vuoto o None")
            
            # Verifica prompt_feedback per blocchi
            if hasattr(response, 'prompt_feedback'):
                print(f"[COVER GENERATOR] DEBUG - prompt_feedback: {response.prompt_feedback}")
                if hasattr(response.prompt_feedback, 'block_reason'):
                    print(f"[COVER GENERATOR] ATTENZIONE - Blocco: {response.prompt_feedback.block_reason}")
            
            # Estrai l'immagine dalla risposta
            # Gestisci sia response.parts che response.candidates[0].content.parts
            parts_to_process = None
            
            # Metodo 1: Prova response.parts direttamente
            if hasattr(response, 'parts') and response.parts:
                parts_to_process = response.parts
                print(f"[COVER GENERATOR] Usando response.parts (metodo diretto), {len(parts_to_process)} parts trovate")
            
            # Metodo 2: Prova response.candidates[0].content.parts (struttura standard Gemini)
            elif hasattr(response, 'candidates') and response.candidates:
                for idx, candidate in enumerate(response.candidates):
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts') and candidate.content.parts:
                            parts_to_process = candidate.content.parts
                            print(f"[COVER GENERATOR] Usando response.candidates[{idx}].content.parts (struttura standard), {len(parts_to_process)} parts trovate")
                            break
            
            if not parts_to_process:
                # Log dettagliato prima di sollevare l'eccezione
                print(f"[COVER GENERATOR] ERRORE - Nessuna part disponibile nella risposta da {model_name}")
                print(f"[COVER GENERATOR] DEBUG - Tipo risposta: {type(response)}")
                print(f"[COVER GENERATOR] DEBUG - Attributi risposta: {[a for a in dir(response) if not a.startswith('_')]}")
                if hasattr(response, 'candidates') and response.candidates:
                    for idx, candidate in enumerate(response.candidates):
                        print(f"[COVER GENERATOR] ERRORE - Candidate {idx}:")
                        print(f"  Tipo: {type(candidate)}")
                        if hasattr(candidate, 'finish_reason'):
                            print(f"  finish_reason: {candidate.finish_reason}")
                        if hasattr(candidate, 'safety_ratings'):
                            print(f"  safety_ratings: {candidate.safety_ratings}")
                        if hasattr(candidate, 'content'):
                            print(f"  content presente: {candidate.content}")
                            if hasattr(candidate.content, 'parts'):
                                print(f"  content.parts: {candidate.content.parts}")
                raise Exception(f"Nessuna part disponibile nella risposta da {model_name}")
            
            print(f"[COVER GENERATOR] Numero di parts nella risposta: {len(parts_to_process)}")
            
            # Estrai l'immagine
            pil_image = None
            
            for idx, part in enumerate(parts_to_process):
                print(f"[COVER GENERATOR] Analizzando part {idx}, tipo: {type(part).__name__}")
                
                # Metodo 1: inline_data (snake_case)
                if hasattr(part, 'inline_data') and part.inline_data is not None:
                    print(f"[COVER GENERATOR] Trovato inline_data (snake_case), mime_type: {getattr(part.inline_data, 'mime_type', 'N/A')}")
                    if hasattr(part.inline_data, 'data'):
                        data = part.inline_data.data
                        print(f"[COVER GENERATOR] Tipo di data: {type(data)}")
                        
                        try:
                            if isinstance(data, bytes):
                                print(f"[COVER GENERATOR] data è già bytes, dimensione: {len(data)} bytes")
                                image_bytes = data
                            elif isinstance(data, str):
                                print(f"[COVER GENERATOR] data è stringa, provo base64 decode...")
                                image_bytes = base64.b64decode(data)
                                print(f"[COVER GENERATOR] Base64 decodificato, dimensione: {len(image_bytes)} bytes")
                            else:
                                print(f"[COVER GENERATOR] Tipo di data non supportato: {type(data)}")
                                continue
                            
                            pil_image = PILImage.open(BytesIO(image_bytes))
                            print(f"[COVER GENERATOR] Immagine caricata come PIL Image, dimensioni: {pil_image.size}")
                            break
                        except Exception as load_error:
                            print(f"[COVER GENERATOR] Errore nel caricamento PIL Image: {load_error}")
                            continue
                
                # Metodo 2: inlineData (camelCase) - per compatibilità con alcune versioni dell'API
                elif hasattr(part, 'inlineData') and part.inlineData is not None:
                    print(f"[COVER GENERATOR] Trovato inlineData (camelCase), mime_type: {getattr(part.inlineData, 'mimeType', getattr(part.inlineData, 'mime_type', 'N/A'))}")
                    if hasattr(part.inlineData, 'data'):
                        data = part.inlineData.data
                        print(f"[COVER GENERATOR] Tipo di data: {type(data)}")
                        
                        try:
                            if isinstance(data, bytes):
                                print(f"[COVER GENERATOR] data è già bytes, dimensione: {len(data)} bytes")
                                image_bytes = data
                            elif isinstance(data, str):
                                print(f"[COVER GENERATOR] data è stringa, provo base64 decode...")
                                image_bytes = base64.b64decode(data)
                                print(f"[COVER GENERATOR] Base64 decodificato, dimensione: {len(image_bytes)} bytes")
                            else:
                                print(f"[COVER GENERATOR] Tipo di data non supportato: {type(data)}")
                                continue
                            
                            pil_image = PILImage.open(BytesIO(image_bytes))
                            print(f"[COVER GENERATOR] Immagine caricata come PIL Image, dimensioni: {pil_image.size}")
                            break
                        except Exception as load_error:
                            print(f"[COVER GENERATOR] Errore nel caricamento PIL Image: {load_error}")
                            continue
                
                # Metodo 3: text con data URI
                if hasattr(part, 'text') and part.text:
                    text_preview = part.text[:100] if len(part.text) > 100 else part.text
                    print(f"[COVER GENERATOR] Trovato text (primi 100 caratteri): {text_preview}")
                    if part.text.startswith('data:image'):
                        print(f"[COVER GENERATOR] text contiene data URI, provo a estrarre...")
                        try:
                            header, encoded = part.text.split(',', 1)
                            image_bytes = base64.b64decode(encoded)
                            pil_image = PILImage.open(BytesIO(image_bytes))
                            print(f"[COVER GENERATOR] Immagine estratta da data URI, dimensioni: {pil_image.size}")
                            break
                        except Exception as data_uri_error:
                            print(f"[COVER GENERATOR] Errore con data URI: {data_uri_error}")
                            continue
            
            if pil_image is None:
                # Log dettagliato per debug
                print(f"[COVER GENERATOR] ERRORE: Impossibile estrarre immagine. Parts disponibili:")
                for idx, part in enumerate(parts_to_process):
                    print(f"  Part {idx}: {type(part).__name__}")
                    print(f"    Attributi: {[a for a in dir(part) if not a.startswith('_')]}")
                    # Prova a vedere se ci sono attributi con valori
                    try:
                        for attr in ['inline_data', 'inlineData', 'text', 'data']:
                            if hasattr(part, attr):
                                value = getattr(part, attr)
                                print(f"    {attr}: {type(value).__name__}")
                    except Exception:
                        pass
                raise Exception(f"Impossibile estrarre l'immagine dalla risposta di {model_name}. Formato non supportato.")
            
            # Verifica che l'immagine sia valida prima del salvataggio
            if not isinstance(pil_image, PILImage.Image):
                raise Exception(f"Immagine estratta ma non è un oggetto PIL Image valido: {type(pil_image)}")
            
            # Verifica dimensioni
            if pil_image.size[0] == 0 or pil_image.size[1] == 0:
                raise Exception(f"Immagine ha dimensioni zero: {pil_image.size}")
            
            print(f"[COVER GENERATOR] Immagine PIL valida, dimensioni: {pil_image.size}, mode: {pil_image.mode}")
            
            # Converti in RGB se necessario (per compatibilità)
            if pil_image.mode != 'RGB':
                print(f"[COVER GENERATOR] Conversione da {pil_image.mode} a RGB")
                pil_image = pil_image.convert('RGB')
            
            # Verifica che l'immagine convertita sia ancora valida
            if pil_image.size[0] == 0 or pil_image.size[1] == 0:
                raise Exception(f"Immagine convertita ha dimensioni zero: {pil_image.size}")
            
            # Salva l'immagine come PNG
            print(f"[COVER GENERATOR] Salvataggio immagine PNG in: {cover_path}")
            try:
                pil_image.save(cover_path, "PNG")
                print(f"[COVER GENERATOR] Salvataggio completato")
            except Exception as save_error:
                raise Exception(f"Errore nel salvataggio dell'immagine: {save_error}")
            
            # Verifica che il file sia stato salvato correttamente
            if not cover_path.exists():
                raise Exception(f"File non creato dopo scrittura: {cover_path}")
            
            file_size = cover_path.stat().st_size
            if file_size == 0:
                raise Exception(f"File creato ma vuoto: {cover_path}")
            
            # Verifica che il file sia un PNG valido aprendolo con PIL
            # NON usare verify() perché chiude il file e lo rende inutilizzabile
            try:
                verify_image = PILImage.open(cover_path)
                # Verifica che l'immagine sia valida controllando le dimensioni
                if verify_image.size[0] == 0 or verify_image.size[1] == 0:
                    verify_image.close()
                    raise Exception("Immagine ha dimensioni zero")
                verify_image.close()
                print(f"[COVER GENERATOR] File PNG validato con successo (dimensioni: {verify_image.size})")
            except Exception as verify_error:
                raise Exception(f"File salvato ma non è un PNG valido: {verify_error}")
            
            print(f"[COVER GENERATOR] Copertina generata con successo usando {model_name}")
            print(f"[COVER GENERATOR] File salvato: {cover_path}, dimensione: {file_size} bytes")
            return str(cover_path)
            
        except Exception as e:
            last_error = e
            print(f"[COVER GENERATOR] ERRORE con {model_name} ({model_type}): {e}")
            import traceback
            traceback.print_exc()
            if model_type == 'primario':
                print(f"[COVER GENERATOR] Tentativo con modello fallback...")
                continue
            else:
                # Se anche il fallback fallisce, solleva l'eccezione
                print(f"[COVER GENERATOR] Anche il modello fallback ha fallito")
                raise
    
    # Se arriviamo qui, entrambi i modelli hanno fallito
    print(f"[COVER GENERATOR] ERRORE: Entrambi i modelli hanno fallito. Ultimo errore: {last_error}")
    import traceback
    traceback.print_exc()
    raise Exception(f"Errore nella generazione della copertina: {str(last_error)}")


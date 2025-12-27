import os
from pathlib import Path
from typing import Optional
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.models import SubmissionRequest


def _coerce_llm_content_to_text(content) -> str:
    """Normalizza response.content a stringa."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if item is None:
                continue
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                txt = item.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


async def generate_cover_description(
    title: str,
    author: str,
    plot: str,
    api_key: str,
) -> str:
    """
    Genera una descrizione visiva dettagliata per la copertina del libro usando un LLM.
    
    Args:
        title: Titolo del libro
        author: Nome dell'autore
        plot: Trama estesa del libro
        api_key: API key per Gemini
    
    Returns:
        Descrizione visiva dettagliata per la generazione dell'immagine
    """
    prompt = f"""Sei un art director esperto nella creazione di copertine per libri. 
Il tuo compito è creare una descrizione visiva dettagliata e coinvolgente per la copertina di un romanzo.

**Informazioni sul libro:**
- Titolo: {title}
- Autore: {author}
- Trama: {plot[:2000]}  # Limita la lunghezza per evitare token eccessivi

**Istruzioni:**
Crea una descrizione visiva dettagliata per la copertina che:
1. Catturi l'essenza e l'atmosfera della storia
2. Sia visivamente accattivante e professionale
3. Comunichi il genere e il tono del romanzo
4. Non includa testo (titolo o nome autore) - solo elementi visivi
5. Descriva composizione, colori, elementi visivi, atmosfera e mood

La descrizione deve essere dettagliata ma concisa, focalizzata su ciò che un artista potrebbe disegnare o un modello di generazione immagini potrebbe creare.

Rispondi SOLO con la descrizione visiva, senza introduzioni o commenti aggiuntivi."""

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        google_api_key=api_key,
        temperature=0.8,
    )
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        description = _coerce_llm_content_to_text(response.content).strip()
        return description
    except Exception as e:
        raise Exception(f"Errore nella generazione della descrizione copertina: {str(e)}")


async def generate_book_cover(
    session_id: str,
    title: str,
    author: str,
    plot: str,
    api_key: str,
) -> str:
    """
    Genera la copertina del libro usando gemini-3-pro-image-preview.
    
    Args:
        session_id: ID della sessione
        title: Titolo del libro
        author: Nome dell'autore (user_name, non autore di riferimento)
        plot: Trama estesa del libro
        api_key: API key per Gemini
    
    Returns:
        Path del file immagine salvato
    """
    try:
        print(f"[COVER GENERATOR] Inizio generazione copertina per sessione {session_id}")
        
        # Step 1: Genera descrizione visiva usando LLM
        print(f"[COVER GENERATOR] Generazione descrizione visiva...")
        visual_description = await generate_cover_description(
            title=title,
            author=author,
            plot=plot,
            api_key=api_key,
        )
        print(f"[COVER GENERATOR] Descrizione generata: {visual_description[:100]}...")
        
        # Step 2: Configura Google Generative AI
        genai.configure(api_key=api_key)
        
        # Step 3: Genera l'immagine usando gemini-3-pro-image-preview
        print(f"[COVER GENERATOR] Generazione immagine con gemini-3-pro-image-preview...")
        model = genai.GenerativeModel('gemini-3-pro-image-preview')
        
        # Crea il prompt completo per la generazione dell'immagine
        image_prompt = f"""Crea una copertina professionale per un libro con le seguenti caratteristiche visive:

{visual_description}

La copertina deve essere:
- Professionale e di alta qualità
- Adatta a un romanzo pubblicato
- Visivamente accattivante e memorabile
- Coerente con il genere e l'atmosfera della storia

Non includere testo, titoli o nomi nella copertina - solo elementi visivi."""
        
        # Genera l'immagine
        response = model.generate_content(image_prompt)
        
        # Estrai l'immagine dalla risposta
        if not response.candidates or not response.candidates[0].content.parts:
            raise Exception("Nessuna immagine generata nella risposta")
        
        # Salva l'immagine
        sessions_dir = Path(__file__).parent.parent.parent / "sessions"
        sessions_dir.mkdir(exist_ok=True)
        cover_path = sessions_dir / f"{session_id}_cover.png"
        
        # Il modello gemini-3-pro-image-preview può restituire immagini in vari formati
        # Proviamo diversi metodi per estrarre l'immagine
        image_data = None
        
        for part in response.candidates[0].content.parts:
            # Metodo 1: inline_data (base64)
            if hasattr(part, 'inline_data') and part.inline_data:
                import base64
                image_data = base64.b64decode(part.inline_data.data)
                break
            
            # Metodo 2: text con data URI
            if hasattr(part, 'text') and part.text:
                if part.text.startswith('data:image'):
                    import base64
                    header, encoded = part.text.split(',', 1)
                    image_data = base64.b64decode(encoded)
                    break
                # Se il testo contiene un URL, potremmo dover scaricarlo
                # Per ora ignoriamo questo caso
        
        if image_data is None:
            # Se non abbiamo trovato l'immagine, proviamo a cercare in altri formati
            # o solleviamo un errore
            raise Exception(f"Impossibile estrarre l'immagine dalla risposta. Formato non supportato.")
        
        # Salva l'immagine
        with open(cover_path, 'wb') as f:
            f.write(image_data)
        
        print(f"[COVER GENERATOR] Copertina salvata in: {cover_path}")
        return str(cover_path)
        
    except Exception as e:
        print(f"[COVER GENERATOR] ERRORE nella generazione copertina: {e}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Errore nella generazione della copertina: {str(e)}")


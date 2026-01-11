"""Service per la generazione di critiche letterarie."""
import os
import sys
from pathlib import Path
from typing import Optional

from google.cloud import texttospeech

from fastapi import HTTPException

from app.models import LiteraryCritique
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async
from app.agent.literary_critic import generate_literary_critique_from_pdf


def setup_google_tts_credentials():
    """Configura le credenziali Google Cloud per Text-to-Speech."""
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not cred_path:
        root_dir = Path(__file__).parent.parent.parent
        default_cred_path = root_dir / "credentials" / "narrai-app-credentials.json"
        if default_cred_path.exists():
            cred_path = str(default_cred_path)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
            print(f"[CRITIQUE AUDIO] Usando credenziali di default: {cred_path}", file=sys.stderr)
        else:
            print(f"[CRITIQUE AUDIO] WARNING: Nessuna credenziale trovata. Cerca GOOGLE_APPLICATION_CREDENTIALS o credentials/narrai-app-credentials.json", file=sys.stderr)
    elif not Path(cred_path).is_absolute():
        root_dir = Path(__file__).parent.parent.parent
        abs_cred_path = (root_dir / cred_path.lstrip("./")).resolve()
        if abs_cred_path.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(abs_cred_path)
            print(f"[CRITIQUE AUDIO] Credenziali caricate da: {abs_cred_path}", file=sys.stderr)
        else:
            print(f"[CRITIQUE AUDIO] WARNING: Path credenziali non trovato: {abs_cred_path}", file=sys.stderr)
    else:
        if Path(cred_path).exists():
            print(f"[CRITIQUE AUDIO] Credenziali caricate da: {cred_path}", file=sys.stderr)
        else:
            print(f"[CRITIQUE AUDIO] WARNING: Path credenziali non trovato: {cred_path}", file=sys.stderr)


def handle_tts_error(e: Exception) -> HTTPException:
    """Gestisce errori del servizio Text-to-Speech con messaggi user-friendly."""
    error_str = str(e)
    
    if "SERVICE_DISABLED" in error_str or "has not been used" in error_str or "it is disabled" in error_str:
        project_id = "274471015864"
        import re
        project_match = re.search(r'project[:\s]+(\d+)', error_str, re.IGNORECASE)
        if project_match:
            project_id = project_match.group(1)
        
        return HTTPException(
            status_code=503,
            detail=f"L'API Text-to-Speech non è abilitata nel progetto Google Cloud. Per abilitarla, visita: https://console.cloud.google.com/apis/library/texttospeech.googleapis.com?project={project_id} e clicca su 'Abilita'. Dopo l'abilitazione, attendi alcuni minuti prima di riprovare."
        )
    elif "403" in error_str or "permission" in error_str.lower() or "forbidden" in error_str.lower():
        return HTTPException(
            status_code=403,
            detail="Permessi insufficienti per utilizzare il servizio Text-to-Speech. Verifica che il service account abbia il ruolo 'Cloud Text-to-Speech API User'."
        )
    elif "401" in error_str or "unauthorized" in error_str.lower() or "invalid credentials" in error_str.lower():
        return HTTPException(
            status_code=401,
            detail="Credenziali Google Cloud non valide o scadute. Verifica il file di credenziali."
        )
    else:
        return HTTPException(
            status_code=500,
            detail="Errore nella configurazione del servizio di sintesi vocale. Verifica le credenziali Google Cloud."
        )


async def generate_critique_audio(
    session_id: str,
    voice_name: Optional[str] = None,
) -> bytes:
    """
    Genera audio MP3 della critica letteraria usando Google Cloud Text-to-Speech.
    
    Args:
        session_id: ID della sessione
        voice_name: Nome della voce (default: it-IT-Standard-A)
    
    Returns:
        Bytes del file MP3
    """
    from fastapi import HTTPException
    
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")
    
    if not session.literary_critique:
        raise HTTPException(status_code=404, detail="Critica non disponibile per questo libro")
    
    # Converti critica in LiteraryCritique se è un dict
    critique = session.literary_critique
    if isinstance(critique, dict):
        critique = LiteraryCritique(**critique)
    
    # Costruisci testo completo per la sintesi vocale
    text_parts = []
    
    if critique.summary:
        text_parts.append(f"Sintesi: {critique.summary}")
    
    if critique.pros and len(critique.pros) > 0:
        pros_text = ". ".join(critique.pros)
        text_parts.append(f"Punti di forza: {pros_text}")
    
    if critique.cons and len(critique.cons) > 0:
        cons_text = ". ".join(critique.cons)
        text_parts.append(f"Punti di debolezza: {cons_text}")
    
    if not text_parts:
        raise HTTPException(status_code=400, detail="Critica vuota, nessun contenuto da leggere")
    
    full_text = ". ".join(text_parts)
    
    # Limita la lunghezza del testo
    max_chars = 4500
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "..."
        print(f"[CRITIQUE AUDIO] Testo troncato a {max_chars} caratteri", file=sys.stderr)
    
    # Configurazione voce italiana
    if not voice_name:
        voice_name = "it-IT-Standard-A"
    
    # Inizializza client Google Cloud Text-to-Speech
    try:
        setup_google_tts_credentials()
        client = texttospeech.TextToSpeechClient()
        print(f"[CRITIQUE AUDIO] Client TTS inizializzato con successo", file=sys.stderr)
    except Exception as e:
        raise handle_tts_error(e)
    
    # Configura sintesi vocale
    synthesis_input = texttospeech.SynthesisInput(text=full_text)
    
    voice = texttospeech.VoiceSelectionParams(
        language_code="it-IT",
        name=voice_name,
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
        pitch=0.0,
        volume_gain_db=0.0,
    )
    
    # Genera audio
    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        
        print(f"[CRITIQUE AUDIO] Audio generato con successo per sessione {session_id} ({len(response.audio_content)} bytes)", file=sys.stderr)
        return response.audio_content
        
    except Exception as e:
        error_str = str(e)
        print(f"[CRITIQUE AUDIO] Errore nella sintesi vocale: {error_str}", file=sys.stderr)
        raise handle_tts_error(e)


async def analyze_pdf_from_bytes(
    pdf_bytes: bytes,
    title: Optional[str] = None,
    author: Optional[str] = None,
) -> dict:
    """
    Analizza un PDF esterno e genera una critica letteraria.
    
    Args:
        pdf_bytes: Bytes del file PDF
        title: Titolo del libro (opzionale)
        author: Autore del libro (opzionale)
    
    Returns:
        Dict con la critica (compatibile con LiteraryCritique)
    """
    critique = await generate_literary_critique_from_pdf(
        title=title or "Romanzo",
        author=author or "Autore",
        pdf_bytes=pdf_bytes,
        api_key=None,  # Auto-detect da env
    )
    
    return critique

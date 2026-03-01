"""Service per la generazione di audio Text-to-Speech."""
import os
import sys
from pathlib import Path
from typing import Optional

from google.cloud import texttospeech
from fastapi import HTTPException

from app.models import LiteraryCritique
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async
from app.services.storage_service import get_storage_service


def setup_google_tts_credentials():
    """Configura le credenziali Google Cloud per Text-to-Speech."""
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not cred_path:
        root_dir = Path(__file__).parent.parent.parent
        default_cred_path = root_dir / "credentials" / "narrai-app-credentials.json"
        if default_cred_path.exists():
            cred_path = str(default_cred_path)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
            print(f"[TTS] Usando credenziali di default: {cred_path}", file=sys.stderr)
        else:
            print(f"[TTS] WARNING: Nessuna credenziale trovata. Cerca GOOGLE_APPLICATION_CREDENTIALS o credentials/narrai-app-credentials.json", file=sys.stderr)
    elif not Path(cred_path).is_absolute():
        root_dir = Path(__file__).parent.parent.parent
        abs_cred_path = (root_dir / cred_path.lstrip("./")).resolve()
        if abs_cred_path.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(abs_cred_path)
            print(f"[TTS] Credenziali caricate da: {abs_cred_path}", file=sys.stderr)
        else:
            print(f"[TTS] WARNING: Path credenziali non trovato: {abs_cred_path}", file=sys.stderr)
    else:
        if Path(cred_path).exists():
            print(f"[TTS] Credenziali caricate da: {cred_path}", file=sys.stderr)
        else:
            print(f"[TTS] WARNING: Path credenziali non trovato: {cred_path}", file=sys.stderr)


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
            detail=f"L'API Text-to-Speech non è abilitata nel progetto Google Cloud. Per abilitarla, visita: https://console.cloud.google.com/apis/library/texttospeech.googleapis.com?project={project_id} e clicca su 'Abilita'."
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
            detail=f"Errore nella configurazione del servizio di sintesi vocale: {error_str}"
        )


async def generate_critique_audio(
    session_id: str,
    voice_name: Optional[str] = None,
) -> bytes:
    """
    Genera audio MP3 della critica letteraria usando Google Cloud Text-to-Speech.
    """
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")
    
    if not session.literary_critique:
        raise HTTPException(status_code=404, detail="Critica non disponibile per questo libro")
    
    critique = session.literary_critique
    if isinstance(critique, dict):
        critique = LiteraryCritique(**critique)
    
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
    max_chars = 4500
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "..."
    
    if not voice_name:
        voice_name = "it-IT-Standard-A"
    
    try:
        setup_google_tts_credentials()
        client = texttospeech.TextToSpeechClient()
    except Exception as e:
        raise handle_tts_error(e)
    
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
    
    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        return response.audio_content
    except Exception as e:
        raise handle_tts_error(e)


async def generate_chapter_audio(
    session_id: str,
    chapter_index: int,
    voice_name: Optional[str] = None,
) -> bytes:
    """
    Genera o recupera dal caching l'audio MP3 del capitolo.
    """
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")
    
    if not session.book_chapters or chapter_index < 0 or chapter_index >= len(session.book_chapters):
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
        
    chapter = session.book_chapters[chapter_index]
    chapter_title = chapter.get('title', f'Capitolo {chapter_index + 1}')
    chapter_content = chapter.get('content', '')
    
    if not chapter_content:
        raise HTTPException(status_code=400, detail="Contenuto del capitolo vuoto")
        
    storage_service = get_storage_service()
    cache_path = f"books/audio/{session_id}_chapter_{chapter_index}.mp3"
    
    # Try to get from cache
    try:
        gcs_cache_path = f"gs://{storage_service.bucket_name}/{cache_path}" if storage_service.gcs_enabled else cache_path
        if storage_service.file_exists(gcs_cache_path) or storage_service.file_exists(cache_path):
            try:
                audio_data = storage_service.download_file(gcs_cache_path if storage_service.gcs_enabled else cache_path)
                print(f"[TTS CHAPTER] Restituito audio da cache: {cache_path}", file=sys.stderr)
                return audio_data
            except Exception as e:
                print(f"[TTS CHAPTER] Errore lettura cache: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[TTS CHAPTER] Errore verifica cache: {e}", file=sys.stderr)
        
    # Remove markdown for reading
    import re
    clean_text = re.sub(r'#+\s*', '', chapter_content)
    clean_text = clean_text.replace('*', '').replace('_', '')
    full_text = f"{chapter_title}. {clean_text}"
    
    if not voice_name:
        voice_name = session.form_data.narrative_voice if session.form_data and session.form_data.narrative_voice else "it-IT-Standard-A"
        
    try:
        setup_google_tts_credentials()
        client = texttospeech.TextToSpeechClient()
    except Exception as e:
        raise handle_tts_error(e)
        
    ssml_gender = texttospeech.SsmlVoiceGender.FEMALE if "-A" in voice_name or "-B" in voice_name else texttospeech.SsmlVoiceGender.MALE
    voice = texttospeech.VoiceSelectionParams(
        language_code="it-IT",
        name=voice_name,
        ssml_gender=ssml_gender,
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
    )
    
    # Chunking max 4000 chars per Google TTS limits
    max_chunk_size = 4000
    chunks = []
    paragraphs = full_text.split('\n')
    current_chunk = ""
    for p in paragraphs:
        if len(current_chunk) + len(p) < max_chunk_size:
            current_chunk += p + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(p) >= max_chunk_size:
                for i in range(0, len(p), max_chunk_size):
                    chunks.append(p[i:i+max_chunk_size])
                current_chunk = ""
            else:
                current_chunk = p + "\n"
                
    if current_chunk:
        chunks.append(current_chunk)
        
    combined_audio = b''
    try:
        for chunk in chunks:
            if not chunk.strip():
                continue
            synthesis_input = texttospeech.SynthesisInput(text=chunk)
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
            combined_audio += response.audio_content
            
        print(f"[TTS CHAPTER] Audio generato con successo per sessione {session_id}, cap {chapter_index} ({len(combined_audio)} bytes)", file=sys.stderr)
        
        # Save to cache
        try:
            storage_service.upload_file(
                data=combined_audio,
                destination_path=cache_path,
                content_type="audio/mpeg",
                user_id=session.user_id
            )
        except Exception as e:
            print(f"[TTS CHAPTER] Errore salvataggio cache: {e}", file=sys.stderr)
            
        return combined_audio
        
    except Exception as e:
        print(f"[TTS CHAPTER] Errore nella sintesi vocale: {e}", file=sys.stderr)
        raise handle_tts_error(e)

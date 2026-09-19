"""Service per la generazione di audio Text-to-Speech via Gemini."""
from __future__ import annotations

import asyncio
import io
import re
import sys
import wave
from typing import Any, Optional

from fastapi import HTTPException
from google.genai import types

from app.models import LiteraryCritique
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async
from app.llm import build_google_genai_client
from app.llm.model_routing import DEFAULT_TTS_MODEL, get_stage_model
from app.services.storage_service import get_storage_service

DEFAULT_VOICE = "Kore"
TTS_SAMPLE_RATE = 24000
MAX_CHUNK_CHARS = 3500


def handle_tts_error(e: Exception) -> HTTPException:
    """Gestisce errori del servizio Text-to-Speech con messaggi user-friendly."""
    error_str = str(e)
    lowered = error_str.lower()
    if "api key" in lowered or "401" in error_str or "unauthorized" in lowered:
        return HTTPException(
            status_code=401,
            detail="Chiave Gemini mancante o non valida. Verifica GOOGLE_API_KEY nel file .env.",
        )
    if "404" in error_str or "not found" in lowered:
        return HTTPException(
            status_code=503,
            detail="Il modello TTS Gemini non è disponibile per questa chiave. Riprova più tardi.",
        )
    return HTTPException(
        status_code=500,
        detail=f"Errore nella sintesi vocale: {error_str}",
    )


def _pcm_to_wav(pcm: bytes, sample_rate: int = TTS_SAMPLE_RATE, sample_width: int = 2, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()


def _extract_inline_audio(response: Any) -> tuple[bytes, str]:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) if content is not None else None
        if not parts:
            continue
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is None or not getattr(inline_data, "data", None):
                continue
            raw = inline_data.data
            if isinstance(raw, str):
                import base64

                raw = base64.b64decode(raw)
            mime = str(getattr(inline_data, "mime_type", "") or "audio/pcm")
            return bytes(raw), mime
    raise ValueError("La risposta TTS non contiene audio")


def _chunk_text(full_text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    chunks: list[str] = []
    paragraphs = full_text.split("\n")
    current = ""
    for paragraph in paragraphs:
        piece = paragraph if paragraph.endswith("\n") else f"{paragraph}\n"
        if len(current) + len(piece) < max_chars:
            current += piece
            continue
        if current.strip():
            chunks.append(current.strip())
        if len(piece) >= max_chars:
            for index in range(0, len(piece), max_chars):
                chunks.append(piece[index : index + max_chars].strip())
            current = ""
        else:
            current = piece
    if current.strip():
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


def _resolve_voice(voice_name: Optional[str]) -> str:
    if not voice_name:
        return DEFAULT_VOICE
    if voice_name.startswith("it-IT-") or voice_name.startswith("en-"):
        return DEFAULT_VOICE
    return voice_name


async def _synthesize_chunks(text: str, *, form_data=None, voice_name: Optional[str] = None) -> bytes:
    model_name = get_stage_model("tts", form_data=form_data) or DEFAULT_TTS_MODEL
    voice = _resolve_voice(voice_name)
    client = build_google_genai_client()
    speech_config = None
    if hasattr(types, "SpeechConfig") and hasattr(types, "VoiceConfig") and hasattr(types, "PrebuiltVoiceConfig"):
        speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        )

    config_kwargs: dict[str, Any] = {"response_modalities": ["AUDIO"]}
    if speech_config is not None:
        config_kwargs["speech_config"] = speech_config
    config_obj = types.GenerateContentConfig(**config_kwargs) if hasattr(types, "GenerateContentConfig") else config_kwargs

    pcm_parts: list[bytes] = []
    mime_type = "audio/pcm"
    for chunk in _chunk_text(text):
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=chunk,
            config=config_obj,
        )
        audio_bytes, mime_type = _extract_inline_audio(response)
        pcm_parts.append(audio_bytes)

    combined = b"".join(pcm_parts)
    if "wav" in mime_type or "mpeg" in mime_type or "mp3" in mime_type:
        return combined
    return _pcm_to_wav(combined)


async def generate_critique_audio(
    session_id: str,
    voice_name: Optional[str] = None,
) -> bytes:
    """Genera audio WAV della critica letteraria usando Gemini TTS."""
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
    if critique.pros:
        text_parts.append(f"Punti di forza: {'. '.join(critique.pros)}")
    if critique.cons:
        text_parts.append(f"Punti di debolezza: {'. '.join(critique.cons)}")

    if not text_parts:
        raise HTTPException(status_code=400, detail="Critica vuota, nessun contenuto da leggere")

    full_text = ". ".join(text_parts)
    if len(full_text) > 4500:
        full_text = full_text[:4500] + "..."

    storage_service = get_storage_service()
    cache_path = f"books/audio/{session_id}_critique.wav"
    try:
        if storage_service.exists(cache_path):
            return storage_service.download_file(cache_path)
    except Exception as exc:
        print(f"[TTS CRITIQUE] Errore verifica cache: {exc}", file=sys.stderr)

    try:
        audio_data = await _synthesize_chunks(
            full_text,
            form_data=getattr(session, "form_data", None),
            voice_name=voice_name,
        )
        try:
            storage_service.upload_file(
                data=audio_data,
                destination_path=cache_path,
                content_type="audio/wav",
            )
        except Exception as exc:
            print(f"[TTS CRITIQUE] Cache non salvata: {exc}", file=sys.stderr)
        return audio_data
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_tts_error(exc)


async def generate_chapter_audio(
    session_id: str,
    chapter_index: int,
    voice_name: Optional[str] = None,
) -> bytes:
    """Genera audio WAV di un capitolo usando Gemini TTS."""
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)

    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")

    if not session.book_chapters or chapter_index < 0 or chapter_index >= len(session.book_chapters):
        raise HTTPException(status_code=404, detail="Capitolo non trovato")

    chapter = session.book_chapters[chapter_index]
    chapter_title = chapter.get("title", f"Capitolo {chapter_index + 1}")
    chapter_content = chapter.get("content", "")
    if not chapter_content:
        raise HTTPException(status_code=400, detail="Contenuto del capitolo vuoto")

    storage_service = get_storage_service()
    cache_path = f"books/audio/{session_id}_chapter_{chapter_index}.wav"
    try:
        if storage_service.exists(cache_path):
            return storage_service.download_file(cache_path)
    except Exception as exc:
        print(f"[TTS CHAPTER] Errore verifica cache: {exc}", file=sys.stderr)

    clean_text = re.sub(r"#+\s*", "", chapter_content)
    clean_text = clean_text.replace("*", "").replace("_", "")
    full_text = f"{chapter_title}. {clean_text}"

    try:
        audio_data = await _synthesize_chunks(
            full_text,
            form_data=getattr(session, "form_data", None),
            voice_name=voice_name,
        )
        try:
            storage_service.upload_file(
                data=audio_data,
                destination_path=cache_path,
                content_type="audio/wav",
            )
        except Exception as exc:
            print(f"[TTS CHAPTER] Cache non salvata: {exc}", file=sys.stderr)
        return audio_data
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_tts_error(exc)

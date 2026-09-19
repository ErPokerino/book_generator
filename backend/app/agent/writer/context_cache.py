"""Cache esplicita Gemini per il prefix stabile dello scrittore."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Optional

from google.genai import types
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_temperature_for_agent
from app.core.logging import get_logger
from app.llm import (
    LLMTraceRecorder,
    build_google_chat_model,
    build_google_genai_client,
    get_max_output_tokens,
    invoke_chat_model,
)

logger = get_logger("writer-context-cache")

_CACHE_NAMES: dict[str, str] = {}
CACHE_TTL_SECONDS = 3600


def writer_cache_fingerprint(model_name: str, system_prompt: str, prefix: str) -> str:
    payload = f"{model_name}\n{system_prompt}\n{prefix}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _create_explicit_cache(
    *,
    model_name: str,
    system_prompt: str,
    prefix: str,
    api_key: Optional[str],
) -> Optional[str]:
    try:
        client = build_google_genai_client(api_key=api_key)
        cache = client.caches.create(
            model=model_name,
            config={
                "system_instruction": system_prompt,
                "contents": [
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prefix)],
                    )
                ],
                "ttl": f"{CACHE_TTL_SECONDS}s",
            },
        )
        name = getattr(cache, "name", None)
        if not name:
            return None
        logger.info("Cache writer creata", context={"model": model_name, "cache": name})
        return str(name)
    except Exception as exc:
        logger.info(
            "Cache writer non disponibile, uso il prefix in chiaro",
            context={"model": model_name, "error": str(exc)},
        )
        return None


def resolve_writer_cache_name(
    *,
    model_name: str,
    system_prompt: str,
    prefix: str,
    api_key: Optional[str],
) -> Optional[str]:
    fingerprint = writer_cache_fingerprint(model_name, system_prompt, prefix)
    cached = _CACHE_NAMES.get(fingerprint)
    if cached:
        return cached
    created = _create_explicit_cache(
        model_name=model_name,
        system_prompt=system_prompt,
        prefix=prefix,
        api_key=api_key,
    )
    if created:
        _CACHE_NAMES[fingerprint] = created
    return created


async def generate_chapter_with_prefix_cache(
    *,
    agent_context: str,
    prefix: str,
    turn: str,
    gemini_model: str,
    api_key: Optional[str],
    current_section_title: str,
    session_id: str | None,
    request_label: str,
    response_validator,
) -> tuple[str, dict[str, int]]:
    """Prova cached_content; se fallisce, invia prefix+turno (cache implicita)."""
    cache_name = resolve_writer_cache_name(
        model_name=gemini_model,
        system_prompt=agent_context,
        prefix=prefix,
        api_key=api_key,
    )
    if cache_name:
        try:
            client = build_google_genai_client(api_key=api_key)
            temperature = get_temperature_for_agent("writer_generator", gemini_model)
            config_kwargs: dict[str, Any] = {
                "cached_content": cache_name,
                "temperature": temperature,
                "max_output_tokens": get_max_output_tokens(gemini_model),
            }
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=gemini_model,
                contents=turn,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            text = (getattr(response, "text", None) or "").strip()
            if not text:
                raise ValueError("Risposta writer vuota dalla cache")
            text = response_validator(text)
            usage = getattr(response, "usage_metadata", None)
            input_tokens = 0
            output_tokens = 0
            if usage:
                input_tokens = int(
                    getattr(usage, "prompt_token_count", None)
                    or getattr(usage, "input_tokens", 0)
                    or 0
                )
                output_tokens = int(
                    getattr(usage, "candidates_token_count", None)
                    or getattr(usage, "output_tokens", 0)
                    or 0
                )
            token_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": gemini_model,
            }
            return text, token_usage
        except Exception as exc:
            logger.info(
                "Chiamata con cache fallita, fallback senza cache esplicita",
                context={"error": str(exc), "section": current_section_title},
            )

    llm = build_google_chat_model(
        model_name=gemini_model,
        api_key=api_key,
        temperature=get_temperature_for_agent("writer_generator", gemini_model),
        max_output_tokens=get_max_output_tokens(gemini_model),
    )
    return await invoke_chat_model(
        llm=llm,
        messages=[
            SystemMessage(content=agent_context),
            HumanMessage(content=f"{prefix}\n{turn}"),
        ],
        model_name=gemini_model,
        stage="chapter-generation",
        request_label=request_label,
        session_id=session_id,
        trace_recorder=LLMTraceRecorder(
            stage="chapter-generation",
            session_id=session_id,
            request_id=request_label,
        ),
        response_validator=response_validator,
    )

import os
import asyncio
import sys
from typing import Any, Optional, Dict

from google.genai import types

from app.core.config import get_literary_critic_config, normalize_critic_model_name
from app.core.logging import get_logger
from app.llm import (
    LLMTraceRecorder,
    build_google_genai_client,
    coerce_llm_content_to_text,
    get_google_backend_config,
    parse_json_model,
)
from app.llm.model_routing import ALLOWED_TEXT_MODELS, DEFAULT_TEXT_MODEL, map_book_model_name
from app.models import LiteraryCritique

logger = get_logger("literary-critic")


def _coerce_points_to_list(value: Any) -> list[str]:
    """Normalizza pros/cons a list[str]."""
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    if isinstance(value, str):
        lines = [ln.strip() for ln in value.splitlines()]
        cleaned: list[str] = []
        for ln in lines:
            ln = ln.lstrip("-•* ").strip()
            if ln:
                cleaned.append(ln)
        if not cleaned and value.strip():
            cleaned = [value.strip()]
        return cleaned
    s = str(value).strip()
    return [s] if s else []


def map_critic_model_name(use_fallback: bool = False, requested_model: Optional[str] = None) -> str:
    """Mappa e normalizza il nome del modello per il critico letterario."""
    cfg = get_literary_critic_config()
    if requested_model and not use_fallback:
        return map_book_model_name(requested_model)
    if use_fallback:
        fallback = cfg.get("fallback_model") or "gemini-3.5-flash-lite"
        if requested_model:
            mapped = map_book_model_name(requested_model)
            other = next((item for item in ALLOWED_TEXT_MODELS if item != mapped), fallback)
            return map_book_model_name(other)
        return map_book_model_name(fallback)
    model_name = requested_model or cfg.get("default_model") or DEFAULT_TEXT_MODEL
    return normalize_critic_model_name(model_name)


def _response_to_text(response: Any) -> str:
    """Best-effort per ottenere testo da una response (google-genai o langchain)."""
    if response is None:
        return ""
    
    # Supporto per risposte LangChain
    if hasattr(response, "content"):
        return coerce_llm_content_to_text(response.content).strip()
    
    # Supporto per risposte google-genai (comportamento esistente)
    txt = getattr(response, "text", None)
    if isinstance(txt, str) and txt.strip():
        return txt
    parts = getattr(response, "parts", None)
    if isinstance(parts, list):
        out: list[str] = []
        for p in parts:
            t = getattr(p, "text", None)
            if isinstance(t, str) and t.strip():
                out.append(t)
        return "\n".join(out).strip()
    
    return str(response)


def parse_critique_response(response_text: str) -> Dict[str, Any]:
    """
    Estrae la valutazione critica dalla risposta del LLM.
    
    Restituisce un dizionario con: score, pros, cons, summary
    """
    if not response_text or not response_text.strip():
        raise ValueError("Risposta del critico vuota.")

    try:
        critique = parse_json_model(response_text, LiteraryCritique)
    except ValueError as exc:
        if "Nessun" in str(exc):
            raise ValueError("Nessun JSON valido trovato nella risposta del critico.") from exc
        raise ValueError(f"JSON critica non valido: {exc}") from exc

    if not critique.summary.strip():
        raise ValueError("JSON critica privo di summary.")
    if not critique.pros:
        raise ValueError("JSON critica privo di punti di forza.")
    if not critique.cons:
        raise ValueError("JSON critica privo di punti di debolezza.")

    return critique.model_dump()


def _extract_token_usage_google_genai(response: Any, model_name: str) -> Dict[str, int]:
    """Estrae token usage dalla risposta google.genai."""
    token_usage = {"input_tokens": 0, "output_tokens": 0, "model": model_name}
    
    # google.genai risposta ha attributo usage_metadata
    usage = getattr(response, 'usage_metadata', None)
    if usage:
        token_usage["input_tokens"] = getattr(usage, 'prompt_token_count', 0) or 0
        token_usage["output_tokens"] = getattr(usage, 'candidates_token_count', 0) or 0
    
    return token_usage


def _resolve_provider_api_key(
    provider: str,
    *,
    api_key: Optional[str] = None,
    google_api_key: Optional[str] = None,
) -> Optional[str]:
    """Risolve la credenziale Gemini senza fallback cross-provider."""
    if provider == "google":
        return google_api_key or api_key or os.getenv("GOOGLE_API_KEY")
    return api_key


async def generate_literary_critique_from_pdf(
    title: str,
    author: str,
    pdf_bytes: bytes,
    api_key: Optional[str] = None,
    google_api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> tuple[Dict[str, Any], Dict[str, int]]:
    """
    Genera una valutazione critica usando come input il PDF finale del libro.

    Usa Gemini multimodale: il PDF viene inviato direttamente (google-genai).

    Returns:
        Tupla (critique_dict, token_usage)
        token_usage contiene {"input_tokens": int, "output_tokens": int, "model": str}
    """
    cfg = get_literary_critic_config()
    system_prompt = (cfg.get("system_prompt") or "").strip()
    user_prompt = (cfg.get("user_prompt") or "").strip()
    if not system_prompt:
        raise ValueError("Config critico mancante: system_prompt")
    if not user_prompt:
        raise ValueError("Config critico mancante: user_prompt")
    
    use_fallback = False
    max_retries = int(cfg.get("max_retries", 2))
    temperature = float(cfg.get("temperature", 0.3))
    response_mime_type = cfg.get("response_mime_type")

    trace = LLMTraceRecorder(stage="critique", request_id=title)

    for attempt in range(max_retries):
        try:
            active_model = map_critic_model_name(use_fallback, requested_model=model_name)
            provider = "google"
            trace.record(
                "critique_attempt_started",
                attempt=attempt + 1,
                provider=provider,
                model=active_model,
                use_fallback=use_fallback,
            )
            
            print(f"[LITERARY_CRITIC] ===== CRITICA LETTERARIA - TENTATIVO {attempt + 1}/{max_retries} =====", file=sys.stderr)
            print(f"[LITERARY_CRITIC] Modello configurato: {active_model}", file=sys.stderr)
            print(f"[LITERARY_CRITIC] Provider: GEMINI", file=sys.stderr)

            provider_api_key = _resolve_provider_api_key(
                provider,
                api_key=api_key,
                google_api_key=google_api_key,
            )
            backend = get_google_backend_config(api_key=provider_api_key)
            backend_label = "VERTEX AI (ADC)" if backend.provider == "vertex" else "GEMINI API KEY"
            print(
                f"[LITERARY_CRITIC] 🟢 USANDO GOOGLE - PDF diretto (multimodale) via {backend_label}",
                file=sys.stderr,
            )
            client = build_google_genai_client(api_key=provider_api_key)
            
            pdf_part = types.Part(
                inline_data=types.Blob(
                    mime_type="application/pdf",
                    data=pdf_bytes,
                )
            )
            
            config_obj = None
            if hasattr(types, "GenerateContentConfig"):
                kwargs: dict[str, Any] = {"temperature": temperature}
                if response_mime_type:
                    kwargs["response_mime_type"] = response_mime_type
                config_obj = types.GenerateContentConfig(**kwargs)

            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text=f"{system_prompt}\n\nTitolo: {title}\nAutore: {author}\n\n{user_prompt}"),
                        pdf_part,
                    ],
                )
            ]

            print(
                f"[LITERARY_CRITIC] Invio PDF diretto a Google GenAI ({backend.provider})...",
                file=sys.stderr,
            )
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=active_model,
                contents=contents,
                config=config_obj,
            )
            response_text = _response_to_text(response)
            
            # Estrai token usage per google.genai
            token_usage = _extract_token_usage_google_genai(response, active_model)
            trace.record(
                "critique_provider_response",
                attempt=attempt + 1,
                provider=provider,
                model=active_model,
                response_characters=len(response_text),
                token_usage=token_usage,
            )
            print(f"[LITERARY_CRITIC] Token usage: {token_usage['input_tokens']} input, {token_usage['output_tokens']} output", file=sys.stderr)
            print(f"[LITERARY_CRITIC] ✅ Risposta ricevuta da Gemini ({len(response_text)} caratteri)", file=sys.stderr)
            
            critique = parse_critique_response(response_text)
            trace.record(
                "critique_parsed",
                attempt=attempt + 1,
                provider=provider,
                model=active_model,
                critique=critique,
            )
            logger.info(
                "Critica letteraria generata con successo",
                context={
                    "provider": provider,
                    "model": active_model,
                    "trace_file": str(trace.file_path),
                },
            )
            print(f"[LITERARY_CRITIC] ✅ Critica generata con successo!", file=sys.stderr)
            print(f"[LITERARY_CRITIC] Score: {critique.get('score', 0)}/10", file=sys.stderr)
            print(f"[LITERARY_CRITIC] Pros: {len(critique.get('pros', []))} punti", file=sys.stderr)
            print(f"[LITERARY_CRITIC] Cons: {len(critique.get('cons', []))} punti", file=sys.stderr)
            print(f"[LITERARY_CRITIC] ===== CRITICA COMPLETATA =====", file=sys.stderr)
            return critique, token_usage

        except Exception as e:
            provider_name = provider if 'provider' in locals() else 'unknown'
            model_name_str = active_model if 'active_model' in locals() else 'unknown'
            trace.record(
                "critique_attempt_failed",
                attempt=attempt + 1,
                provider=provider_name,
                model=model_name_str,
                error_type=type(e).__name__,
                error=str(e),
            )
            print(f"[LITERARY_CRITIC] ❌ ERRORE con modello {model_name_str} (provider: {provider_name}): {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            
            if attempt < max_retries - 1:
                use_fallback = True
                print(f"[LITERARY_CRITIC] ⚠️ Retry con fallback model...", file=sys.stderr)
                continue
            print(f"[LITERARY_CRITIC] ❌ CRITICA FALLITA dopo {max_retries} tentativi", file=sys.stderr)
            raise

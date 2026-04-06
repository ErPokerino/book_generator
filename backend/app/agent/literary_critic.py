import os
import asyncio
import sys
from io import BytesIO
from typing import Any, Optional, Dict

from google import genai
from google.genai import types

from app.core.config import get_literary_critic_config, detect_critic_provider, normalize_critic_model_name
from app.core.logging import get_logger
from app.llm import (
    LLMTraceRecorder,
    coerce_llm_content_to_text,
    invoke_chat_model,
    parse_json_model,
)
from app.models import LiteraryCritique
from app.utils.token_tracker import extract_token_usage

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


def map_critic_model_name(use_fallback: bool = False) -> str:
    """Mappa e normalizza il nome del modello per il critico letterario."""
    cfg = get_literary_critic_config()
    if use_fallback:
        model_name = cfg.get("fallback_model", "gemini-3-flash-preview")
    else:
        model_name = cfg.get("default_model", "gemini-3.1-pro-preview")
    
    # Normalizza il nome del modello
    return normalize_critic_model_name(model_name)


def _response_to_text(response: Any) -> str:
    """Best-effort per ottenere testo da una response (google-genai o langchain)."""
    if response is None:
        return ""
    
    # Supporto per risposte LangChain OpenAI
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


def extract_text_from_pdf(pdf_bytes: bytes, max_chars: Optional[int] = None) -> str:
    """
    Estrae testo da un PDF per uso con OpenAI (che non supporta PDF direttamente).
    
    Args:
        pdf_bytes: Bytes del file PDF
        max_chars: Numero massimo di caratteri da estrarre (None = tutto)
                   Utile per rispettare limiti token (GPT-5.2: ~400k token ≈ ~1.6M caratteri)
    
    Returns:
        Testo estratto dal PDF
    
    Raises:
        ImportError: Se PyPDF2 non è installato
        ValueError: Se il PDF è vuoto o non valido
    """
    try:
        import PyPDF2
    except ImportError:
        raise ImportError(
            "PyPDF2 non è installato. Installa con: pip install PyPDF2 o uv add PyPDF2"
        )
    
    if not pdf_bytes or len(pdf_bytes) == 0:
        raise ValueError("PDF bytes vuoto")
    
    try:
        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        extracted_text = []
        total_chars = 0
        
        for page_num, page in enumerate(pdf_reader.pages, start=1):
            try:
                page_text = page.extract_text()
                if page_text:
                    page_text = page_text.strip()
                    if max_chars and total_chars + len(page_text) > max_chars:
                        # Tronca l'ultima pagina se necessario
                        remaining = max_chars - total_chars
                        if remaining > 0:
                            extracted_text.append(page_text[:remaining])
                            print(f"[PDF_EXTRACT] Testo troncato a {max_chars} caratteri (pagina {page_num})", file=sys.stderr)
                        break
                    
                    extracted_text.append(page_text)
                    total_chars += len(page_text)
            except Exception as e:
                print(f"[PDF_EXTRACT] Errore nell'estrazione pagina {page_num}: {e}", file=sys.stderr)
                continue
        
        full_text = "\n\n".join(extracted_text).strip()
        
        if not full_text:
            raise ValueError("Nessun testo estratto dal PDF. Il PDF potrebbe essere scannerizzato o protetto.")
        
        print(f"[PDF_EXTRACT] Estratti {len(full_text)} caratteri da {len(pdf_reader.pages)} pagine", file=sys.stderr)
        return full_text
    
    except Exception as e:
        print(f"[PDF_EXTRACT] ERRORE nell'estrazione testo PDF: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise ValueError(f"Errore nell'estrazione testo dal PDF: {str(e)}")


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
    openai_api_key: Optional[str] = None,
) -> Optional[str]:
    """Risolve la credenziale corretta per il provider senza contaminare fallback cross-provider."""
    if provider == "google":
        return google_api_key or api_key or os.getenv("GOOGLE_API_KEY")
    if provider == "openai":
        return openai_api_key or api_key or os.getenv("OPENAI_API_KEY")
    return api_key


async def generate_literary_critique_from_pdf(
    title: str,
    author: str,
    pdf_bytes: bytes,
    api_key: Optional[str] = None,
    google_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> tuple[Dict[str, Any], Dict[str, int]]:
    """
    Genera una valutazione critica usando come input il PDF finale del libro.
    
    Supporta due provider:
    - Gemini: PDF diretto (multimodale) - comportamento originale
    - OpenAI: Estrazione testo dal PDF - per modelli GPT che non supportano PDF direttamente
    
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
    
    # Limite caratteri per OpenAI (400k token ≈ ~1.6M caratteri, usiamo ~1.5M per sicurezza)
    MAX_TEXT_CHARS_OPENAI = 1500000  # ~375k token (sotto il limite di 400k)

    trace = LLMTraceRecorder(stage="critique", request_id=title)

    for attempt in range(max_retries):
        try:
            model_name = map_critic_model_name(use_fallback)
            provider = detect_critic_provider(model_name)
            trace.record(
                "critique_attempt_started",
                attempt=attempt + 1,
                provider=provider,
                model=model_name,
                use_fallback=use_fallback,
            )
            
            print(f"[LITERARY_CRITIC] ===== CRITICA LETTERARIA - TENTATIVO {attempt + 1}/{max_retries} =====", file=sys.stderr)
            print(f"[LITERARY_CRITIC] Modello configurato: {model_name}", file=sys.stderr)
            print(f"[LITERARY_CRITIC] Provider rilevato: {provider.upper()}", file=sys.stderr)
            
            if provider == "google":
                # Comportamento originale: PDF diretto con Gemini
                print(f"[LITERARY_CRITIC] 🟢 USANDO GEMINI - PDF diretto (multimodale)", file=sys.stderr)
                provider_api_key = _resolve_provider_api_key(
                    provider,
                    api_key=api_key,
                    google_api_key=google_api_key,
                    openai_api_key=openai_api_key,
                )

                if not provider_api_key:
                    raise ValueError("GOOGLE_API_KEY non configurata. Imposta la variabile d'ambiente o passa api_key.")

                print(f"[LITERARY_CRITIC] API Key Google trovata: {'Sì' if provider_api_key else 'No'}", file=sys.stderr)
                client = genai.Client(api_key=provider_api_key)
                
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

                print(f"[LITERARY_CRITIC] Invio PDF diretto a Gemini API (multimodale)...", file=sys.stderr)
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=contents,
                    config=config_obj,
                )
                response_text = _response_to_text(response)
                
                # Estrai token usage per google.genai
                token_usage = _extract_token_usage_google_genai(response, model_name)
                trace.record(
                    "critique_provider_response",
                    attempt=attempt + 1,
                    provider=provider,
                    model=model_name,
                    response_characters=len(response_text),
                    token_usage=token_usage,
                )
                print(f"[LITERARY_CRITIC] Token usage: {token_usage['input_tokens']} input, {token_usage['output_tokens']} output", file=sys.stderr)
                print(f"[LITERARY_CRITIC] ✅ Risposta ricevuta da Gemini ({len(response_text)} caratteri)", file=sys.stderr)
                
            elif provider == "openai":
                # OpenAI: estrae testo dal PDF
                print(f"[LITERARY_CRITIC] 🔵 USANDO OPENAI (GPT) - Estrazione testo da PDF", file=sys.stderr)
                try:
                    from langchain_openai import ChatOpenAI
                    from langchain_core.messages import SystemMessage, HumanMessage
                except ImportError:
                    raise ImportError(
                        "langchain-openai non è installato. Installa con: pip install langchain-openai o uv add langchain-openai"
                    )
                
                provider_api_key = _resolve_provider_api_key(
                    provider,
                    api_key=api_key,
                    google_api_key=google_api_key,
                    openai_api_key=openai_api_key,
                )

                if not provider_api_key:
                    raise ValueError("OPENAI_API_KEY non configurata. Imposta la variabile d'ambiente o passa api_key.")

                print(f"[LITERARY_CRITIC] API Key OpenAI trovata: {'Sì' if provider_api_key else 'No'}", file=sys.stderr)
                
                # Estrai testo dal PDF
                print(f"[LITERARY_CRITIC] Estrazione testo da PDF per OpenAI (max {MAX_TEXT_CHARS_OPENAI:,} caratteri)...", file=sys.stderr)
                pdf_text = extract_text_from_pdf(pdf_bytes, max_chars=MAX_TEXT_CHARS_OPENAI)
                print(f"[LITERARY_CRITIC] Testo estratto: {len(pdf_text):,} caratteri da PDF", file=sys.stderr)
                
                # Crea prompt completo con testo estratto
                # Per OpenAI, includiamo tutto nel user_prompt perché non supporta PDF multimodale
                full_user_prompt = f"""Titolo: {title}
Autore: {author}

Testo completo del libro (estratto dal PDF):

{pdf_text}

{user_prompt}"""
                
                # Usa ChatOpenAI da LangChain
                # Se response_mime_type è "application/json", usa JSON mode per OpenAI
                model_kwargs = {}
                if response_mime_type == "application/json":
                    # GPT-5.2 e altri modelli OpenAI supportano JSON mode
                    model_kwargs["response_format"] = {"type": "json_object"}
                    print(f"[LITERARY_CRITIC] Modalità JSON abilitata per OpenAI", file=sys.stderr)
                    # Assicurati che il prompt chieda esplicitamente JSON
                    if "JSON" not in full_user_prompt.upper() and "json" not in full_user_prompt.lower():
                        full_user_prompt = f"{full_user_prompt}\n\nIMPORTANTE: Restituisci SOLO un JSON valido, senza testo aggiuntivo."
                
                print(f"[LITERARY_CRITIC] Invio richiesta a OpenAI API (modello: {model_name}, temperature: {temperature})...", file=sys.stderr)
                llm = ChatOpenAI(
                    model=model_name,
                    openai_api_key=provider_api_key,
                    temperature=temperature,
                    max_tokens=4096,  # Output sufficiente per critica JSON
                    model_kwargs=model_kwargs if model_kwargs else None,
                )
                
                # Genera critica con system message e user message contenente tutto il testo
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=full_user_prompt),
                ]

                response_text, token_usage = await invoke_chat_model(
                    llm=llm,
                    messages=messages,
                    model_name=model_name,
                    stage="critique",
                    request_label=f"critique-openai-{title}",
                    trace_recorder=trace,
                    max_retries=1,
                )
                print(f"[LITERARY_CRITIC] Token usage: {token_usage['input_tokens']} input, {token_usage['output_tokens']} output", file=sys.stderr)
                print(f"[LITERARY_CRITIC] ✅ Risposta ricevuta da OpenAI ({len(response_text)} caratteri)", file=sys.stderr)
                
            else:
                raise ValueError(f"Provider non supportato: {provider}")
            
            # Parse risposta (comune per entrambi i provider)
            critique = parse_critique_response(response_text)
            trace.record(
                "critique_parsed",
                attempt=attempt + 1,
                provider=provider,
                model=model_name,
                critique=critique,
            )
            logger.info(
                "Critica letteraria generata con successo",
                context={
                    "provider": provider,
                    "model": model_name,
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
            model_name_str = model_name if 'model_name' in locals() else 'unknown'
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


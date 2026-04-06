"""Runtime condiviso per invocazioni LLM con retry, token tracking e tracing."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.core.config import get_app_config
from app.core.logging import get_logger
from app.llm.model_routing import get_structured_output_method
from app.llm.structured_outputs import coerce_llm_content_to_text
from app.llm.tracing import LLMTraceRecorder
from app.utils.token_tracker import extract_token_usage

DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_RETRY_DELAY_SECONDS = 5
DEFAULT_MAX_RETRIES = 3
DEFAULT_STRUCTURED_REPAIR_ATTEMPTS = 1

StructuredPayloadT = TypeVar("StructuredPayloadT", bound=BaseModel)

RETRYABLE_EXCEPTIONS = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    ConnectionError,
    TimeoutError,
)


class StructuredOutputValidationError(ValueError):
    """Errore applicativo per output nativo strutturato non parsabile o semanticamente invalido."""

    def __init__(
        self,
        message: str,
        *,
        raw_text: str = "",
        parsing_error: Exception | None = None,
        token_usage: dict[str, int] | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_text = raw_text
        self.parsing_error = parsing_error
        self.token_usage = token_usage or {}


def is_retryable_llm_error(error: Exception) -> bool:
    """Riconosce errori di rete o transient failure su cui ha senso fare retry."""
    if isinstance(error, RETRYABLE_EXCEPTIONS):
        return True
    error_message = str(error).lower()
    retryable_patterns = [
        "timeout",
        "timed out",
        "connection",
        "connect",
        "read timeout",
        "ssl",
        "tls",
        "handshake",
        "network",
        "socket",
        "eof",
        "reset",
        "rate limit",
        "temporarily unavailable",
    ]
    return any(pattern in error_message for pattern in retryable_patterns)


def _get_structured_output_retry_settings() -> dict[str, int]:
    retry_settings = get_app_config().get("retry", {}).get("structured_output", {})
    return {
        "max_retries": int(retry_settings.get("max_retries", 2)),
        "repair_attempts": int(retry_settings.get("repair_attempts", DEFAULT_STRUCTURED_REPAIR_ATTEMPTS)),
        "base_delay_seconds": int(retry_settings.get("base_delay_seconds", 2)),
    }


def build_google_chat_model(
    *,
    model_name: str,
    api_key: str,
    temperature: float,
    max_output_tokens: int | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> ChatGoogleGenerativeAI:
    """Costruisce il client LangChain Gemini con configurazione uniforme."""
    kwargs: dict[str, Any] = {
        "model": model_name,
        "google_api_key": api_key,
        "temperature": temperature,
        "timeout": timeout_seconds,
    }
    if max_output_tokens is not None:
        kwargs["max_output_tokens"] = max_output_tokens
    return ChatGoogleGenerativeAI(**kwargs)


def _preview_or_omit(trace: LLMTraceRecorder, text: str, *, preview_kind: str) -> str | None:
    preview = trace.preview_text(text, preview_kind=preview_kind)
    return preview if preview else None


def _summarize_messages(
    messages: list[Any],
    *,
    trace: LLMTraceRecorder,
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        content = getattr(message, "content", message)
        text = coerce_llm_content_to_text(content)
        item = {
            "index": index,
            "type": type(message).__name__,
            "characters": len(text),
        }
        preview = _preview_or_omit(trace, text, preview_kind="message")
        if preview is not None:
            item["preview"] = preview
        summary.append(item)
    return summary


def _format_messages_for_repair(messages: list[Any]) -> str:
    chunks: list[str] = []
    for index, message in enumerate(messages, start=1):
        content = coerce_llm_content_to_text(getattr(message, "content", message)).strip()
        if not content:
            continue
        message_type = type(message).__name__
        chunks.append(f"## Messaggio {index} ({message_type})\n{content[:6000]}")
    return "\n\n".join(chunks)


def _merge_token_usage(*entries: dict[str, int]) -> dict[str, int]:
    merged = {"input_tokens": 0, "output_tokens": 0}
    model_name = ""
    for entry in entries:
        if not entry:
            continue
        merged["input_tokens"] += int(entry.get("input_tokens", 0))
        merged["output_tokens"] += int(entry.get("output_tokens", 0))
        model_name = entry.get("model", model_name)
    if model_name:
        merged["model"] = model_name
    return merged


def _accumulate_token_usage(
    running_total: dict[str, int],
    increment: dict[str, int] | None,
    *,
    model_name: str,
) -> dict[str, int]:
    return _merge_token_usage(
        running_total,
        increment or {"input_tokens": 0, "output_tokens": 0, "model": model_name},
        {"input_tokens": 0, "output_tokens": 0, "model": model_name},
    )


async def _repair_structured_output(
    *,
    llm: Any,
    schema: type[StructuredPayloadT],
    messages: list[Any],
    invalid_raw_text: str,
    model_name: str,
    stage: str,
    request_label: str,
    trace: LLMTraceRecorder,
    method: str,
    parsed_validator: Callable[[StructuredPayloadT], StructuredPayloadT] | None = None,
) -> tuple[StructuredPayloadT, dict[str, int], str]:
    structured_llm = llm.with_structured_output(
        schema,
        method=method,
        include_raw=True,
    )
    repair_messages = [
        SystemMessage(
            content=(
                "Ripara un output strutturato generato in precedenza. "
                "Non aggiungere spiegazioni: ricostruisci esclusivamente il contenuto richiesto."
            )
        ),
        HumanMessage(
            content=(
                "Il seguente output non ha rispettato lo schema richiesto.\n\n"
                "## Task originale\n"
                f"{_format_messages_for_repair(messages)}\n\n"
                "## Output invalido da correggere\n"
                f"{invalid_raw_text or '[vuoto]'}\n\n"
                "Ricostruisci un payload valido che preservi l'intento dell'output originale."
            )
        ),
    ]
    result = await structured_llm.ainvoke(repair_messages)
    raw_response = result.get("raw") if isinstance(result, dict) else None
    parsed = result.get("parsed") if isinstance(result, dict) else result
    parsing_error = result.get("parsing_error") if isinstance(result, dict) else None
    raw_text = coerce_llm_content_to_text(getattr(raw_response, "content", raw_response)).strip()
    token_usage = extract_token_usage(raw_response if raw_response is not None else result)
    token_usage["model"] = model_name
    if parsing_error or parsed is None:
        raise StructuredOutputValidationError(
            f"Repair structured output fallito per {request_label}",
            raw_text=raw_text,
            parsing_error=parsing_error,
            token_usage=token_usage,
        )
    if parsed_validator:
        try:
            parsed = parsed_validator(parsed)
        except Exception as validation_error:
            raise StructuredOutputValidationError(
                f"Validazione semantica del repair fallita per {request_label}: {validation_error}",
                raw_text=raw_text,
                parsing_error=validation_error,
                token_usage=token_usage,
            ) from validation_error
    trace.record(
        "structured_repair_attempt_succeeded",
        stage=stage,
        request_label=request_label,
        token_usage=token_usage,
        repaired_response_characters=len(raw_text),
        repaired_response_preview=_preview_or_omit(trace, raw_text, preview_kind="response"),
    )
    return parsed, token_usage, raw_text


async def invoke_chat_model(
    *,
    llm: Any,
    messages: list[Any],
    model_name: str,
    stage: str,
    request_label: str,
    session_id: str | None = None,
    trace_recorder: LLMTraceRecorder | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SECONDS,
    response_validator: Callable[[str], str] | None = None,
) -> tuple[str, dict[str, int]]:
    """Invoca un client LangChain con retry, tracing e token tracking coerenti."""
    trace = trace_recorder or LLMTraceRecorder(
        stage=stage,
        session_id=session_id,
        request_id=request_label,
    )
    logger = get_logger("llm-runtime", stage=stage, request=request_label)

    trace.record(
        "invocation_started",
        model=model_name,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay_seconds,
        messages=_summarize_messages(messages, trace=trace),
    )

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(messages)
            response_text = coerce_llm_content_to_text(getattr(response, "content", response)).strip()
            if response_validator:
                response_text = response_validator(response_text)
            elif not response_text:
                raise ValueError(f"Risposta vuota per {request_label}")

            token_usage = extract_token_usage(response)
            token_usage["model"] = model_name
            response_preview = _preview_or_omit(trace, response_text, preview_kind="response")
            trace.record(
                "invocation_succeeded",
                attempt=attempt + 1,
                token_usage=token_usage,
                response_characters=len(response_text),
                response_preview=response_preview,
            )
            if attempt > 0:
                logger.info(
                    "Invocazione LLM riuscita dopo retry",
                    context={"attempt": attempt + 1, "trace_file": str(trace.file_path)},
                )
            return response_text, token_usage
        except Exception as exc:  # pragma: no cover - exercise via unit tests and runtime
            last_error = exc
            retryable = is_retryable_llm_error(exc)
            trace.record(
                "invocation_failed",
                attempt=attempt + 1,
                retryable=retryable,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            if retryable and attempt < max_retries - 1:
                delay = retry_delay_seconds * (attempt + 1)
                logger.warning(
                    "Invocazione LLM fallita, riprovo",
                    context={
                        "attempt": attempt + 1,
                        "delay_seconds": delay,
                        "error_type": type(exc).__name__,
                        "trace_file": str(trace.file_path),
                    },
                )
                await asyncio.sleep(delay)
                continue

            logger.exception(
                "Invocazione LLM fallita in modo definitivo",
                context={
                    "attempt": attempt + 1,
                    "retryable": retryable,
                    "trace_file": str(trace.file_path),
                },
            )
            raise

    raise last_error if last_error else RuntimeError(f"Invocazione fallita per {request_label}")


async def invoke_structured_chat_model(
    *,
    llm: Any,
    schema: type[StructuredPayloadT],
    messages: list[Any],
    model_name: str,
    stage: str,
    request_label: str,
    session_id: str | None = None,
    trace_recorder: LLMTraceRecorder | None = None,
    max_retries: int | None = None,
    retry_delay_seconds: int | None = None,
    repair_attempts: int | None = None,
    method: str | None = None,
    parsed_validator: Callable[[StructuredPayloadT], StructuredPayloadT] | None = None,
) -> tuple[StructuredPayloadT, dict[str, int], str]:
    """Invoca un modello Gemini con structured output nativo e repair loop bounded."""
    trace = trace_recorder or LLMTraceRecorder(
        stage=stage,
        session_id=session_id,
        request_id=request_label,
    )
    logger = get_logger("llm-runtime", stage=stage, request=request_label)
    retry_settings = _get_structured_output_retry_settings()
    effective_max_retries = max_retries if max_retries is not None else retry_settings["max_retries"]
    effective_retry_delay = (
        retry_delay_seconds
        if retry_delay_seconds is not None
        else retry_settings["base_delay_seconds"]
    )
    effective_repair_attempts = (
        repair_attempts
        if repair_attempts is not None
        else retry_settings["repair_attempts"]
    )
    structured_method = method or get_structured_output_method()
    structured_llm = llm.with_structured_output(
        schema,
        method=structured_method,
        include_raw=True,
    )

    trace.record(
        "structured_invocation_started",
        model=model_name,
        schema=schema.__name__,
        method=structured_method,
        max_retries=effective_max_retries,
        retry_delay_seconds=effective_retry_delay,
        repair_attempts=effective_repair_attempts,
        messages=_summarize_messages(messages, trace=trace),
    )

    last_error: Exception | None = None
    accumulated_token_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "model": model_name,
    }
    for attempt in range(effective_max_retries):
        try:
            result = await structured_llm.ainvoke(messages)
            raw_response = result.get("raw") if isinstance(result, dict) else None
            parsed = result.get("parsed") if isinstance(result, dict) else result
            parsing_error = result.get("parsing_error") if isinstance(result, dict) else None
            raw_text = coerce_llm_content_to_text(getattr(raw_response, "content", raw_response)).strip()
            token_usage = extract_token_usage(raw_response if raw_response is not None else result)
            token_usage["model"] = model_name
            accumulated_token_usage = _accumulate_token_usage(
                accumulated_token_usage,
                token_usage,
                model_name=model_name,
            )

            if parsing_error or parsed is None:
                raise StructuredOutputValidationError(
                    f"Structured output non valido per {request_label}",
                    raw_text=raw_text,
                    parsing_error=parsing_error,
                    token_usage=token_usage,
                )
            if parsed_validator:
                try:
                    parsed = parsed_validator(parsed)
                except Exception as validation_error:
                    raise StructuredOutputValidationError(
                        f"Validazione semantica fallita per {request_label}: {validation_error}",
                        raw_text=raw_text,
                        parsing_error=validation_error,
                        token_usage=token_usage,
                    ) from validation_error

            trace.record(
                "structured_invocation_succeeded",
                attempt=attempt + 1,
                schema=schema.__name__,
                token_usage=accumulated_token_usage,
                raw_response_characters=len(raw_text),
                raw_response_preview=_preview_or_omit(trace, raw_text, preview_kind="response"),
            )
            if attempt > 0:
                logger.info(
                    "Structured invocation riuscita dopo retry",
                    context={"attempt": attempt + 1, "trace_file": str(trace.file_path)},
                )
            return parsed, accumulated_token_usage, raw_text
        except StructuredOutputValidationError as exc:
            last_error = exc
            trace.record(
                "structured_invocation_parse_failed",
                attempt=attempt + 1,
                schema=schema.__name__,
                error_type=type(exc).__name__,
                error=str(exc),
                raw_response_preview=_preview_or_omit(trace, exc.raw_text, preview_kind="response"),
            )
            if effective_repair_attempts > 0:
                for repair_index in range(effective_repair_attempts):
                    try:
                        repaired_payload, repair_token_usage, repaired_raw_text = await _repair_structured_output(
                            llm=llm,
                            schema=schema,
                            messages=messages,
                            invalid_raw_text=exc.raw_text,
                            model_name=model_name,
                            stage=stage,
                            request_label=request_label,
                            trace=trace,
                            method=structured_method,
                            parsed_validator=parsed_validator,
                        )
                        accumulated_token_usage = _accumulate_token_usage(
                            accumulated_token_usage,
                            repair_token_usage,
                            model_name=model_name,
                        )
                        trace.record(
                            "structured_repair_completed",
                            attempt=attempt + 1,
                            repair_attempt=repair_index + 1,
                            schema=schema.__name__,
                            token_usage=accumulated_token_usage,
                            repaired_response_characters=len(repaired_raw_text),
                        )
                        return repaired_payload, accumulated_token_usage, repaired_raw_text or exc.raw_text
                    except Exception as repair_exc:  # pragma: no cover - exercised by unit tests
                        last_error = repair_exc
                        if isinstance(repair_exc, StructuredOutputValidationError):
                            accumulated_token_usage = _accumulate_token_usage(
                                accumulated_token_usage,
                                repair_exc.token_usage,
                                model_name=model_name,
                            )
                        trace.record(
                            "structured_repair_failed",
                            attempt=attempt + 1,
                            repair_attempt=repair_index + 1,
                            schema=schema.__name__,
                            error_type=type(repair_exc).__name__,
                            error=str(repair_exc),
                        )

            if attempt < effective_max_retries - 1:
                delay = effective_retry_delay * (attempt + 1)
                logger.warning(
                    "Structured invocation non valida, riprovo",
                    context={
                        "attempt": attempt + 1,
                        "delay_seconds": delay,
                        "trace_file": str(trace.file_path),
                    },
                )
                await asyncio.sleep(delay)
                continue

            logger.exception(
                "Structured invocation fallita in modo definitivo",
                context={
                    "attempt": attempt + 1,
                    "schema": schema.__name__,
                    "trace_file": str(trace.file_path),
                },
            )
            raise last_error if last_error else exc
        except Exception as exc:  # pragma: no cover - exercised via unit tests and runtime
            last_error = exc
            retryable = is_retryable_llm_error(exc)
            trace.record(
                "structured_invocation_failed",
                attempt=attempt + 1,
                retryable=retryable,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            if retryable and attempt < effective_max_retries - 1:
                delay = effective_retry_delay * (attempt + 1)
                logger.warning(
                    "Structured invocation fallita, riprovo",
                    context={
                        "attempt": attempt + 1,
                        "delay_seconds": delay,
                        "error_type": type(exc).__name__,
                        "trace_file": str(trace.file_path),
                    },
                )
                await asyncio.sleep(delay)
                continue

            logger.exception(
                "Structured invocation fallita in modo definitivo",
                context={
                    "attempt": attempt + 1,
                    "retryable": retryable,
                    "trace_file": str(trace.file_path),
                },
            )
            raise

    raise last_error if last_error else RuntimeError(f"Structured invocation fallita per {request_label}")

"""Helper per contratti JSON e parsing tipizzato delle risposte LLM."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

TModel = TypeVar("TModel", bound=BaseModel)


def coerce_llm_content_to_text(content: Any) -> str:
    """Normalizza contenuti LangChain/Gemini/OpenAI in una stringa."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if item is None:
                continue
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text_value = item.get("text")
                parts.append(text_value if isinstance(text_value, str) else str(item))
                continue
            text_attr = getattr(item, "text", None)
            if isinstance(text_attr, str):
                parts.append(text_attr)
            else:
                parts.append(str(item))
        return "\n".join(parts)
    text_attr = getattr(content, "text", None)
    if isinstance(text_attr, str):
        return text_attr
    return str(content)


def extract_first_json_value(
    response_text: str,
    *,
    expected_type: type | tuple[type, ...] = dict,
) -> Any:
    """Estrae il primo payload JSON valido anche se racchiuso in prose o code fences."""
    if not response_text or not response_text.strip():
        raise ValueError("Risposta JSON vuota.")

    candidate_blocks: list[str] = []
    stripped_text = response_text.strip()
    opening_token = "{" if expected_type is dict else "["
    closing_token = "}" if expected_type is dict else "]"
    if stripped_text.startswith(opening_token) and stripped_text.endswith(closing_token):
        candidate_blocks.append(stripped_text)

    fence_marker = "```"
    if fence_marker in response_text:
        segments = response_text.split(fence_marker)
        for index, segment in enumerate(segments):
            if index % 2 != 1:
                continue
            cleaned = segment.strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            if cleaned:
                candidate_blocks.append(cleaned)

    decoder = json.JSONDecoder()

    def _decode(candidate: str) -> Any | None:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, expected_type):
                return parsed
        except json.JSONDecodeError:
            return None
        return None

    for candidate in candidate_blocks:
        parsed = _decode(candidate)
        if parsed is not None:
            return parsed

    for start_index, char in enumerate(response_text):
        if char not in "{[":
            continue
        try:
            parsed, _ = decoder.raw_decode(response_text[start_index:])
            if isinstance(parsed, expected_type):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError("Nessun payload JSON valido trovato nella risposta.")


def parse_json_model(response_text: str, model_cls: type[TModel]) -> TModel:
    """Valida il primo oggetto JSON trovato contro un modello Pydantic."""
    payload = extract_first_json_value(response_text, expected_type=dict)
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"JSON non conforme a {model_cls.__name__}: {exc}") from exc


def build_json_schema_prompt(
    model_cls: type[BaseModel],
    *,
    intro: str = "Restituisci SOLO JSON valido conforme al seguente schema.",
) -> str:
    """Genera istruzioni riutilizzabili per imporre un contratto JSON al modello."""
    schema = model_cls.model_json_schema()
    schema_text = json.dumps(schema, ensure_ascii=False, indent=2)
    return (
        f"{intro}\n"
        "- Non aggiungere testo introduttivo o conclusivo.\n"
        "- Non usare markdown code fences.\n"
        "- Compila tutti i campi richiesti.\n"
        "- Se un campo testuale opzionale non serve, usa stringa vuota.\n"
        "- Se un campo lista non serve, usa una lista vuota.\n\n"
        f"Schema JSON:\n{schema_text}"
    )

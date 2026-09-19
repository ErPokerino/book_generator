from typing import Optional
import re

from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import get_temperature_for_agent
from app.core.logging import get_logger
from app.llm import (
    LLMTraceRecorder,
    OutlineGenerationPayload,
    OutlineSectionPayload,
    append_contract_instructions,
    build_google_chat_model,
    compose_prompt_files,
    get_stage_model,
    invoke_structured_chat_model,
    parse_json_model,
)
from app.models import SubmissionRequest, QuestionAnswer


logger = get_logger("outline-generator")

_HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_METADATA_HEADINGS = {
    "eventi chiave",
    "focus personaggi",
    "atmosfera e temi",
    "atmosfera",
    "temi",
    "collegamenti narrativi",
    "collegamenti",
    "dettaglio",
    "note",
}


def sanitize_outline_description(text: str) -> str:
    """Evita che le note di un capitolo vengano parsate come nuovi heading markdown."""
    if not text:
        return text
    lines: list[str] = []
    for raw in text.splitlines():
        match = _HEADING_LINE.match(raw.strip())
        if match:
            lines.append(f"**{match.group(2).strip()}**")
            continue
        lines.append(raw)
    return "\n".join(lines).strip()


def expand_nested_outline_section(section: OutlineSectionPayload) -> list[OutlineSectionPayload]:
    """Estrae heading markdown annidati nella description e li promuove a sezioni."""
    preface: list[str] = []
    nested: list[OutlineSectionPayload] = []
    current_title: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_body
        if not current_title:
            return
        nested.append(
            OutlineSectionPayload(
                title=current_title,
                description=sanitize_outline_description("\n".join(current_body)) or current_title,
                level=max(int(section.level) + 1, 3),
            )
        )
        current_title = None
        current_body = []

    for raw in (section.description or "").splitlines():
        match = _HEADING_LINE.match(raw.strip())
        if not match:
            if current_title:
                current_body.append(raw)
            else:
                preface.append(raw)
            continue
        title = match.group(2).strip()
        if title.lower() in _METADATA_HEADINGS:
            formatted = f"**{title}**"
            if current_title:
                current_body.append(formatted)
            else:
                preface.append(formatted)
            continue
        flush()
        current_title = title
    flush()

    parent_description = sanitize_outline_description("\n".join(preface)) or section.title
    parent = OutlineSectionPayload(
        title=section.title,
        description=parent_description,
        level=section.level,
    )
    if not nested:
        return [parent]
    return [parent, *nested]


def normalize_outline_payload(payload: OutlineGenerationPayload) -> OutlineGenerationPayload:
    expanded: list[OutlineSectionPayload] = []
    for section in payload.sections:
        expanded.extend(expand_nested_outline_section(section))
    return OutlineGenerationPayload(sections=expanded)


def _validate_outline_payload(payload: OutlineGenerationPayload) -> OutlineGenerationPayload:
    if not payload.sections:
        raise ValueError("Outline privo di sezioni.")
    return normalize_outline_payload(payload)


def load_outline_agent_context() -> str:
    """Carica mestiere condiviso e istruzioni dell'outline."""
    return compose_prompt_files(
        "narrative_craft.md",
        "outline_agent_context.md",
        agent_label="outline generator",
        anchor_file=__file__,
    )


def format_input_for_outline(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str] = None,
) -> str:
    """Formatta tutti i dati di input per il prompt dell'agente di outline."""
    lines = ["# Materiale per la struttura\n"]
    lines.append("La bozza validata ha priorità sul form iniziale se i due divergono.\n")
    lines.append("## Bozza validata")
    if draft_title:
        lines.append(f"**Titolo**: {draft_title}\n")
    lines.append(validated_draft)
    lines.append("\n---\n")
    lines.append("## Form iniziale (contesto)")
    lines.append(f"**Trama iniziale**: {form_data.plot}")
    
    optional_fields = {
        "Nome Autore": form_data.user_name,
        "Genere": form_data.genre,
        "Sottogenere": form_data.subgenre,
        "Pubblico di Riferimento": form_data.target_audience,
        "Tema": form_data.theme,
        "Protagonista": form_data.protagonist,
        "Archetipo Protagonista": form_data.protagonist_archetype,
        "Arco del personaggio": form_data.character_arc,
        "Punto di vista": form_data.point_of_view,
        "Voce narrante": form_data.narrative_voice,
        "Stile": form_data.style,
        "Struttura temporale": form_data.temporal_structure,
        "Ritmo": form_data.pace,
        "Realismo": form_data.realism,
        "Ambiguità": form_data.ambiguity,
        "Intenzionalità": form_data.intentionality,
        "Autore di riferimento": form_data.author,
    }
    
    for label, value in optional_fields.items():
        if value:
            lines.append(f"**{label}**: {value}")
    
    if question_answers:
        lines.append("\n**Risposte alle domande preliminari:**")
        for qa in question_answers:
            if qa.answer:
                lines.append(f"- {qa.answer}")
    
    return "\n".join(lines)


def render_outline_markdown(payload: OutlineGenerationPayload) -> str:
    """Rende l'outline strutturato in markdown per UI e parser legacy."""
    normalized = normalize_outline_payload(payload)
    lines: list[str] = []
    for section in normalized.sections:
        header_prefix = "#" * section.level
        lines.append(f"{header_prefix} {section.title.strip()}")
        lines.append("")
        description = sanitize_outline_description(section.description.strip())
        if description:
            lines.append(description)
            lines.append("")
    outline_text = "\n".join(lines).strip()
    if not outline_text:
        raise ValueError("Outline vuoto dopo il rendering markdown.")
    return outline_text


async def generate_outline(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    session_id: str,
    draft_title: Optional[str] = None,
    api_key: Optional[str] = None,
    existing_outline: Optional[str] = None,
) -> tuple[str, dict[str, int]]:
    """
    Restituisce l'indice già prodotto col piano, o lo genera per sessioni legacy.
    """
    stored = (existing_outline or "").strip()
    if stored:
        logger.info(
            "Outline riutilizzato dal piano già salvato",
            context={"session_id": session_id, "characters": len(stored)},
        )
        return stored, {"input_tokens": 0, "output_tokens": 0, "model": "cached-plan"}

    agent_context = load_outline_agent_context()
    formatted_input = format_input_for_outline(
        form_data,
        question_answers,
        validated_draft,
        draft_title,
    )
    system_prompt = SystemMessage(
        content=append_contract_instructions(
            agent_context,
            (
                "IMPORTANTE: il runtime applica uno schema strutturato nativo. "
                "Non restituire markdown libero o wrapper extra: compila soltanto la struttura semantica richiesta."
            ),
        )
    )
    user_prompt_content = f"""Genera la struttura completa del romanzo.

{formatted_input}

Restituisci JSON: sezioni ordinate con `title`, `description`, `level`. Segui le regole di granularità del system prompt."""

    user_prompt = HumanMessage(content=user_prompt_content)
    gemini_model = get_stage_model("outline", form_data.llm_model, form_data=form_data)
    temperature = get_temperature_for_agent("outline_generator", gemini_model)
    trace = LLMTraceRecorder(
        stage="outline",
        session_id=session_id,
        request_id="generate-outline",
    )
    llm = build_google_chat_model(
        model_name=gemini_model,
        api_key=api_key,
        temperature=temperature,
    )

    payload, token_usage, _raw_output = await invoke_structured_chat_model(
        llm=llm,
        schema=OutlineGenerationPayload,
        messages=[system_prompt, user_prompt],
        model_name=gemini_model,
        stage="outline",
        request_label="generate outline",
        session_id=session_id,
        trace_recorder=trace,
        parsed_validator=_validate_outline_payload,
    )
    outline_text = render_outline_markdown(payload)
    trace.record(
        "outline_rendered",
        sections=len(payload.sections),
        markdown_characters=len(outline_text),
    )
    logger.info(
        "Outline generato con successo",
        context={
            "session_id": session_id,
            "sections": len(payload.sections),
            "model": gemini_model,
            "trace_file": str(trace.file_path),
        },
    )
    return outline_text, token_usage



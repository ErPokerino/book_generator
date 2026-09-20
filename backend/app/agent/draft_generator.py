from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.outline_generator import render_outline_markdown
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async
from app.core.config import get_temperature_for_agent
from app.core.logging import get_logger
from app.llm import (
    DraftGenerationPayload,
    LLMTraceRecorder,
    OutlineGenerationPayload,
    append_contract_instructions,
    build_google_chat_model,
    compose_prompt_files,
    get_stage_model,
    invoke_structured_chat_model,
    load_prompt_file,
    parse_json_model,
)
from app.models import SubmissionRequest, QuestionAnswer


logger = get_logger("draft-generator")


def load_draft_agent_context() -> str:
    """Carica mestiere condiviso e istruzioni della bozza."""
    return compose_prompt_files(
        "narrative_craft.md",
        "draft_agent_context.md",
        agent_label="draft generator",
        anchor_file=__file__,
    )


def load_draft_plan_context() -> str:
    """Prompt unico: bozza estesa e indice nello stesso JSON."""
    return compose_prompt_files(
        "narrative_craft.md",
        "draft_agent_context.md",
        "outline_agent_context.md",
        agent_label="draft generator",
        anchor_file=__file__,
    )


def load_draft_edit_context() -> str:
    """Istruzioni usate solo quando l'utente chiede una modifica alla bozza."""
    return load_prompt_file(
        "draft_edit_context.md",
        "draft editor",
        anchor_file=__file__,
    )


def format_form_data_for_draft(form_data: SubmissionRequest) -> str:
    """Formatta i dati del form in una stringa leggibile per il prompt."""
    lines = [f"**Trama iniziale**: {form_data.plot}"]
    
    # Aggiunge solo i campi compilati
    optional_fields = {
        "Nome Autore": form_data.user_name,
        "Genere": form_data.genre,
        "Ampiezza richiesta (capitoli indicativi)": {"breve": "6", "media": "12", "lunga": "20"}.get(form_data.length),
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
    
    return "\n".join(lines)


def format_question_answers(question_answers: list[QuestionAnswer]) -> str:
    """Formatta le risposte alle domande in una stringa leggibile."""
    if not question_answers:
        return "Nessuna risposta fornita alle domande preliminari."
    
    lines = ["**Risposte alle domande preliminari:**"]
    for qa in question_answers:
        if qa.answer:
            lines.append(f"- {qa.question_id}: {qa.answer}")
    
    return "\n".join(lines)


def parse_draft_output(llm_output: str) -> tuple[str, str, str]:
    """Valida e normalizza l'output bozza contro il contratto JSON."""
    payload = parse_json_model(llm_output, DraftGenerationPayload)
    return payload.title.strip(), payload.draft_text.strip(), payload.character_profiles.strip()


def render_draft_outline(payload: DraftGenerationPayload) -> str:
    """Rende in markdown le sezioni del piano, se presenti."""
    if not payload.sections:
        return ""
    return render_outline_markdown(OutlineGenerationPayload(sections=payload.sections))


async def generate_draft(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    session_id: str,
    api_key: Optional[str] = None,
    previous_draft: Optional[str] = None,
    user_feedback: Optional[str] = None,
) -> tuple[str, str, int, dict[str, int], str, str]:
    """
    Genera o rigenera bozza estesa e indice in un'unica chiamata.
    
    Returns:
        Tupla (draft_text, title, version, token_usage, character_profiles, outline_text)
    """
    agent_context = load_draft_plan_context()
    formatted_form_data = format_form_data_for_draft(form_data)
    formatted_answers = format_question_answers(question_answers)
    system_prompt = SystemMessage(
        content=append_contract_instructions(
            agent_context,
            (
                "Il runtime applica uno schema strutturato nativo: "
                "`title`, `character_profiles`, `draft_text`, `sections`. "
                "Ogni elemento di `sections` ha `title`, `description`, `level`. "
                "Niente testo fuori da quei campi."
            ),
        )
    )

    if previous_draft and user_feedback:
        user_prompt_content = f"""{load_draft_edit_context()}

**Feedback:**
{user_feedback}

**Bozza attuale:**
{previous_draft}

**Dati del romanzo (riferimento):**
{formatted_form_data}

{formatted_answers}

Restituisci il piano completo come JSON del contratto (`title`, `character_profiles`, `draft_text`, `sections`)."""
    else:
        user_prompt_content = f"""Genera il piano narrativo completo per questo romanzo: bozza estesa e indice dei capitoli.

{formatted_form_data}

{formatted_answers}

Restituisci il JSON del contratto (`title`, `character_profiles`, `draft_text`, `sections`)."""

    user_prompt = HumanMessage(content=user_prompt_content)
    gemini_model = get_stage_model("draft", form_data.llm_model, form_data=form_data)
    temperature = get_temperature_for_agent("draft_generator", gemini_model)
    trace = LLMTraceRecorder(
        stage="draft",
        session_id=session_id,
        request_id="modify-draft" if previous_draft and user_feedback else "generate-draft",
    )
    llm = build_google_chat_model(
        model_name=gemini_model,
        api_key=api_key,
        temperature=temperature,
    )

    payload, token_usage, _raw_output = await invoke_structured_chat_model(
        llm=llm,
        schema=DraftGenerationPayload,
        messages=[system_prompt, user_prompt],
        model_name=gemini_model,
        stage="draft",
        request_label=trace.request_id or "draft",
        session_id=session_id,
        trace_recorder=trace,
    )
    title = payload.title.strip()
    draft_text = payload.draft_text.strip()
    character_profiles = payload.character_profiles.strip()
    outline_text = render_draft_outline(payload)
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)
    new_version = session.current_version + 1 if session else 1

    trace.record(
        "draft_parsed",
        title=title,
        version=new_version,
        draft_characters=len(draft_text),
        character_profiles_characters=len(character_profiles),
        outline_sections=len(payload.sections),
    )
    logger.info(
        "Bozza generata con successo",
        context={
            "session_id": session_id,
            "version": new_version,
            "model": gemini_model,
            "outline_sections": len(payload.sections),
            "trace_file": str(trace.file_path),
        },
    )
    return draft_text, title, new_version, token_usage, character_profiles, outline_text

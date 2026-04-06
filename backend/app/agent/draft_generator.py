import os
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async
from app.core.config import get_temperature_for_agent
from app.core.logging import get_logger
from app.llm import (
    DraftGenerationPayload,
    LLMTraceRecorder,
    append_contract_instructions,
    build_google_chat_model,
    get_stage_model,
    invoke_structured_chat_model,
    load_prompt_file,
    parse_json_model,
)
from app.models import SubmissionRequest, QuestionAnswer


logger = get_logger("draft-generator")


def load_draft_agent_context() -> str:
    """Carica il contesto dell'agente di bozza dal file Markdown."""
    return load_prompt_file(
        "draft_agent_context.md",
        "draft generator",
        anchor_file=__file__,
    )


def format_form_data_for_draft(form_data: SubmissionRequest) -> str:
    """Formatta i dati del form in una stringa leggibile per il prompt."""
    lines = [f"**Trama iniziale**: {form_data.plot}"]
    
    # Aggiunge solo i campi compilati
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


async def generate_draft(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    session_id: str,
    api_key: Optional[str] = None,
    previous_draft: Optional[str] = None,
    user_feedback: Optional[str] = None,
) -> tuple[str, str, int, dict[str, int], str]:
    """
    Genera o rigenera una bozza estesa della trama.
    
    Args:
        form_data: Dati del form compilato
        question_answers: Risposte alle domande preliminari
        session_id: ID della sessione
        api_key: API key per Gemini (se None, usa variabile d'ambiente)
        previous_draft: Bozza precedente (se rigenerazione)
        user_feedback: Feedback dell'utente per modifiche
    
    Returns:
        Tupla (draft_text, title, version, token_usage)
        token_usage contiene {"input_tokens": int, "output_tokens": int, "model": str}
    """
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY non configurata. Imposta la variabile d'ambiente o passa api_key.")

    agent_context = load_draft_agent_context()
    formatted_form_data = format_form_data_for_draft(form_data)
    formatted_answers = format_question_answers(question_answers)
    system_prompt = SystemMessage(
        content=append_contract_instructions(
            agent_context,
            (
                "IMPORTANTE: il runtime applica uno schema strutturato nativo con i campi "
                "`title`, `character_profiles` e `draft_text`. "
                "Non usare il formato legacy TITOLO/PERSONAGGI/TRAMA."
            ),
        )
    )

    if previous_draft and user_feedback:
        user_prompt_content = f"""## MODIFICA CHIRURGICA RICHIESTA

**REGOLA FONDAMENTALE**: Devi applicare un approccio CHIRURGICO alle modifiche.
- Modifica SOLO le parti specifiche indicate nel feedback dell'utente
- Tutto ciò che NON è menzionato nel feedback deve rimanere ESATTAMENTE IDENTICO, parola per parola
- Non riscrivere sezioni che non sono coinvolte dalla richiesta
- Non migliorare, espandere o modificare parti non richieste

**Feedback dell'utente (modifica SOLO ciò che è indicato qui):**
{user_feedback}

**Bozza attuale (mantieni IDENTICO tutto ciò che non è nel feedback):**
{previous_draft}

**Dati originali del romanzo (per riferimento):**
{formatted_form_data}

{formatted_answers}

**ISTRUZIONI**:
1. Identifica ESATTAMENTE quali sezioni/paragrafi sono interessati dal feedback
2. Modifica SOLO quelle parti specifiche
3. Copia ESATTAMENTE tutto il resto senza modifiche
4. Se il feedback richiede modifiche a un personaggio/evento, tocca SOLO le parti dove quel personaggio/evento appare in relazione alla modifica richiesta
5. Restituisci la bozza completa esclusivamente come JSON conforme al contratto finale."""
    else:
        user_prompt_content = f"""Genera una bozza estesa e dettagliata dello svolgimento della trama per il seguente romanzo.

**Dati del romanzo:**
{formatted_form_data}

{formatted_answers}

Genera una bozza estesa che sviluppi in dettaglio la trama, incorporando tutte le specifiche indicate e le informazioni emerse dalle risposte.
Restituisci esclusivamente il JSON finale richiesto."""

    user_prompt = HumanMessage(content=user_prompt_content)
    gemini_model = get_stage_model("draft", form_data.llm_model)
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
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)
    new_version = session.current_version + 1 if session else 1

    trace.record(
        "draft_parsed",
        title=title,
        version=new_version,
        draft_characters=len(draft_text),
        character_profiles_characters=len(character_profiles),
    )
    logger.info(
        "Bozza generata con successo",
        context={
            "session_id": session_id,
            "version": new_version,
            "model": gemini_model,
            "trace_file": str(trace.file_path),
        },
    )
    return draft_text, title, new_version, token_usage, character_profiles



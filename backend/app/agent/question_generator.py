import uuid
from typing import Any, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import get_temperature_for_agent
from app.core.logging import get_logger
from app.llm import (
    LLMTraceRecorder,
    QuestionsPayload,
    append_contract_instructions,
    build_google_chat_model,
    coerce_llm_content_to_text,
    get_stage_model,
    invoke_chat_model,
    invoke_structured_chat_model,
    load_prompt_file,
    parse_json_model,
)
from app.models import SubmissionRequest, Question, QuestionsResponse


logger = get_logger("question-generator")

_RICH_FORM_FIELDS = (
    "genre",
    "subgenre",
    "target_audience",
    "theme",
    "protagonist",
    "protagonist_archetype",
    "character_arc",
    "point_of_view",
    "narrative_voice",
    "style",
    "temporal_structure",
    "pace",
    "realism",
    "ambiguity",
    "intentionality",
    "author",
)

_DEFAULT_QUESTION_SPECS = (
    (
        "secondari",
        "Chi sono i personaggi secondari più importanti e che ruolo hanno nella storia?",
    ),
    (
        "antagonista",
        "Chi o che cosa si oppone al protagonista, e perché?",
    ),
    (
        "relazione",
        "Quale relazione (affettiva, familiare, di potere) deve restare centrale nel romanzo?",
    ),
    (
        "tono",
        "Che tono emotivo deve prevalere nella narrazione?",
    ),
)


def form_is_rich_enough_to_skip_llm(form_data: SubmissionRequest) -> bool:
    """True se trama e campi opzionali sono già abbastanza densi da evitare una chiamata."""
    if not (form_data.plot or "").strip():
        return False
    filled = sum(1 for name in _RICH_FORM_FIELDS if getattr(form_data, name, None))
    return filled >= 6


def build_default_questions(form_data: SubmissionRequest) -> list[Question]:
    """Domande fisse, omettendo i temi già coperti dal form."""
    skip_ids: set[str] = set()
    if form_data.style:
        skip_ids.add("tono")
    questions: list[Question] = []
    for question_id, text in _DEFAULT_QUESTION_SPECS:
        if question_id in skip_ids:
            continue
        questions.append(Question(id=question_id, text=text, type="text"))
    return questions[:4]


def _validate_questions_payload(payload: QuestionsPayload) -> QuestionsPayload:
    if not payload.questions:
        raise ValueError("Il modello non ha restituito alcuna domanda valida.")
    return payload


def _questions_from_payload(payload: QuestionsPayload) -> list[Question]:
    questions: list[Question] = []
    for index, item in enumerate(payload.questions, start=1):
        options = item.options if item.type == "multiple_choice" else None
        questions.append(
            Question(
                id=item.id or f"q{index}",
                text=item.text.strip(),
                type=item.type,
                options=options,
            )
        )
    return questions


def load_agent_context() -> str:
    """Carica il contesto dell'agente dal file Markdown."""
    return load_prompt_file("agent_context.md", "question generator", anchor_file=__file__)


def format_form_data(form_data: SubmissionRequest) -> str:
    """Formatta i dati del form in una stringa leggibile per il prompt."""
    lines = [f"**Trama**: {form_data.plot}"]
    
    # Aggiunge solo i campi compilati
    optional_fields = {
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


def parse_questions_from_llm_response(response_text: Any) -> list[Question]:
    """Valida le domande contro il contratto JSON e normalizza i campi applicativi."""
    payload = _validate_questions_payload(
        parse_json_model(coerce_llm_content_to_text(response_text), QuestionsPayload)
    )
    return _questions_from_payload(payload)


async def generate_questions(
    form_data: SubmissionRequest,
    api_key: Optional[str] = None,
    session_id: Optional[str] = None,
) -> tuple[QuestionsResponse, dict[str, int]]:
    """
    Genera domande usando Gemini con contratto JSON tipizzato.
    
    Args:
        form_data: Dati del form compilato dall'utente
        api_key: API key opzionale per fallback Gemini Developer API locale
        session_id: ID della sessione (opzionale, usato solo per logging)
    
    Returns:
        Tupla (QuestionsResponse, token_usage_dict)
        token_usage_dict contiene {"input_tokens": int, "output_tokens": int, "model": str}
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    if form_is_rich_enough_to_skip_llm(form_data):
        questions = build_default_questions(form_data)
        logger.info(
            "Domande di default senza chiamata LLM",
            context={"session_id": session_id, "question_count": len(questions)},
        )
        return (
            QuestionsResponse(
                success=True,
                session_id=session_id,
                questions=questions,
                message="Domande generate con successo",
            ),
            {"input_tokens": 0, "output_tokens": 0, "model": "skipped"},
        )

    context = load_agent_context()
    formatted_data = format_form_data(form_data)
    system_prompt = append_contract_instructions(
        f"{context}\n\nAnalizza le informazioni e genera solo domande utili.",
        (
            "IMPORTANTE: il runtime applica uno schema strutturato nativo. "
            "Compila solo i campi richiesti per le domande senza aggiungere wrapper o testo extra."
        ),
    )

    user_prompt = f"""Informazioni fornite dall'utente:

{formatted_data}

Genera solo domande davvero utili e non ridondanti rispetto ai dati già presenti.
Rispondi esclusivamente con il JSON finale."""

    gemini_model = get_stage_model("questions", form_data.llm_model, form_data=form_data)
    temperature = get_temperature_for_agent("question_generator", gemini_model)
    trace = LLMTraceRecorder(
        stage="questions",
        session_id=session_id,
        request_id="generate-questions",
    )
    llm = build_google_chat_model(
        model_name=gemini_model,
        api_key=api_key,
        temperature=temperature,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    payload, token_usage, _raw_output = await invoke_structured_chat_model(
        llm=llm,
        schema=QuestionsPayload,
        messages=messages,
        model_name=gemini_model,
        stage="questions",
        request_label="generate questions",
        session_id=session_id,
        trace_recorder=trace,
        parsed_validator=_validate_questions_payload,
    )
    questions = _questions_from_payload(payload)
    trace.record(
        "questions_parsed",
        count=len(questions),
        question_ids=[question.id for question in questions],
    )
    logger.info(
        "Domande generate con successo",
        context={
            "session_id": session_id,
            "question_count": len(questions),
            "model": gemini_model,
            "trace_file": str(trace.file_path),
        },
    )

    questions_response = QuestionsResponse(
        success=True,
        session_id=session_id,
        questions=questions,
        message="Domande generate con successo",
    )
    return questions_response, token_usage


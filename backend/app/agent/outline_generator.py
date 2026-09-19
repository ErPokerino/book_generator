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
    get_stage_model,
    invoke_structured_chat_model,
    load_prompt_file,
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
    """Carica il contesto dell'agente di outline dal file Markdown."""
    return load_prompt_file(
        "outline_agent_context.md",
        "outline generator",
        anchor_file=__file__,
    )


def format_input_for_outline(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str] = None,
) -> str:
    """Formatta tutti i dati di input per il prompt dell'agente di outline."""
    lines = ["# Informazioni per la Generazione della Struttura\n"]
    
    # IMPORTANTE: Enfatizza che la bozza validata è la fonte di verità
    lines.append("## ⚠️ REGOLA FONDAMENTALE")
    lines.append("La **bozza estesa validata** (riportata di seguito) è la fonte di verità definitiva.")
    lines.append("Se ci sono differenze o conflitti con le informazioni iniziali, DEVI seguire la bozza validata.\n")
    
    # Bozza validata (priorità massima)
    lines.append("## Bozza Estesa Validata (FONTE DI VERITÀ)")
    if draft_title:
        lines.append(f"**Titolo**: {draft_title}\n")
    lines.append(validated_draft)
    lines.append("\n---\n")
    
    # Informazioni iniziali (per contesto, ma con priorità inferiore)
    lines.append("## Informazioni Iniziali (per contesto generale)")
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
) -> tuple[str, dict[str, int]]:
    """
    Genera la struttura/indice del libro basandosi sulla bozza validata.
    
    Args:
        form_data: Dati del form compilato
        question_answers: Risposte alle domande preliminari
        validated_draft: Bozza estesa validata dall'utente (fonte di verità)
        session_id: ID della sessione
        draft_title: Titolo del libro (se disponibile)
        api_key: API key opzionale per fallback Gemini Developer API locale
    
    Returns:
        Tupla (outline_text, token_usage)
        token_usage contiene {"input_tokens": int, "output_tokens": int, "model": str}
    """
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
    user_prompt_content = f"""Genera la struttura completa (indice) del romanzo basandoti sulle seguenti informazioni.

{formatted_input}

IMPORTANTE - Granularità e Stratificazione Narrativa:

La bozza estesa che hai ricevuto contiene eventi, sviluppi e momenti narrativi che devono essere trasformati in una struttura dettagliata di capitoli.

Principio fondamentale:
- Non condensare eventi complessi in un solo capitolo. Quando un evento include fasi distinte (preparazione → svolgimento → conseguenze) oppure comporta cambiamenti emotivi/relazionali importanti, trasformalo in più capitoli, ciascuno con un obiettivo narrativo chiaro.
- Non creare capitoli “di riempimento”: aggiungi capitoli solo quando c’è progressione reale (scelta, ostacolo, rivelazione, conseguenza, cambiamento di relazione, svolta tematica).

Domande guida (per decidere se dividere):
- Questo evento ha conseguenze che cambiano la direzione della storia o dei personaggi? Se sì, dedica capitoli distinti a conseguenze immediate e a conseguenze che maturano nel tempo.
- C’è escalation (tentativi, fallimenti, complicazioni) prima della risoluzione? Se sì, non comprimere escalation e risoluzione nello stesso capitolo.
- C’è un passaggio emotivo/psicologico significativo (shock, negazione, rabbia, accettazione, decisione)? Se sì, rendilo visibile con capitoli dedicati.

Per ogni sezione della bozza (Introduzione, Atto I, Atto II, Atto III, Conclusione), genera capitoli che:
- Sviluppano gli eventi principali con il tempo narrativo necessario
- Includono scene intermedie che approfondiscono personaggi, atmosfere e temi
- Integrano sottotrame e personaggi secondari con i loro archi narrativi
- Aggiungono momenti di riflessione, caratterizzazione e sviluppo emotivo
- Creano transizioni naturali tra eventi significativi
- Arricchiscono il mondo narrativo con dettagli, ambientazioni e contesti

Dettaglio per capitolo (obbligatorio):
Per ogni capitolo che proponi, includi sempre:
1) Titolo evocativo
2) Eventi chiave (in elenco puntato) con un livello di dettaglio sufficiente a guidare la scrittura
3) Focus personaggi (chi cambia, cosa decide, che attrito emerge)
4) Atmosfera e temi (tono, sottotesto, idee in gioco)
5) Collegamenti narrativi (cosa riprende dal capitolo precedente e cosa prepara per il successivo)

Non limitarti a un capitolo per evento: ogni momento narrativo significativo merita il suo spazio. 
Eventi complessi, sviluppi caratteriali, rivelazioni importanti, conflitti interiori ed esteriori 
devono essere sviluppati con la profondità che richiedono, non compressi in riassunti.

Restituisci l'outline come JSON strutturato: una lista ordinata di sezioni/capitoli, ciascuna con `title`, `description` e `level`.
La struttura deve essere ampia e stratificata, includendo non solo gli eventi principali, ma anche approfondimenti su personaggi, temi, atmosfere, sottotrame e sviluppi narrativi."""

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



import os
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import get_temperature_for_agent
from app.core.logging import get_logger
from app.llm import (
    LLMTraceRecorder,
    OutlineGenerationPayload,
    append_contract_instructions,
    build_google_chat_model,
    get_stage_model,
    invoke_structured_chat_model,
    load_prompt_file,
    parse_json_model,
)
from app.models import SubmissionRequest, QuestionAnswer


logger = get_logger("outline-generator")


def _validate_outline_payload(payload: OutlineGenerationPayload) -> OutlineGenerationPayload:
    if not payload.sections:
        raise ValueError("Outline privo di sezioni.")
    return payload


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
    lines: list[str] = []
    for section in payload.sections:
        header_prefix = "#" * section.level
        lines.append(f"{header_prefix} {section.title.strip()}")
        lines.append("")
        lines.append(section.description.strip())
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
        api_key: API key per Gemini (se None, usa variabile d'ambiente)
    
    Returns:
        Tupla (outline_text, token_usage)
        token_usage contiene {"input_tokens": int, "output_tokens": int, "model": str}
    """
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY non configurata. Imposta la variabile d'ambiente o passa api_key.")

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
    gemini_model = get_stage_model("outline", form_data.llm_model)
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



"""Planner testuale one-shot per il manga beta."""

from __future__ import annotations

import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import get_temperature_for_agent
from app.core.logging import get_logger
from app.llm import (
    LLMTraceRecorder,
    build_google_chat_model,
    get_max_output_tokens,
    get_stage_model,
    invoke_structured_chat_model,
)
from app.models import MangaCreateRequest, MangaPagePlan, MangaPlan

logger = get_logger("manga-planner")

MANGA_TYPE_DESCRIPTIONS = {
    "shonen": "Azione e avventura, ritmo energico, forte slancio narrativo e posta in gioco aspirazionale.",
    "shojo": "Focus romantico ed emotivo, sentimenti espressivi, momenti delicati e coinvolgenti.",
    "seinen": "Tono maturo e concreto, conflitti sfumati, conseguenze realistiche e maggiore intensita drammatica.",
    "josei": "Realismo quotidiano ed emotivo, relazioni intime, ritmo guidato dai personaggi.",
    "kodomo": "Tono chiaro, giocoso e adatto ai bambini, con conflitti semplici e ottimistici.",
}

MANGA_COLOR_MODE_DESCRIPTIONS = {
    "black_and_white": "Pagine interne in bianco e nero o scala di grigi, con retini/contrasti coerenti e nessun elemento a colori.",
    "color": "Pagine interne interamente a colori, con palette coerente e resa cromatica stabile da inizio a fine manga.",
}


def _format_characters(request: MangaCreateRequest) -> str:
    if not request.main_characters:
        return "- Nessun personaggio esplicito fornito dall'utente.\n"
    lines = []
    for character in request.main_characters:
        lines.append(f"- {character.name}: {character.description}")
    return "\n".join(lines)


def _clean_dialogue(dialogue: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in dialogue:
        text = _normalize_visible_text_line(line)
        if not text:
            continue
        if len(text) > 120:
            text = f"{text[:117].rstrip()}..."
        cleaned.append(text)
    return cleaned[:5]


def _normalize_visible_text_line(line: str) -> str:
    text = " ".join((line or "").split()).strip()
    if not text:
        return ""

    text = re.sub(
        r"^(?:sfx|sound effect|fx|caption|note|editor(?:ial)? note|panel)\s*[:\-]\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    return text


def _clean_list(items: list[str], *, max_items: int = 5, max_chars: int = 160) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        text = " ".join((item or "").split()).strip()
        if not text:
            continue
        if len(text) > max_chars:
            text = f"{text[: max_chars - 3].rstrip()}..."
        cleaned.append(text)
    return cleaned[:max_items]


def _describe_requested_page_range(request: MangaCreateRequest) -> str:
    if request.min_pages == request.max_pages:
        return f"esattamente {request.min_pages}"
    return f"tra {request.min_pages} e {request.max_pages}"


def _build_page_count_policy(request: MangaCreateRequest) -> str:
    if request.min_pages == request.max_pages:
        return (
            f"Rispetta esattamente {request.min_pages} pagine. "
            "Non scegliere una lunghezza diversa."
        )
    return (
        "Scegli tu la lunghezza finale del manga in base al materiale narrativo disponibile, "
        "ma resta sempre dentro il range richiesto."
    )


def _build_page_count_requirement(request: MangaCreateRequest) -> str:
    if request.min_pages == request.max_pages:
        return f"- Il manga deve avere esattamente {request.min_pages} pagine.\n"
    return (
        f"- Scegli una lunghezza finale compresa tra {request.min_pages} e {request.max_pages} pagine.\n"
        "- Se il range contiene piu opzioni, seleziona il numero di pagine che meglio bilancia completezza narrativa, ritmo e chiarezza.\n"
    )


def _validate_manga_plan(plan: MangaPlan, *, request: MangaCreateRequest) -> MangaPlan:
    if len(plan.page_plans) < request.min_pages or len(plan.page_plans) > request.max_pages:
        raise ValueError(
            "Il planner manga deve restituire un numero di page_plans compreso "
            f"tra {request.min_pages} e {request.max_pages}"
        )

    normalized_pages: list[MangaPagePlan] = []
    for index, page in enumerate(plan.page_plans, start=1):
        normalized_pages.append(
            page.model_copy(
                update={
                    "page_number": index,
                    "dialogue": _clean_dialogue(page.dialogue),
                    "visual_notes": _clean_list(page.visual_notes),
                    "continuity_notes": _clean_list(page.continuity_notes),
                }
            )
        )

    return plan.model_copy(update={"page_plans": normalized_pages})


def _build_manga_chat_llm(*, model_name: str, api_key: Optional[str], temperature: float):
    return build_google_chat_model(
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        max_output_tokens=get_max_output_tokens(model_name),
    )


async def generate_manga_plan(
    *,
    session_id: str,
    request: MangaCreateRequest,
    api_key: Optional[str] = None,
) -> tuple[MangaPlan, dict[str, int], str]:
    """Genera titolo, bible personaggi e piani pagina in un solo output strutturato."""
    stage_model = get_stage_model("manga_planning", overrides=getattr(request, "model_overrides", None))
    llm = _build_manga_chat_llm(
        model_name=stage_model,
        api_key=api_key,
        temperature=get_temperature_for_agent("manga_planner", stage_model),
    )
    trace = LLMTraceRecorder(
        stage="manga-planning",
        session_id=session_id,
        request_id="storyboard-plan",
    )

    system_prompt = (
        "Sei un planner narrativo per mini manga in una beta di prodotto. Produci un piano compatto ma coerente, "
        "pronto per essere trasformato in immagini pagina per pagina. "
        "Ogni pagina e una pagina manga completa con vignette, balloon e testo gia integrati nell'immagine. "
        f"{_build_page_count_policy(request)} "
        "Mantieni i dialoghi molto brevi, facili da inserire nei balloon, e non sovraccaricare mai una pagina. "
        "Preserva la continuita di personaggi, vestiti, oggetti e ambientazioni tra pagine adiacenti. "
        "Preserva rigorosamente anche coerenza grafica e cromatica dalla prima all'ultima pagina. "
        "Anche se l'input utente contiene testo in inglese, devi tradurre e riformulare tutto il contenuto finale in italiano. "
        "Tutto il contenuto narrativo e testuale deve essere in italiano. "
        "Non inserire mai testo meta o istruzioni per il disegnatore tra i dialoghi finali. "
        "Restituisci solo dati compatibili con lo schema richiesto."
    )
    human_prompt = (
        f"Crea un piano per un mini manga lungo {_describe_requested_page_range(request)} pagine.\n\n"
        f"Titolo richiesto: {request.title or 'Scegli automaticamente il titolo migliore'}\n"
        f"Tipo di manga: {request.manga_type} - {MANGA_TYPE_DESCRIPTIONS.get(request.manga_type, '')}\n"
        f"Modalita cromatica pagine interne: {MANGA_COLOR_MODE_DESCRIPTIONS.get(request.page_color_mode, '')}\n"
        f"Trama iniziale:\n{request.plot.strip()}\n\n"
        f"Personaggi principali:\n{_format_characters(request)}\n\n"
        "Requisiti:\n"
        f"{_build_page_count_requirement(request)}"
        f"- Mantieni la stessa modalita cromatica per tutte le pagine interne: {request.page_color_mode}.\n"
        "- Mantieni coerenti stile grafico, volti, costumi, silhouette, ambienti e livello di dettaglio dalla prima all'ultima pagina.\n"
        "- Restituisci un arco breve ma completo, con apertura, escalation, climax e chiusura chiara.\n"
        "- L'intero piano deve gia decidere cosa accade in ogni pagina.\n"
        "- Ogni page_plan deve includere: narrative_goal, scene_description, short dialogue, visual_notes, continuity_notes e summary.\n"
        "- Titolo, sinossi, tono, dialoghi, visual notes, continuity notes e summary devono essere in italiano.\n"
        "- Se la trama iniziale o i dettagli dei personaggi sono in inglese, traducili in italiano senza lasciare residui nella risposta finale.\n"
        "- I dialoghi dovrebbero essere in genere da 1 a 4 battute brevi.\n"
        "- Se servono onomatopee, scrivile direttamente come testo da disegnare, senza prefissi come SFX:, FX:, NOTE: o simili.\n"
        "- Non pianificare testo editoriale o meta in pagina: niente numeri pagina, intestazioni, titoli correnti, etichette di pannello o istruzioni per il disegnatore.\n"
        "- Le visual notes devono menzionare ritmo delle vignette, inquadrature/emozioni o dettagli grafici utili alla generazione.\n"
        "- Le continuity notes devono catturare i dettagli che la pagina successiva deve ricordare.\n"
        "- La pagina finale deve dare davvero un senso di conclusione, anche in una beta mini manga.\n"
    )

    logger.info(
        "Avvio planning manga",
        context={"session_id": session_id, "model": stage_model, "manga_type": request.manga_type},
    )
    return await invoke_structured_chat_model(
        llm=llm,
        schema=MangaPlan,
        messages=[
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ],
        model_name=stage_model,
        stage="manga-planning",
        request_label="storyboard-plan",
        session_id=session_id,
        trace_recorder=trace,
        parsed_validator=lambda plan: _validate_manga_plan(plan, request=request),
    )

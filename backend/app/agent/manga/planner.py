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

MANGA_LANGUAGE_RULE = (
    "Tutto il contenuto narrativo e il testo visibile devono essere in italiano. "
    "Se la fonte e in inglese, traducila senza residui."
)
MANGA_NO_META_RULE = (
    "Niente testo meta: numeri pagina, intestazioni, etichette di vignetta, "
    "istruzioni al disegnatore, prefissi SFX/FX/NOTE."
)

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
        "Sei un planner narrativo per mini manga. Produci un piano compatto, coerente, "
        "pronto a diventare pagine con vignette e balloon gia integrati. "
        f"{_build_page_count_policy(request)} "
        "Dialoghi brevissimi; non sovraccaricare una pagina. "
        "Continuita di personaggi, vestiti, oggetti, ambienti, tratto e colore da pagina a pagina. "
        f"{MANGA_LANGUAGE_RULE} {MANGA_NO_META_RULE} "
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
        "- Arco breve ma completo: apertura, escalation, climax, chiusura.\n"
        "- Ogni page_plan: narrative_goal, scene_description, dialoghi brevi (1-4), visual_notes, continuity_notes, summary.\n"
        "- Visual notes: ritmo vignette, inquadrature, dettagli grafici. Continuity notes: cosa la pagina dopo deve ricordare.\n"
        "- Onomatopee come suono da disegnare, senza prefissi.\n"
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

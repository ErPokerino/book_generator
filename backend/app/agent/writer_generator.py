import os
import json
import re
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.models import SubmissionRequest, QuestionAnswer
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    get_session_async, update_writing_progress_async, start_chapter_timing_async, 
    end_chapter_timing_async, update_book_chapter_async, pause_writing_async, resume_writing_async,
    save_session_async, update_token_usage_async,
)
from app.core.config import get_app_config, get_temperature_for_agent
from app.agent.story_bible import (
    build_story_bible,
    get_nearby_chapter_cards,
    get_recent_full_chapters,
    get_relevant_continuity_notes,
)
from app.utils.token_tracker import extract_token_usage
from app.services.pdf_service import calculate_page_count
import math
import httpx

# Configurazione retry e timeout per robustezza contro errori di rete
CHAPTER_GENERATION_MAX_RETRIES = 3  # Numero massimo di tentativi per generare un capitolo
CHAPTER_GENERATION_RETRY_DELAY = 5  # Delay base in secondi tra tentativi (con backoff)
CHAPTER_GENERATION_TIMEOUT = 300  # Timeout in secondi per la generazione (5 minuti)
DEFAULT_MIN_CHAPTER_LENGTH = 1200
DEFAULT_MIN_CHAPTER_WORDS = 180
DEFAULT_DISALLOWED_OUTPUT_MARKERS = ("[ERRORE:", "[ERROR:")

# Errori di rete che giustificano un retry
RETRYABLE_EXCEPTIONS = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    ConnectionError,
    TimeoutError,
)


def _is_retryable_error(error: Exception) -> bool:
    """Verifica se l'errore è recuperabile con un retry."""
    # Controlla se è un'istanza diretta
    if isinstance(error, RETRYABLE_EXCEPTIONS):
        return True
    # Controlla se il messaggio contiene indicatori di errori di rete
    error_msg = str(error).lower()
    retryable_patterns = [
        'timeout', 'timed out', 'connection', 'connect', 
        'read timeout', 'ssl', 'tls', 'handshake',
        'network', 'socket', 'eof', 'reset'
    ]
    return any(pattern in error_msg for pattern in retryable_patterns)


def _count_words(text: str) -> int:
    """Conta le parole in modo robusto anche con apostrofi e lettere accentate."""
    return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ'-]+\b", text, flags=re.UNICODE))


def _get_chapter_validation_settings(app_config: Optional[dict[str, Any]] = None) -> tuple[int, int, list[str]]:
    """Restituisce le soglie di validazione per i capitoli."""
    if app_config is None:
        app_config = get_app_config()

    validation_config = app_config.get("validation", {})
    min_chars = int(validation_config.get("min_chapter_length", DEFAULT_MIN_CHAPTER_LENGTH))
    min_words = int(validation_config.get("min_chapter_words", DEFAULT_MIN_CHAPTER_WORDS))
    disallowed_markers = validation_config.get(
        "disallowed_output_markers",
        list(DEFAULT_DISALLOWED_OUTPUT_MARKERS),
    )
    if not isinstance(disallowed_markers, list):
        disallowed_markers = list(DEFAULT_DISALLOWED_OUTPUT_MARKERS)

    return min_chars, min_words, [str(marker) for marker in disallowed_markers if marker]


def _find_blocked_output_marker(text: str, disallowed_markers: list[str]) -> Optional[str]:
    """Cerca marker che indicano output tecnico o placeholder non narrativi."""
    text_lower = text.lower()
    for marker in disallowed_markers:
        if marker.lower() in text_lower:
            return marker
    return None


def validate_generated_chapter_text(
    chapter_text: str,
    current_section_title: str,
    app_config: Optional[dict[str, Any]] = None,
) -> str:
    """Valida che un capitolo abbia contenuto narrativo sufficiente e nessun placeholder tecnico."""
    if not chapter_text or not chapter_text.strip():
        raise ValueError(f"Capitolo vuoto per '{current_section_title}'")

    text = chapter_text.strip()
    min_chars, min_words, disallowed_markers = _get_chapter_validation_settings(app_config)

    blocked_marker = _find_blocked_output_marker(text, disallowed_markers)
    if blocked_marker:
        raise ValueError(
            f"Capitolo non valido per '{current_section_title}': contiene il marker non narrativo '{blocked_marker}'"
        )

    char_count = len(text)
    word_count = _count_words(text)
    alnum_count = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]", text))

    if alnum_count < 20:
        raise ValueError(
            f"Capitolo non valido per '{current_section_title}': contenuto non significativo ({alnum_count} caratteri alfanumerici)"
        )

    if char_count < min_chars:
        raise ValueError(
            f"Capitolo troppo corto per '{current_section_title}': {char_count} caratteri "
            f"(minimo richiesto: {min_chars})"
        )

    if word_count < min_words:
        raise ValueError(
            f"Capitolo troppo breve per '{current_section_title}': {word_count} parole "
            f"(minimo richiesto: {min_words})"
        )

    return text


def _format_question_answers_for_writer(question_answers: List[QuestionAnswer]) -> Optional[str]:
    """Formatta le risposte alle domande preliminari come vincoli espliciti per lo scrittore."""
    if not question_answers:
        return None

    answered_lines = []
    for qa in question_answers:
        if qa.answer and qa.answer.strip():
            answered_lines.append(f"- {qa.question_id}: {qa.answer.strip()}")

    if not answered_lines:
        return None

    return "\n".join(answered_lines)


async def refresh_story_bible_for_session(
    session_store: Any,
    session: Any,
    outline_sections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rigenera e persiste la story bible della sessione usando outline e capitoli già completati."""
    session.story_bible = build_story_bible(
        form_data=session.form_data,
        question_answers=session.question_answers,
        validated_draft=session.current_draft or "",
        draft_title=session.current_title,
        outline_sections=outline_sections,
        completed_chapters=session.book_chapters or [],
        draft_version=session.current_version,
        outline_version=session.outline_version,
    )
    await save_session_async(session_store, session)
    return session.story_bible


def _load_agent_prompt(prompt_filename: str, agent_label: str) -> str:
    """Carica un prompt agente dalla cartella config."""
    # In locale: __file__ = backend/app/agent/writer_generator.py -> root = .parent.parent.parent.parent
    # Nel container: __file__ = /app/app/agent/writer_generator.py -> root = .parent.parent.parent
    base_path = Path(__file__).parent.parent.parent
    config_path = base_path / "config" / prompt_filename
    
    # Se non esiste, prova un livello sopra (per ambiente locale)
    if not config_path.exists():
        base_path = base_path.parent
        config_path = base_path / "config" / prompt_filename
    
    if not config_path.exists():
        raise FileNotFoundError(f"File prompt {agent_label} non trovato: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return f.read()


def load_writer_agent_context() -> str:
    """Carica il contesto dell'agente scrittore dal file Markdown."""
    return _load_agent_prompt("writer_agent_context.md", "scrittore")


def load_chapter_reviewer_context() -> str:
    """Carica il contesto dell'agente reviewer del capitolo dal file Markdown."""
    return _load_agent_prompt("chapter_reviewer_context.md", "reviewer capitolo")


def _coerce_llm_content_to_text(content: Any) -> str:
    """
    Normalizza `response.content` (Gemini/LangChain) a stringa.
    In alcuni casi `content` può essere una lista di "parts" invece che una stringa.
    """
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
            elif isinstance(item, dict):
                txt = item.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _resolve_generation_mode(model_name: str) -> str:
    """Converte il nome modello in una modalità di prodotto."""
    model_lower = (model_name or "").lower()
    if "ultra" in model_lower:
        return "ultra"
    if "pro" in model_lower:
        return "pro"
    return "flash"


def _get_chapter_review_settings(app_config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Restituisce la configurazione del review flow dei capitoli."""
    if app_config is None:
        app_config = get_app_config()

    review_config = app_config.get("review", {})
    chapters_config = review_config.get("chapters", {}) if isinstance(review_config, dict) else {}

    target_modes = chapters_config.get("target_modes", ["pro", "ultra"])
    if not isinstance(target_modes, list):
        target_modes = ["pro", "ultra"]

    return {
        "enabled": bool(chapters_config.get("enabled", True)),
        "target_modes": [str(mode) for mode in target_modes],
        "min_chapter_words": int(chapters_config.get("min_chapter_words", 220)),
        "max_issues": int(chapters_config.get("max_issues", 5)),
        "reviewer_max_output_tokens": int(chapters_config.get("reviewer_max_output_tokens", 2048)),
        "allow_fallback_to_original": bool(chapters_config.get("allow_fallback_to_original", True)),
    }


def should_run_chapter_review(
    form_data: SubmissionRequest,
    chapter_text: str,
    app_config: Optional[dict[str, Any]] = None,
) -> bool:
    """Determina se attivare il pass review->revise per il capitolo."""
    settings = _get_chapter_review_settings(app_config)
    if not settings["enabled"]:
        return False

    mode = _resolve_generation_mode(form_data.llm_model)
    if mode not in settings["target_modes"]:
        return False

    return _count_words(chapter_text) >= settings["min_chapter_words"]


def _coerce_review_points(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.lstrip("-•* ").strip() for line in value.splitlines() if line.strip()]
    coerced = str(value).strip()
    return [coerced] if coerced else []


def _extract_first_json_object(response_text: str) -> dict[str, Any]:
    """Estrae il primo oggetto JSON valido trovato nel testo."""
    if not response_text or not response_text.strip():
        raise ValueError("Risposta vuota del reviewer.")

    candidate_blocks: list[str] = []
    stripped_text = response_text.strip()
    if stripped_text.startswith("{") and stripped_text.endswith("}"):
        candidate_blocks.append(stripped_text)

    if "```" in response_text:
        segments = response_text.split("```")
        for idx, segment in enumerate(segments):
            if idx % 2 == 1:
                cleaned = segment.strip()
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].strip()
                if cleaned:
                    candidate_blocks.append(cleaned)

    for candidate in candidate_blocks:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    for start_index, char in enumerate(response_text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(response_text[start_index:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError("Nessun JSON valido trovato nella risposta del reviewer.")


def parse_chapter_review_response(response_text: str, max_issues: int = 5) -> dict[str, Any]:
    """Parsa l'output JSON del reviewer capitolo."""
    parsed = _extract_first_json_object(response_text)
    issues = _coerce_review_points(parsed.get("issues"))[:max_issues]
    preserve = _coerce_review_points(parsed.get("preserve"))[:max_issues]
    needs_revision = bool(parsed.get("needs_revision")) or bool(issues)

    if not issues:
        needs_revision = False

    return {
        "needs_revision": needs_revision,
        "issues": issues,
        "preserve": preserve,
    }


def _combine_token_usage(*token_usages: dict[str, int]) -> dict[str, int]:
    """Somma il token usage di più chiamate LLM."""
    combined = {"input_tokens": 0, "output_tokens": 0, "model": None}
    for usage in token_usages:
        if not usage:
            continue
        combined["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        combined["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        if usage.get("model"):
            combined["model"] = usage.get("model")
    return combined


def format_chapter_review_context(
    form_data: SubmissionRequest,
    current_section: Dict[str, Any],
    story_bible: Optional[Dict[str, Any]],
    chapter_text: str,
) -> str:
    """Costruisce il contesto compatto per l'editor reviewer."""
    lines = [
        f"## Modalità: {_resolve_generation_mode(form_data.llm_model)}",
        f"## Sezione corrente: {current_section.get('title', 'Sezione senza titolo')}",
        "### Descrizione della sezione",
        current_section.get("description", "Nessuna descrizione disponibile."),
    ]

    if story_bible:
        creative_brief = story_bible.get("creative_brief", [])
        if creative_brief:
            lines.append("\n### Brief creativo")
            for item in creative_brief:
                lines.append(f"- {item}")

        user_constraints = story_bible.get("user_constraints", [])
        if user_constraints:
            lines.append("\n### Vincoli utente")
            for item in user_constraints:
                lines.append(f"- {item}")

        nearby_cards = get_nearby_chapter_cards(
            story_bible,
            current_section.get("section_index"),
        )
        if nearby_cards:
            lines.append("\n### Chapter cards rilevanti")
            for card in nearby_cards:
                lines.append(f"- {card.get('title', '')}: {card.get('description', '')}")

        continuity_notes = get_relevant_continuity_notes(story_bible, [])
        if continuity_notes:
            lines.append("\n### Continuità consolidata")
            for note in continuity_notes:
                lines.append(f"- {note.get('title', '')}: {note.get('summary', '')}")

        recent_developments = story_bible.get("recent_developments", [])
        if recent_developments:
            lines.append("\n### Ultimi sviluppi")
            for item in recent_developments:
                lines.append(f"- {item}")

    lines.append("\n## Capitolo da valutare")
    lines.append(chapter_text)
    return "\n".join(lines)


async def _invoke_messages_with_retry(
    messages: list[Any],
    gemini_model: str,
    api_key: str,
    temperature: float,
    max_output_tokens: int,
    request_label: str,
) -> tuple[str, dict[str, int]]:
    """Invoca il modello Gemini con retry e restituisce testo + token usage."""
    llm = ChatGoogleGenerativeAI(
        model=gemini_model,
        google_api_key=api_key,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout=CHAPTER_GENERATION_TIMEOUT,
    )

    last_error = None
    for attempt in range(CHAPTER_GENERATION_MAX_RETRIES):
        try:
            response = await llm.ainvoke(messages)
            response_text = _coerce_llm_content_to_text(response.content).strip()
            token_usage = extract_token_usage(response)
            token_usage["model"] = gemini_model

            if not response_text:
                raise ValueError(f"Risposta vuota per {request_label}")

            if attempt > 0:
                print(f"[WRITER] Chiamata riuscita al tentativo {attempt + 1} per {request_label}")
            return response_text, token_usage

        except Exception as e:
            last_error = e
            is_retryable = _is_retryable_error(e)
            if is_retryable and attempt < CHAPTER_GENERATION_MAX_RETRIES - 1:
                delay = CHAPTER_GENERATION_RETRY_DELAY * (attempt + 1)
                print(f"[WRITER] Tentativo {attempt + 1}/{CHAPTER_GENERATION_MAX_RETRIES} fallito per {request_label}: {type(e).__name__}")
                print(f"[WRITER] Errore recuperabile, riprovo tra {delay}s...")
                await asyncio.sleep(delay)
            else:
                raise

    raise last_error if last_error else Exception(f"Invocazione fallita per {request_label}")


async def review_and_maybe_revise_chapter(
    *,
    agent_context: str,
    formatted_context: str,
    gemini_model: str,
    api_key: str,
    form_data: SubmissionRequest,
    current_section: Dict[str, Any],
    story_bible: Optional[Dict[str, Any]],
    chapter_text: str,
) -> tuple[str, dict[str, int]]:
    """Esegue un pass review->revise non bloccante su un capitolo già valido."""
    app_config = get_app_config()
    if not should_run_chapter_review(form_data, chapter_text, app_config):
        return chapter_text, {"input_tokens": 0, "output_tokens": 0, "model": gemini_model}

    settings = _get_chapter_review_settings(app_config)
    reviewer_context = load_chapter_reviewer_context()
    review_payload = format_chapter_review_context(
        form_data=form_data,
        current_section=current_section,
        story_bible=story_bible,
        chapter_text=chapter_text,
    )

    try:
        review_response_text, review_token_usage = await _invoke_messages_with_retry(
            messages=[
                SystemMessage(content=reviewer_context),
                HumanMessage(
                    content=(
                        "Valuta il capitolo seguente come editor tecnico e restituisci SOLO JSON valido.\n\n"
                        f"{review_payload}"
                    )
                ),
            ],
            gemini_model=gemini_model,
            api_key=api_key,
            temperature=get_temperature_for_agent("chapter_reviewer", gemini_model),
            max_output_tokens=min(get_max_output_tokens(gemini_model), settings["reviewer_max_output_tokens"]),
            request_label=f"review capitolo '{current_section['title']}'",
        )

        review_result = parse_chapter_review_response(
            review_response_text,
            max_issues=settings["max_issues"],
        )

        if not review_result["needs_revision"]:
            return chapter_text, review_token_usage

        revision_prompt = f"""Rivedi il capitolo seguente mantenendo voce, continuità e materiale già efficace.

{formatted_context}

## CAPITOLO DA REVISIONARE
{chapter_text}

## PROBLEMI DA CORREGGERE
{chr(10).join(f"- {issue}" for issue in review_result["issues"])}
"""

        if review_result["preserve"]:
            revision_prompt += f"""
## ELEMENTI DA PRESERVARE
{chr(10).join(f"- {item}" for item in review_result["preserve"])}
"""

        revision_prompt += """
## ISTRUZIONI FINALI
- Correggi solo i problemi segnalati, senza cambiare inutilmente il resto.
- Mantieni coerenza con continuità, chapter cards e vincoli utente.
- Restituisci SOLO la versione finale del capitolo, senza note editoriali o spiegazioni.
"""

        revised_text, revision_token_usage = await _invoke_messages_with_retry(
            messages=[
                SystemMessage(content=agent_context),
                HumanMessage(content=revision_prompt),
            ],
            gemini_model=gemini_model,
            api_key=api_key,
            temperature=get_temperature_for_agent("chapter_reviser", gemini_model),
            max_output_tokens=get_max_output_tokens(gemini_model),
            request_label=f"revisione capitolo '{current_section['title']}'",
        )

        revised_text = validate_generated_chapter_text(
            revised_text,
            current_section["title"],
            app_config=app_config,
        )
        return revised_text, _combine_token_usage(review_token_usage, revision_token_usage)

    except Exception as e:
        if settings["allow_fallback_to_original"]:
            print(
                f"[WRITER] WARNING: review flow non bloccante fallito per '{current_section['title']}': {e}. "
                f"Uso il capitolo originale valido."
            )
            return chapter_text, {"input_tokens": 0, "output_tokens": 0, "model": gemini_model}
        raise


def parse_outline_sections(outline_text: str) -> List[Dict[str, str]]:
    """
    Analizza il testo Markdown della struttura e estrae le sezioni (capitoli, introduzione, prologo, ecc.).
    
    Restituisce una lista di dizionari con:
    - 'title': Titolo della sezione
    - 'description': Descrizione/testo della sezione
    - 'level': Livello gerarchico (1=parte, 2=capitolo, ecc.)
    
    Raises:
        ValueError: Se l'outline è vuoto o non contiene sezioni valide
    """
    if not outline_text or not outline_text.strip():
        raise ValueError("L'outline è vuoto. Genera prima la struttura del romanzo.")
    
    sections = []
    lines = outline_text.split('\n')
    
    current_section = None
    current_description = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Rileva intestazioni Markdown
        if line.startswith('#'):
            # Salva la sezione precedente se esiste
            if current_section:
                current_section['description'] = '\n'.join(current_description).strip()
                sections.append(current_section)
            
            # Determina il livello
            level = 0
            while level < len(line) and line[level] == '#':
                level += 1
            
            # Estrae il titolo (rimuove # e spazi)
            title = line[level:].strip()
            
            if not title:
                # Intestazione vuota, salta
                continue
            
            # Ignora il titolo principale del documento (livello 1 all'inizio)
            if level == 1 and len(sections) == 0 and ('struttura' in title.lower() or 'indice' in title.lower() or 'outline' in title.lower()):
                current_section = None
                current_description = []
                continue
            
            # Crea nuova sezione
            current_section = {
                'title': title,
                'description': '',
                'level': level
            }
            current_description = []
        
        elif current_section:
            # Aggiungi la riga alla descrizione della sezione corrente
            current_description.append(line)
    
    # Aggiungi l'ultima sezione
    if current_section:
        current_section['description'] = '\n'.join(current_description).strip()
        sections.append(current_section)
    
    # Log per debug
    level2_sections = [s for s in sections if s['level'] == 2]
    level3_sections = [s for s in sections if s['level'] == 3]
    print(f"[PARSE OUTLINE] Trovate {len(sections)} sezioni totali (prima del filtro)")
    print(f"[PARSE OUTLINE] - Sezioni livello 2: {len(level2_sections)}")
    print(f"[PARSE OUTLINE] - Sezioni livello 3: {len(level3_sections)}")
    
    # Mostra esempi di sezioni di livello 2 e 3
    if level2_sections:
        print(f"[PARSE OUTLINE] Esempi livello 2 (primi 3):")
        for i, s in enumerate(level2_sections[:3]):
            print(f"[PARSE OUTLINE]   {i+1}. {s['title'][:60]}")
    if level3_sections:
        print(f"[PARSE OUTLINE] Esempi livello 3 (primi 3):")
        for i, s in enumerate(level3_sections[:3]):
            print(f"[PARSE OUTLINE]   {i+1}. {s['title'][:60]}")
    
    # Filtra solo le sezioni di livello 2 o 3 (capitoli, non contenitori strutturali)
    # Keyword che identificano contenitori strutturali (livello 2 che contengono capitoli)
    structural_keywords = [
        'Parte', 'Part', 'Atto', 'Act', 
        'Introduzione', 'Introduction', 
        'Conclusione', 'Conclusion',
        'Prologo', 'Prologue', 
        'Epilogo', 'Epilogue',
        'Sezione', 'Section'
    ]
    
    # Verifica se ci sono contenitori strutturali di livello 2
    structural_containers = [
        s for s in sections 
        if s['level'] == 2 and any(keyword.lower() in s['title'].lower() for keyword in structural_keywords)
    ]
    structural_container_count = len(structural_containers)
    
    # Verifica se ci sono capitoli espliciti di livello 2 (parola "Capitolo" o "Chapter")
    explicit_chapters_level2 = [
        s for s in sections 
        if s['level'] == 2 and ('capitolo' in s['title'].lower() or 'chapter' in s['title'].lower())
    ]
    has_explicit_chapters_level2 = len(explicit_chapters_level2) > 0
    
    # Verifica se ci sono sezioni di livello 3
    has_level3_sections = len(level3_sections) > 0
    
    # Debug: stampa risultati del rilevamento
    print(f"[PARSE OUTLINE] Rilevamento:")
    print(f"[PARSE OUTLINE] - Contenitori strutturali (livello 2): {structural_container_count}")
    if structural_containers:
        for s in structural_containers[:3]:
            print(f"[PARSE OUTLINE]   * {s['title'][:60]}")
    print(f"[PARSE OUTLINE] - Capitoli espliciti (livello 2): {len(explicit_chapters_level2)}")
    print(f"[PARSE OUTLINE] - Sezioni livello 3: {has_level3_sections}")
    
    # Logica migliorata: se ci sono sezioni di livello 3 E contenitori strutturali di livello 2, usa livello 3
    # OPPURE se non ci sono capitoli espliciti di livello 2, usa livello 3 se disponibile
    if (structural_container_count > 0 and has_level3_sections) or \
       (not has_explicit_chapters_level2 and has_level3_sections):
        # Prendi solo i capitoli (livello 3)
        filtered_sections = [s for s in sections if s['level'] == 3]
        print(f"[PARSE OUTLINE] DECISIONE: Struttura con contenitori + capitoli livello 3 -> filtrate {len(filtered_sections)} sezioni di livello 3")
    elif has_explicit_chapters_level2:
        # Prendi le sezioni di livello 2 (capitoli diretti)
        filtered_sections = [s for s in sections if s['level'] == 2]
        print(f"[PARSE OUTLINE] DECISIONE: Capitoli espliciti livello 2 -> filtrate {len(filtered_sections)} sezioni di livello 2")
    else:
        # Fallback: prova con livello 2
        filtered_sections = [s for s in sections if s['level'] == 2]
        print(f"[PARSE OUTLINE] DECISIONE: Fallback -> filtrate {len(filtered_sections)} sezioni di livello 2")
    
    # Se dopo il filtro non ci sono sezioni, prova a prendere tutte le sezioni di livello 2 o 3
    if len(filtered_sections) == 0:
        print(f"[PARSE OUTLINE] Nessuna sezione dopo filtro, provo con tutti i livelli 2 e 3...")
        filtered_sections = [s for s in sections if s['level'] in [2, 3]]
        print(f"[PARSE OUTLINE] Trovate {len(filtered_sections)} sezioni di livello 2 o 3")
    
    # Se ancora non ci sono sezioni, prova con qualsiasi livello > 1
    if len(filtered_sections) == 0:
        print(f"[PARSE OUTLINE] Nessuna sezione di livello 2-3, provo con tutti i livelli > 1...")
        filtered_sections = [s for s in sections if s['level'] > 1]
        print(f"[PARSE OUTLINE] Trovate {len(filtered_sections)} sezioni di livello > 1")
    
    if len(filtered_sections) == 0:
        raise ValueError(
            f"Nessuna sezione scrivibile trovata nella struttura. "
            f"Trovate {len(sections)} sezioni totali, ma nessuna di livello appropriato (2 o 3). "
            f"Verifica che la struttura contenga capitoli con intestazioni Markdown (## o ###)."
        )
    
    for index, section in enumerate(filtered_sections):
        section["section_index"] = index

    print(f"[PARSE OUTLINE] Restituisco {len(filtered_sections)} sezioni da scrivere")
    return filtered_sections


def regenerate_outline_markdown(sections: List[Dict[str, Any]]) -> str:
    """
    Rigenera il markdown dell'outline da un array di sezioni modificate.
    
    Args:
        sections: Lista di dizionari con 'title', 'description', 'level', 'section_index'
    
    Returns:
        Stringa markdown formattata
    """
    if not sections:
        raise ValueError("La lista di sezioni non può essere vuota")
    
    # Ordina per section_index per mantenere l'ordine
    sorted_sections = sorted(sections, key=lambda s: s.get('section_index', 0))
    
    lines = []
    
    for section in sorted_sections:
        title = section.get('title', '').strip()
        description = section.get('description', '').strip()
        level = section.get('level', 2)  # Default a livello 2 (capitolo)
        
        if not title:
            continue  # Salta sezioni senza titolo
        
        # Genera l'header markdown con il livello appropriato
        header_prefix = '#' * level
        lines.append(f"{header_prefix} {title}")
        lines.append("")  # Linea vuota dopo l'header
        
        # Aggiungi la descrizione se presente
        if description:
            # Mantieni la formattazione della descrizione (può contenere markdown)
            lines.append(description)
            lines.append("")  # Linea vuota dopo la descrizione
    
    return "\n".join(lines)


def format_writer_context(
    form_data: SubmissionRequest,
    question_answers: List[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    previous_chapters: List[Dict[str, Any]],
    current_section: Dict[str, str],
    story_bible: Optional[Dict[str, Any]] = None,
    is_long_form_part1: bool = False,
    is_long_form_part2: bool = False,
    part1_text: Optional[str] = None,
) -> str:
    """
    Formatta tutto il contesto per la scrittura di un capitolo.
    Include configurazione, trama, struttura, capitoli precedenti e sezione corrente.
    """
    lines = []
    
    # Titolo del romanzo
    if draft_title:
        lines.append(f"# TITOLO DEL ROMANZO: {draft_title}\n")
    
    # Configurazione iniziale
    lines.append("## CONFIGURAZIONE INIZIALE")
    lines.append(f"**Genere**: {form_data.genre or 'Non specificato'}")
    lines.append(f"**Sottogenere**: {form_data.subgenre or 'Non specificato'}")
    lines.append(f"**Stile**: {form_data.style or 'Non specificato'}")
    if form_data.author:
        lines.append(f"**Autore di riferimento (stile)**: {form_data.author}")
    if form_data.user_name:
        lines.append(f"**Autore del romanzo**: {form_data.user_name}")
    
    optional_fields = {
        "Pubblico di Riferimento": form_data.target_audience,
        "Tema": form_data.theme,
        "Protagonista": form_data.protagonist,
        "Archetipo Protagonista": form_data.protagonist_archetype,
        "Arco del personaggio": form_data.character_arc,
        "Punto di vista": form_data.point_of_view,
        "Voce narrante": form_data.narrative_voice,
        "Ritmo": form_data.pace,
        "Struttura temporale": form_data.temporal_structure,
        "Realismo": form_data.realism,
        "Ambiguità": form_data.ambiguity,
        "Intenzionalità": form_data.intentionality,
    }
    
    for label, value in optional_fields.items():
        if value:
            lines.append(f"**{label}**: {value}")
    
    lines.append("\n---\n")

    formatted_answers = _format_question_answers_for_writer(question_answers)
    if formatted_answers:
        lines.append("## RISPOSTE ALLE DOMANDE PRELIMINARI")
        lines.append("Questi chiarimenti esprimono preferenze e vincoli specifici dell'utente.")
        lines.append(formatted_answers)
        lines.append("\n---\n")
    
    if story_bible:
        lines.append("## STORY BIBLE DEL ROMANZO")
        lines.append("Usa questa memoria strutturata come guida primaria per mantenere continuità, vincoli e direzione narrativa.")

        creative_brief = story_bible.get("creative_brief", [])
        if creative_brief:
            lines.append("### Brief creativo")
            for item in creative_brief:
                lines.append(f"- {item}")

        premise = story_bible.get("premise")
        if premise:
            lines.append("\n### Premessa")
            lines.append(premise)

        draft_summary = story_bible.get("draft_summary")
        if draft_summary:
            lines.append("\n### Sintesi della bozza validata")
            lines.append(draft_summary)

        user_constraints = story_bible.get("user_constraints", [])
        if user_constraints:
            lines.append("\n### Vincoli espliciti dell'utente")
            for item in user_constraints:
                lines.append(f"- {item}")

        nearby_cards = get_nearby_chapter_cards(
            story_bible,
            current_section.get("section_index"),
        )
        if nearby_cards:
            lines.append("\n### Chapter Cards Rilevanti")
            for card in nearby_cards:
                relation = "Capitolo attuale"
                card_index = int(card.get("section_index", -1))
                current_index = current_section.get("section_index")
                if current_index is not None:
                    if card_index < current_index:
                        relation = "Contesto immediatamente precedente"
                    elif card_index > current_index:
                        relation = "Sviluppo immediatamente successivo"
                lines.append(f"- [{relation}] {card.get('title', '')}: {card.get('description', '')}")

        continuity_notes = get_relevant_continuity_notes(story_bible, previous_chapters)
        if continuity_notes:
            lines.append("\n### Continuità Consolidata")
            for note in continuity_notes:
                lines.append(f"- {note.get('title', '')}: {note.get('summary', '')}")

        recent_developments = story_bible.get("recent_developments", [])
        if recent_developments:
            lines.append("\n### Ultimi sviluppi già avvenuti")
            for item in recent_developments:
                lines.append(f"- {item}")

        lines.append("\n---\n")
    else:
        # Fallback legacy: usa bozza e outline completi se la story bible non è disponibile
        lines.append("## TRAMA ESTESA VALIDATA")
        lines.append("Questa è la fonte di verità per gli eventi principali e lo sviluppo narrativo.")
        lines.append(validated_draft)
        lines.append("\n---\n")

        lines.append("## STRUTTURA COMPLETA DEL ROMANZO")
        lines.append("Questa è la struttura completa. La sezione che devi scrivere è indicata di seguito.")
        lines.append(outline_text)
        lines.append("\n---\n")

    # Capitoli Precedenti (CONTESTO AUTOREGRESSIVO)
    if previous_chapters:
        lines.append("## CAPITOLI PRECEDENTI SCRITTI")
        lines.append("**IMPORTANTE**: Questi capitoli sono già stati scritti. DEVI mantenere la massima coerenza con:")
        lines.append("- Eventi già narrati")
        lines.append("- Caratterizzazione dei personaggi già stabilita")
        lines.append("- Atmosfere e toni già introdotti")
        lines.append("- Dettagli di ambientazione già forniti")
        lines.append("- Stile narrativo già utilizzato\n")

        chapters_for_prompt = previous_chapters
        if story_bible:
            chapters_for_prompt = get_recent_full_chapters(previous_chapters)
            lines.append("Per evitare ridondanza, hai il testo integrale solo degli ultimi capitoli; per il resto usa la continuità sintetica della story bible.\n")

        for i, chapter in enumerate(chapters_for_prompt, 1):
            title = chapter.get('title', f'Capitolo {i}')
            content = chapter.get('content', '')
            lines.append(f"### {title}")
            lines.append(content)
            lines.append("\n")

        lines.append("---\n")
    
    # Sezione Corrente da Scrivere
    lines.append("## SEZIONE DA SCRIVERE ORA")
    lines.append(f"**Titolo**: {current_section['title']}")
    lines.append(f"**Descrizione**:")
    lines.append(current_section['description'])
    lines.append("\n")
    
    # Istruzioni specifiche per modalità Long Form
    if is_long_form_part1:
        lines.append("**Istruzioni (Modalità Estesa - Parte 1 di 2)**:")
        lines.append("- Scrivi SOLO la prima parte (circa 50-60%) di questa sezione.")
        # lines.append("- Mantieni un ritmo lento e dettagliato: esplora descrizioni sensoriali, dialoghi estesi, riflessioni interiori.")
        lines.append("- **VINCOLO CRITICO**: NON concludere la sezione. NON risolvere tutti gli eventi descritti nell'outline.")
        lines.append("- Fermati a un punto intermedio logico nell'azione, prima di completare tutti gli eventi previsti.")
        lines.append("- L'obiettivo è creare profondità narrativa, non arrivare alla fine.")
        lines.append("- Mantieni coerenza assoluta con i capitoli precedenti.")
        lines.append("- Elabora i primi elementi narrativi indicati nella descrizione con grande dettaglio.")
        lines.append("- Inizia direttamente con la narrazione, senza titoli o numerazioni.")
    elif is_long_form_part2:
        lines.append("**Istruzioni (Modalità Estesa - Parte 2 di 2)**:")
        lines.append("- Ecco la prima parte della sezione che hai appena scritto:")
        lines.append("\n[INIZIO PARTE 1]")
        lines.append(part1_text or "")
        lines.append("[FINE PARTE 1]\n")
        lines.append("- **OBIETTIVO**: Continua la narrazione ESATTAMENTE da dove si è interrotta la Parte 1.")
        lines.append("- Mantieni lo stesso stile, ritmo e livello di dettaglio della prima parte.")
        lines.append("- NON riassumere ciò che è già accaduto nella Parte 1. Continua l'azione come se fosse un flusso unico.")
        lines.append("- Completa gli eventi descritti nell'outline della sezione che non sono stati ancora narrati.")
        lines.append("- Porta la sezione a una conclusione naturale, rispettando la descrizione dell'outline.")
        lines.append("- Mantieni coerenza assoluta con i capitoli precedenti e con la Parte 1 appena scritta.")
        lines.append("- Inizia direttamente continuando la narrazione, senza titoli o numerazioni.")
    else:
        # Istruzioni standard
        lines.append("**Istruzioni**:")
        lines.append("- Scrivi questa sezione seguendo la descrizione fornita.")
        lines.append("- Mantieni coerenza assoluta con i capitoli precedenti.")
        lines.append("- Elabora tutti i temi e sviluppi narrativi indicati nella descrizione.")
        lines.append("- **Stratificazione**: Arricchisci la narrazione con:")
        lines.append("  * Descrizioni sensoriali dettagliate (cosa si vede, sente, percepisce)")
        lines.append("  * Dialoghi sviluppati che rivelano carattere e relazioni")
        lines.append("  * Riflessioni interiori dei personaggi")
        lines.append("  * Scene intermedie che approfondiscono atmosfere e temi")
        lines.append("  * Dettagli ambientali che creano contesto narrativo")
        lines.append("  * Sviluppi graduali che richiedono tempo narrativo per maturare")
        lines.append("- Non avere fretta: sviluppa ogni elemento con la profondità necessaria per creare un'esperienza immersiva.")
        lines.append("- Inizia direttamente con la narrazione, senza titoli o numerazioni.")
    
    return "\n".join(lines)


def map_model_name(model_name: str) -> str:
    """Mappa il nome del modello utente al nome corretto per Gemini API."""
    if "gemini-2.5-flash" in model_name.lower():
        return "gemini-2.5-flash"
    elif "gemini-2.5-pro" in model_name.lower():
        return "gemini-2.5-pro"
    elif "gemini-3-flash" in model_name.lower():
        return "gemini-3-flash-preview"
    elif "gemini-3-pro" in model_name.lower() or "gemini-3.1-pro" in model_name.lower():
        return "gemini-3.1-pro-preview"
    elif "gemini-3-ultra" in model_name.lower():
        # Gemini 3 Ultra usa Gemini 3 Pro come motore sottostante
        return "gemini-3.1-pro-preview"
    else:
        return "gemini-2.5-flash"  # default


def get_max_output_tokens(model_name: str) -> int:
    """
    Determina il max_output_tokens in base al modello.
    
    Args:
        model_name: Nome del modello Gemini (dopo mappatura o originale)
    
    Returns:
        Numero massimo di token di output
    """
    app_config = get_app_config()
    tokens_config = app_config.get("llm_models", {}).get("max_output_tokens", {})
    
    # Flash 2.5 ha limite più basso
    if "gemini-2.5-flash" in model_name.lower():
        return tokens_config.get("gemini_2_5_flash", 8192)
    
    # Gemini 3 Ultra usa il limite massimo (mappato a Pro)
    if "gemini-3-ultra" in model_name.lower():
        return tokens_config.get("default", 65536)
    
    # Tutti gli altri modelli (Pro 2.5, Flash 3, Pro 3) usano il default
    return tokens_config.get("default", 65536)


async def _generate_chapter_part(
    agent_context: str,
    formatted_context: str,
    gemini_model: str,
    api_key: str,
    current_section_title: str,
) -> tuple[str, dict[str, int]]:
    """
    Helper per generare una parte di un capitolo (usato per modalità Long Form).
    
    Args:
        agent_context: Contesto dell'agente scrittore
        formatted_context: Contesto formattato con tutte le informazioni
        gemini_model: Nome del modello Gemini (dopo mappatura)
        api_key: API key per Gemini
        current_section_title: Titolo della sezione corrente (per logging)
    
    Returns:
        Tupla (part_text, token_usage)
    """
    # Determina max_output_tokens
    max_tokens = get_max_output_tokens(gemini_model)
    
    # Crea il prompt
    system_prompt = SystemMessage(content=agent_context)
    user_prompt_content = f"""Scrivi la sezione del romanzo indicata di seguito.

{formatted_context}

Scrivi SOLO il testo narrativo della sezione, senza titoli o numerazioni. Inizia direttamente con la narrazione."""
    
    user_prompt = HumanMessage(content=user_prompt_content)
    
    # Inizializza il modello Gemini con timeout configurato
    temperature = get_temperature_for_agent("writer_generator", gemini_model)
    llm = ChatGoogleGenerativeAI(
        model=gemini_model,
        google_api_key=api_key,
        temperature=temperature,
        max_output_tokens=max_tokens,
        timeout=CHAPTER_GENERATION_TIMEOUT,  # Timeout esplicito
    )
    
    # Genera la parte del capitolo con retry automatico
    last_error = None
    for attempt in range(CHAPTER_GENERATION_MAX_RETRIES):
        try:
            response = await llm.ainvoke([system_prompt, user_prompt])
            part_text = _coerce_llm_content_to_text(response.content).strip()
            
            # Estrai token usage dalla risposta
            token_usage = extract_token_usage(response)
            token_usage["model"] = gemini_model
            
            # Validazione base
            if not part_text or len(part_text.strip()) < 20:
                raise ValueError(
                    f"Parte del capitolo generata vuota o troppo corta per '{current_section_title}': "
                    f"{len(part_text) if part_text else 0} caratteri"
                )
            
            # Successo: log e ritorna
            if attempt > 0:
                print(f"[WRITER] Generazione riuscita al tentativo {attempt + 1} per '{current_section_title}'")
            return part_text, token_usage
            
        except Exception as e:
            last_error = e
            is_retryable = _is_retryable_error(e)
            
            if is_retryable and attempt < CHAPTER_GENERATION_MAX_RETRIES - 1:
                delay = CHAPTER_GENERATION_RETRY_DELAY * (attempt + 1)  # Backoff lineare
                print(f"[WRITER] Tentativo {attempt + 1}/{CHAPTER_GENERATION_MAX_RETRIES} fallito per '{current_section_title}': {type(e).__name__}")
                print(f"[WRITER] Errore recuperabile, riprovo tra {delay}s...")
                await asyncio.sleep(delay)
            else:
                # Non recuperabile o ultimo tentativo
                if attempt > 0:
                    print(f"[WRITER] Tutti i {CHAPTER_GENERATION_MAX_RETRIES} tentativi falliti per '{current_section_title}'")
                raise
    
    # Non dovremmo mai arrivare qui, ma per sicurezza
    raise last_error if last_error else Exception(f"Generazione fallita per '{current_section_title}'")


async def generate_chapter(
    form_data: SubmissionRequest,
    question_answers: List[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    previous_chapters: List[Dict[str, Any]],
    current_section: Dict[str, str],
    story_bible: Optional[Dict[str, Any]],
    api_key: str,
) -> tuple[str, dict[str, int]]:
    """
    Genera il testo di un singolo capitolo/sezione usando il contesto completo.
    
    Supporta due modalità:
    - Standard: 1 chiamata singola (comportamento normale)
    - Long Form (gemini-3-ultra): 2 chiamate sequenziali per capitoli più estesi
    
    Args:
        form_data: Dati del form iniziale
        question_answers: Risposte alle domande preliminari
        validated_draft: Bozza estesa validata
        draft_title: Titolo del romanzo
        outline_text: Struttura completa del romanzo
        previous_chapters: Lista di capitoli già scritti (per autoregressione)
        current_section: Dizionario con 'title' e 'description' della sezione corrente
        story_bible: Memoria narrativa strutturata della sessione
        api_key: API key per Gemini
    
    Returns:
        Tupla (chapter_text, token_usage)
        token_usage contiene {"input_tokens": int, "output_tokens": int, "model": str}
    """
    # Carica il contesto dell'agente
    agent_context = load_writer_agent_context()
    
    # Determina se siamo in modalità Long Form
    is_long_form = form_data.llm_model.lower() == "gemini-3-ultra"
    
    # Mappa il modello (gemini-3-ultra -> gemini-3.1-pro-preview)
    gemini_model = map_model_name(form_data.llm_model)
    
    print(f"[WRITER] Modello originale: {form_data.llm_model}, mappato a: {gemini_model}, Long Form: {is_long_form}")
    
    if is_long_form:
        # MODALITÀ LONG FORM: 2 chiamate sequenziali
        print(f"[WRITER] Modalità Long Form attivata per '{current_section['title']}' - Generazione in 2 step")
        
        # STEP 1: Prima parte (50-60%)
        print(f"[WRITER] Step 1/2: Generazione prima parte...")
        formatted_context_part1 = format_writer_context(
            form_data=form_data,
            question_answers=question_answers,
            validated_draft=validated_draft,
            draft_title=draft_title,
            outline_text=outline_text,
            previous_chapters=previous_chapters,
            current_section=current_section,
            story_bible=story_bible,
            is_long_form_part1=True,
        )
        
        try:
            part1_text, token_usage_part1 = await _generate_chapter_part(
                agent_context=agent_context,
                formatted_context=formatted_context_part1,
                gemini_model=gemini_model,
                api_key=api_key,
                current_section_title=current_section['title'],
            )
            print(f"[WRITER] Step 1/2 completato: {len(part1_text)} caratteri, {token_usage_part1['input_tokens']}+{token_usage_part1['output_tokens']} tokens")
        except Exception as e:
            raise Exception(f"Errore nella generazione della prima parte del capitolo '{current_section['title']}': {str(e)}")
        
        # STEP 2: Seconda parte (completamento)
        print(f"[WRITER] Step 2/2: Generazione seconda parte...")
        formatted_context_part2 = format_writer_context(
            form_data=form_data,
            question_answers=question_answers,
            validated_draft=validated_draft,
            draft_title=draft_title,
            outline_text=outline_text,
            previous_chapters=previous_chapters,
            current_section=current_section,
            story_bible=story_bible,
            is_long_form_part2=True,
            part1_text=part1_text,
        )
        
        try:
            part2_text, token_usage_part2 = await _generate_chapter_part(
                agent_context=agent_context,
                formatted_context=formatted_context_part2,
                gemini_model=gemini_model,
                api_key=api_key,
                current_section_title=current_section['title'],
            )
            print(f"[WRITER] Step 2/2 completato: {len(part2_text)} caratteri, {token_usage_part2['input_tokens']}+{token_usage_part2['output_tokens']} tokens")
        except Exception as e:
            raise Exception(f"Errore nella generazione della seconda parte del capitolo '{current_section['title']}': {str(e)}")
        
        # Unione delle due parti
        chapter_text = f"{part1_text}\n\n{part2_text}".strip()
        
        # Combina token usage delle due parti
        token_usage = {
            "input_tokens": token_usage_part1.get("input_tokens", 0) + token_usage_part2.get("input_tokens", 0),
            "output_tokens": token_usage_part1.get("output_tokens", 0) + token_usage_part2.get("output_tokens", 0),
            "model": gemini_model,
        }
        
        # Validazione finale
        app_config = get_app_config()
        chapter_text = validate_generated_chapter_text(
            chapter_text,
            current_section['title'],
            app_config=app_config,
        )

        review_context = format_writer_context(
            form_data=form_data,
            question_answers=question_answers,
            validated_draft=validated_draft,
            draft_title=draft_title,
            outline_text=outline_text,
            previous_chapters=previous_chapters,
            current_section=current_section,
            story_bible=story_bible,
        )
        chapter_text, review_token_usage = await review_and_maybe_revise_chapter(
            agent_context=agent_context,
            formatted_context=review_context,
            gemini_model=gemini_model,
            api_key=api_key,
            form_data=form_data,
            current_section=current_section,
            story_bible=story_bible,
            chapter_text=chapter_text,
        )
        token_usage = _combine_token_usage(token_usage, review_token_usage)
        
        print(f"[WRITER] Capitolo Long Form '{current_section['title']}' generato con successo: {len(chapter_text)} caratteri totali (Parte 1: {len(part1_text)}, Parte 2: {len(part2_text)})")
        print(f"[WRITER] Token totali capitolo: {token_usage['input_tokens']} input, {token_usage['output_tokens']} output")
        return chapter_text, token_usage
    
    else:
        # MODALITÀ STANDARD: 1 chiamata singola
        formatted_context = format_writer_context(
            form_data=form_data,
            question_answers=question_answers,
            validated_draft=validated_draft,
            draft_title=draft_title,
            outline_text=outline_text,
            previous_chapters=previous_chapters,
            current_section=current_section,
            story_bible=story_bible,
        )
        
        # Determina max_output_tokens in base al modello
        max_tokens = get_max_output_tokens(gemini_model)
        print(f"[WRITER] Modello: {gemini_model}, max_output_tokens: {max_tokens}")
        
        # Crea il prompt
        system_prompt = SystemMessage(content=agent_context)
        user_prompt_content = f"""Scrivi la sezione del romanzo indicata di seguito.

{formatted_context}

Scrivi SOLO il testo narrativo della sezione, senza titoli o numerazioni. Inizia direttamente con la narrazione."""
        
        user_prompt = HumanMessage(content=user_prompt_content)
        
        # Inizializza il modello Gemini con timeout configurato
        temperature = get_temperature_for_agent("writer_generator", gemini_model)
        llm = ChatGoogleGenerativeAI(
            model=gemini_model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
            timeout=CHAPTER_GENERATION_TIMEOUT,  # Timeout esplicito
        )
        
        # Genera il capitolo con retry automatico
        last_error = None
        for attempt in range(CHAPTER_GENERATION_MAX_RETRIES):
            try:
                response = await llm.ainvoke([system_prompt, user_prompt])
                chapter_text = _coerce_llm_content_to_text(response.content).strip()
                
                # Estrai token usage dalla risposta
                token_usage = extract_token_usage(response)
                token_usage["model"] = gemini_model
                
                app_config = get_app_config()
                chapter_text = validate_generated_chapter_text(
                    chapter_text,
                    current_section['title'],
                    app_config=app_config,
                )
                chapter_text, review_token_usage = await review_and_maybe_revise_chapter(
                    agent_context=agent_context,
                    formatted_context=formatted_context,
                    gemini_model=gemini_model,
                    api_key=api_key,
                    form_data=form_data,
                    current_section=current_section,
                    story_bible=story_bible,
                    chapter_text=chapter_text,
                )
                token_usage = _combine_token_usage(token_usage, review_token_usage)
                
                # Successo
                if attempt > 0:
                    print(f"[WRITER] Generazione riuscita al tentativo {attempt + 1} per '{current_section['title']}'")
                print(f"[WRITER] Capitolo '{current_section['title']}' generato con successo: {len(chapter_text)} caratteri")
                print(f"[WRITER] Token usage: {token_usage['input_tokens']} input, {token_usage['output_tokens']} output")
                return chapter_text, token_usage
                
            except Exception as e:
                last_error = e
                is_retryable = _is_retryable_error(e)
                
                if is_retryable and attempt < CHAPTER_GENERATION_MAX_RETRIES - 1:
                    delay = CHAPTER_GENERATION_RETRY_DELAY * (attempt + 1)  # Backoff lineare
                    print(f"[WRITER] Tentativo {attempt + 1}/{CHAPTER_GENERATION_MAX_RETRIES} fallito per '{current_section['title']}': {type(e).__name__}")
                    print(f"[WRITER] Errore recuperabile, riprovo tra {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Non recuperabile o ultimo tentativo
                    if attempt > 0:
                        print(f"[WRITER] Tutti i {CHAPTER_GENERATION_MAX_RETRIES} tentativi falliti per '{current_section['title']}'")
                    raise Exception(f"Errore nella generazione del capitolo '{current_section['title']}': {str(e)}")
        
        # Fallback (non dovremmo mai arrivare qui)
        raise last_error if last_error else Exception(f"Generazione fallita per '{current_section['title']}'")


async def generate_full_book(
    session_id: str,
    form_data: SubmissionRequest,
    question_answers: List[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    api_key: str,
) -> List[Dict[str, Any]]:
    """
    Genera l'intero romanzo sezione per sezione in modo autoregressivo.
    
    Args:
        session_id: ID della sessione
        form_data: Dati del form iniziale
        question_answers: Risposte alle domande preliminari
        validated_draft: Bozza estesa validata
        draft_title: Titolo del romanzo
        outline_text: Struttura completa del romanzo
        api_key: API key per Gemini
    
    Returns:
        Lista di dizionari con 'title', 'content', 'section_index' per ogni capitolo
    """
    session_store = get_session_store()
    
    # Parsa l'outline (già validato nell'endpoint, ma lo rifacciamo per sicurezza)
    print(f"[WRITER] Parsing outline per sessione {session_id}...")
    sections = parse_outline_sections(outline_text)
    total_sections = len(sections)
    
    # Verifica che il progresso sia già stato inizializzato dall'endpoint
    # Se non lo è, lo inizializziamo qui (fallback)
    existing_progress = await get_session_async(session_store, session_id, user_id=None)
    if existing_progress and existing_progress.writing_progress:
        existing_total = existing_progress.writing_progress.get('total_steps', 0)
        if existing_total != total_sections:
            print(f"[WRITER] WARNING: total_steps nel progresso ({existing_total}) != sezioni trovate ({total_sections}). Aggiorno.")
            await update_writing_progress_async(
                session_store,
                session_id=session_id,
                current_step=0,
                total_steps=total_sections,
                current_section_name=sections[0]['title'] if sections else None,
                is_complete=False,
                is_paused=False,
            )
    else:
        # Progresso non inizializzato, lo inizializziamo qui
        print(f"[WRITER] Progresso non trovato, inizializzazione...")
        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=0,
            total_steps=total_sections,
            current_section_name=sections[0]['title'] if sections else None,
            is_complete=False,
            is_paused=False,
        )
    
    session = await get_session_async(session_store, session_id, user_id=None)
    if not session:
        raise ValueError(f"Sessione {session_id} non trovata durante la preparazione della story bible")
    story_bible = await refresh_story_bible_for_session(session_store, session, sections)

    completed_chapters = []
    
    # Loop autoregressivo: per ogni sezione
    for index, section in enumerate(sections):
        print(f"[WRITER] === Scrittura sezione {index + 1}/{total_sections}: {section['title']} ===")
        
        # Aggiorna il progresso PRIMA di iniziare la generazione
        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=index,
            total_steps=total_sections,
            current_section_name=section['title'],
            is_complete=False,
            is_paused=False,
        )
        print(f"[WRITER] Progresso aggiornato: {index}/{total_sections}")
        
        # Retry logic per capitoli vuoti
        app_config = get_app_config()
        retry_config = app_config.get("retry", {}).get("chapter_generation", {})
        max_retries = retry_config.get("max_retries", 2)
        chapter_content = None
        
        # Inizia tracciamento tempo capitolo
        print(f"[WRITER] Inizio tracciamento tempo per capitolo '{section['title']}'")
        await start_chapter_timing_async(session_store, session_id)
        
        for retry in range(max_retries):
            try:
                # Genera il capitolo con contesto autoregressivo
                if retry > 0:
                    print(f"[WRITER] Retry {retry}/{max_retries - 1} per capitolo '{section['title']}'...")
                else:
                    print(f"[WRITER] Chiamata a generate_chapter per '{section['title']}'...")
                
                chapter_content, chapter_token_usage = await generate_chapter(
                    form_data=form_data,
                    question_answers=question_answers,
                    validated_draft=validated_draft,
                    draft_title=draft_title,
                    outline_text=outline_text,
                    previous_chapters=completed_chapters,  # Passa i capitoli già scritti
                    current_section=section,
                    story_bible=story_bible,
                    api_key=api_key,
                )
                
                # Aggiorna token usage per la fase chapters
                await update_token_usage_async(
                    session_store,
                    session_id,
                    phase="chapters",
                    input_tokens=chapter_token_usage.get("input_tokens", 0),
                    output_tokens=chapter_token_usage.get("output_tokens", 0),
                    model=chapter_token_usage.get("model", "gemini-3.1-pro-preview"),
                )
                
                # Verifica che il contenuto sia valido
                app_config = get_app_config()
                chapter_content = validate_generated_chapter_text(
                    chapter_content,
                    section['title'],
                    app_config=app_config,
                )
                print(f"[WRITER] Capitolo generato con successo: {len(chapter_content)} caratteri")
                # Termina tracciamento tempo capitolo
                await end_chapter_timing_async(session_store, session_id)
                session = await get_session_async(session_store, session_id, user_id=None)
                if session and session.chapter_timings:
                    print(f"[WRITER] Tempo capitolo salvato: {session.chapter_timings[-1]:.1f} secondi. Totale timings: {len(session.chapter_timings)}")
                    # Logging dettagliato per Ultra
                    if form_data.llm_model.lower() == "gemini-3-ultra":
                        last_timing = session.chapter_timings[-1]
                        print(f"[WRITER] [ULTRA] Timing capitolo '{section['title']}' salvato: {last_timing:.1f} secondi")
                        print(f"[WRITER] [ULTRA] Questo timing include entrambe le chiamate API (part1 + part2)")
                        print(f"[WRITER] [ULTRA] Totale timings salvati: {len(session.chapter_timings)}")
                break
                        
            except ValueError as ve:
                # Errore di validazione (capitolo vuoto)
                if retry < max_retries - 1:
                    print(f"[WRITER] WARNING: {str(ve)}, retry {retry + 1}/{max_retries - 1}...")
                    continue
                else:
                    error_msg = f"Contenuto non valido per la sezione '{section['title']}' dopo {max_retries} tentativi: {str(ve)}"
                    print(f"[WRITER] ERRORE: {error_msg} - Mettendo in pausa la generazione")
                    await end_chapter_timing_async(session_store, session_id)
                    await pause_writing_async(
                        session_store,
                        session_id=session_id,
                        current_step=index,
                        total_steps=total_sections,
                        current_section_name=section['title'],
                        error_msg=error_msg,
                    )
                    print(f"[WRITER] Generazione messa in pausa. Capitoli completati: {len(completed_chapters)}/{total_sections}")
                    return completed_chapters
                    
            except Exception as e:
                # Altri errori: se non è l'ultimo tentativo, riprova
                if retry < max_retries - 1:
                    print(f"[WRITER] WARNING: Errore nella generazione: {str(e)}, retry {retry + 1}/{max_retries - 1}...")
                    continue
                else:
                    # Ultimo tentativo fallito: metti in pausa invece di rilanciare
                    error_msg = f"Errore nella generazione della sezione '{section['title']}': {str(e)}"
                    print(f"[WRITER] ERRORE: {error_msg} - Mettendo in pausa la generazione")
                    # Termina tracciamento tempo anche in caso di errore critico
                    await end_chapter_timing_async(session_store, session_id)
                    import traceback
                    traceback.print_exc()
                    
                    # Metti in pausa la generazione invece di rilanciare l'eccezione
                    await pause_writing_async(
                        session_store,
                        session_id=session_id,
                        current_step=index,
                        total_steps=total_sections,
                        current_section_name=section['title'],
                        error_msg=error_msg,
                    )
                    # Restituisci i capitoli completati finora invece di rilanciare
                    print(f"[WRITER] Generazione messa in pausa. Capitoli completati: {len(completed_chapters)}/{total_sections}")
                    return completed_chapters
        
        # Se siamo arrivati qui, abbiamo un contenuto (valido o placeholder)
        if chapter_content:
            # Salva il capitolo completato
            chapter_dict = {
                'title': section['title'],
                'content': chapter_content,
                'section_index': index,
            }
            
            session = await update_book_chapter_async(
                session_store,
                session_id=session_id,
                chapter_title=section['title'],
                chapter_content=chapter_content,
                section_index=index,
            )
            print(f"[WRITER] Capitolo salvato nella sessione")
            
            completed_chapters.append(chapter_dict)
            story_bible = await refresh_story_bible_for_session(session_store, session, sections)
            print(f"[WRITER] OK - Sezione {index + 1}/{total_sections} completata: {len(chapter_content)} caratteri")
    
    # Calcola total_pages per la libreria (ottimizzazione performance)
    chapters_pages = sum(calculate_page_count(ch.get('content', '')) for ch in completed_chapters)
    cover_pages = 1
    app_config = get_app_config()
    toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
    toc_pages = math.ceil(len(completed_chapters) / toc_chapters_per_page) if completed_chapters else 0
    total_pages = chapters_pages + cover_pages + toc_pages
    
    # Marca come completato con total_pages pre-calcolato
    await update_writing_progress_async(
        session_store,
        session_id=session_id,
        current_step=total_sections,
        total_steps=total_sections,
        current_section_name=None,
        is_complete=True,
        is_paused=False,
        total_pages=total_pages,
        completed_chapters_count=len(completed_chapters),
    )
    
    print(f"[WRITER] Scrittura completata: {total_sections} sezioni scritte, {total_pages} pagine")
    
    return completed_chapters


async def resume_book_generation(
    session_id: str,
    api_key: str,
) -> List[Dict[str, Any]]:
    """
    Riprende la generazione del libro dal capitolo fallito.
    
    Args:
        session_id: ID della sessione
        api_key: API key per Gemini
    
    Returns:
        Lista di dizionari con 'title', 'content', 'section_index' per ogni capitolo
    """
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)
    
    if not session:
        raise ValueError(f"Sessione {session_id} non trovata")
    
    if not session.writing_progress:
        raise ValueError(f"Sessione {session_id} non ha uno stato di scrittura")
    
    progress = session.writing_progress
    if not progress.get("is_paused", False):
        raise ValueError(f"Sessione {session_id} non è in stato di pausa")
    
    # Riprendi lo stato di pausa
    await resume_writing_async(session_store, session_id)
    
    # Recupera i dati necessari dalla sessione
    form_data = session.form_data
    question_answers = session.question_answers
    validated_draft = session.current_draft
    draft_title = session.current_title
    outline_text = session.current_outline
    
    if not validated_draft or not outline_text:
        raise ValueError(f"Sessione {session_id} non ha bozza validata o outline")
    
    # Parsa l'outline
    sections = parse_outline_sections(outline_text)
    total_sections = len(sections)
    
    # Recupera i capitoli già completati
    completed_chapters = session.book_chapters.copy()
    story_bible = await refresh_story_bible_for_session(session_store, session, sections)
    
    # Identifica il capitolo da cui riprendere (quello fallito)
    failed_step = progress.get("current_step", 0)
    
    print(f"[WRITER] Ripresa generazione per sessione {session_id}")
    print(f"[WRITER] Capitoli già completati: {len(completed_chapters)}/{total_sections}")
    print(f"[WRITER] Riprendo dal capitolo {failed_step + 1}/{total_sections}: {sections[failed_step]['title'] if failed_step < len(sections) else 'N/A'}")
    
    # Riprendi la generazione dal capitolo fallito
    # Usa la stessa logica di generate_full_book ma partendo da failed_step
    app_config = get_app_config()
    retry_config = app_config.get("retry", {}).get("chapter_generation", {})
    max_retries = retry_config.get("max_retries", 2)
    
    # Loop autoregressivo: continua dal capitolo fallito
    for index in range(failed_step, total_sections):
        section = sections[index]
        print(f"[WRITER] === Scrittura sezione {index + 1}/{total_sections}: {section['title']} ===")
        
        # Aggiorna il progresso PRIMA di iniziare la generazione
        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=index,
            total_steps=total_sections,
            current_section_name=section['title'],
            is_complete=False,
            is_paused=False,
        )
        print(f"[WRITER] Progresso aggiornato: {index}/{total_sections}")
        
        # Retry logic per capitoli vuoti
        chapter_content = None
        
        # Inizia tracciamento tempo capitolo
        print(f"[WRITER] Inizio tracciamento tempo per capitolo '{section['title']}'")
        await start_chapter_timing_async(session_store, session_id)
        
        for retry in range(max_retries):
            try:
                # Genera il capitolo con contesto autoregressivo
                if retry > 0:
                    print(f"[WRITER] Retry {retry}/{max_retries - 1} per capitolo '{section['title']}'...")
                else:
                    print(f"[WRITER] Chiamata a generate_chapter per '{section['title']}'...")
                
                chapter_content, chapter_token_usage = await generate_chapter(
                    form_data=form_data,
                    question_answers=question_answers,
                    validated_draft=validated_draft,
                    draft_title=draft_title,
                    outline_text=outline_text,
                    previous_chapters=completed_chapters,
                    current_section=section,
                    story_bible=story_bible,
                    api_key=api_key,
                )

                await update_token_usage_async(
                    session_store,
                    session_id,
                    phase="chapters",
                    input_tokens=chapter_token_usage.get("input_tokens", 0),
                    output_tokens=chapter_token_usage.get("output_tokens", 0),
                    model=chapter_token_usage.get("model", "gemini-3.1-pro-preview"),
                )

                # Verifica che il contenuto sia valido
                chapter_content = validate_generated_chapter_text(
                    chapter_content,
                    section['title'],
                    app_config=app_config,
                )

                print(f"[WRITER] Capitolo generato con successo: {len(chapter_content)} caratteri")
                await end_chapter_timing_async(session_store, session_id)
                session = await get_session_async(session_store, session_id, user_id=None)
                if session and session.chapter_timings:
                    print(f"[WRITER] Tempo capitolo salvato: {session.chapter_timings[-1]:.1f} secondi. Totale timings: {len(session.chapter_timings)}")
                break
                        
            except ValueError as ve:
                if retry < max_retries - 1:
                    print(f"[WRITER] WARNING: {str(ve)}, retry {retry + 1}/{max_retries - 1}...")
                    continue
                else:
                    error_msg = f"Contenuto non valido per la sezione '{section['title']}' dopo {max_retries} tentativi: {str(ve)}"
                    print(f"[WRITER] ERRORE: {error_msg} - Mettendo in pausa la generazione")
                    await end_chapter_timing_async(session_store, session_id)
                    await pause_writing_async(
                        session_store,
                        session_id=session_id,
                        current_step=index,
                        total_steps=total_sections,
                        current_section_name=section['title'],
                        error_msg=error_msg,
                    )
                    print(f"[WRITER] Generazione messa in pausa. Capitoli completati: {len(completed_chapters)}/{total_sections}")
                    return completed_chapters
                    
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"[WRITER] WARNING: Errore nella generazione: {str(e)}, retry {retry + 1}/{max_retries - 1}...")
                    continue
                else:
                    # Ultimo tentativo fallito: metti in pausa invece di rilanciare
                    error_msg = f"Errore nella generazione della sezione '{section['title']}': {str(e)}"
                    print(f"[WRITER] ERRORE: {error_msg} - Mettendo in pausa la generazione")
                    await end_chapter_timing_async(session_store, session_id)
                    import traceback
                    traceback.print_exc()
                    
                    # Metti in pausa la generazione invece di rilanciare l'eccezione
                    await pause_writing_async(
                        session_store,
                        session_id=session_id,
                        current_step=index,
                        total_steps=total_sections,
                        current_section_name=section['title'],
                        error_msg=error_msg,
                    )
                    # Restituisci i capitoli completati finora invece di rilanciare
                    print(f"[WRITER] Generazione messa in pausa. Capitoli completati: {len(completed_chapters)}/{total_sections}")
                    return completed_chapters
        
        # Se siamo arrivati qui, abbiamo un contenuto valido
        if chapter_content:
            # Salva il capitolo completato
            chapter_dict = {
                'title': section['title'],
                'content': chapter_content,
                'section_index': index,
            }
            session = await update_book_chapter_async(
                session_store,
                session_id=session_id,
                chapter_title=section['title'],
                chapter_content=chapter_content,
                section_index=index,
            )
            completed_chapters.append(chapter_dict)
            story_bible = await refresh_story_bible_for_session(session_store, session, sections)
            print(f"[WRITER] OK - Sezione {index + 1}/{total_sections} completata: {len(chapter_content)} caratteri")
    
    # Calcola total_pages per la libreria (ottimizzazione performance)
    chapters_pages = sum(calculate_page_count(ch.get('content', '')) for ch in completed_chapters)
    cover_pages = 1
    app_config = get_app_config()
    toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
    toc_pages = math.ceil(len(completed_chapters) / toc_chapters_per_page) if completed_chapters else 0
    total_pages = chapters_pages + cover_pages + toc_pages
    
    # Marca come completato con total_pages pre-calcolato
    await update_writing_progress_async(
        session_store,
        session_id=session_id,
        current_step=total_sections,
        total_steps=total_sections,
        current_section_name=None,
        is_complete=True,
        is_paused=False,
        total_pages=total_pages,
        completed_chapters_count=len(completed_chapters),
    )
    
    print(f"[WRITER] Scrittura completata: {total_sections} sezioni scritte, {total_pages} pagine")
    
    return completed_chapters


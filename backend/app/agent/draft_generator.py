import os
from pathlib import Path
from typing import Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.models import SubmissionRequest, QuestionAnswer
from app.agent.session_store import get_session_store


def load_draft_agent_context() -> str:
    """Carica il contesto dell'agente di bozza dal file Markdown."""
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "draft_agent_context.md"
    
    if not config_path.exists():
        raise FileNotFoundError(f"File di contesto agente bozza non trovato: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return f.read()


def format_form_data_for_draft(form_data: SubmissionRequest) -> str:
    """Formatta i dati del form in una stringa leggibile per il prompt."""
    lines = [f"**Trama iniziale**: {form_data.plot}"]
    
    # Aggiunge solo i campi compilati
    optional_fields = {
        "Nome Autore": form_data.user_name,
        "Genere": form_data.genre,
        "Sottogenere": form_data.subgenre,
        "Tema": form_data.theme,
        "Protagonista": form_data.protagonist,
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


def map_model_name(model_name: str) -> str:
    """Mappa il nome del modello utente al nome corretto per Gemini API."""
    if "gemini-2.5-flash" in model_name:
        return "gemini-2.5-flash"
    elif "gemini-2.5-pro" in model_name:
        return "gemini-2.5-pro"
    elif "gemini-3-flash" in model_name:
        return "gemini-3-flash-preview"
    elif "gemini-3-pro" in model_name:
        return "gemini-3-pro-preview"
    else:
        return "gemini-2.5-flash"  # default


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


def parse_draft_output(llm_output: str) -> tuple[str, str]:
    """
    Estrae titolo e trama dall'output del LLM.
    
    Args:
        llm_output: Output completo del LLM
    
    Returns:
        Tupla (title, draft_text)
    """
    lines = llm_output.split('\n')
    title = None
    draft_text = ""
    found_title = False
    found_trama = False
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Cerca "TITOLO:"
        if not found_title and line_stripped.upper().startswith("TITOLO:"):
            title = line_stripped[7:].strip()  # Rimuove "TITOLO:"
            found_title = True
            continue
        
        # Cerca "TRAMA:" o "TRAMA"
        if not found_trama and (line_stripped.upper().startswith("TRAMA:") or line_stripped.upper() == "TRAMA"):
            found_trama = True
            # Se c'è testo dopo "TRAMA:", includilo
            if line_stripped.upper().startswith("TRAMA:"):
                remaining = line_stripped[6:].strip()
                if remaining:
                    draft_text = remaining + "\n"
            continue
        
        # Se abbiamo trovato "TRAMA:", aggiungi tutte le righe successive
        if found_trama:
            draft_text += line + "\n"
    
    # Se non abbiamo trovato il formato previsto, usa tutto come draft_text
    if not found_title or not found_trama:
        # Fallback: cerca il primo titolo markdown (# Titolo) o usa tutto come draft
        if not found_title:
            # Prova a estrarre un titolo markdown
            for line in lines:
                if line.strip().startswith("# "):
                    title = line.strip()[2:].strip()
                    break
            if not title:
                title = "Titolo non specificato"
        
        if not found_trama:
            draft_text = llm_output
    
    return title or "Titolo non specificato", draft_text.strip()


async def generate_draft(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    session_id: str,
    api_key: Optional[str] = None,
    previous_draft: Optional[str] = None,
    user_feedback: Optional[str] = None,
) -> tuple[str, str, int]:
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
        Tupla (draft_text, title, version)
    """
    # Usa la variabile d'ambiente se api_key non è fornita
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError("GOOGLE_API_KEY non configurata. Imposta la variabile d'ambiente o passa api_key.")
    
    # Carica il contesto dell'agente
    agent_context = load_draft_agent_context()
    
    # Formatta i dati
    formatted_form_data = format_form_data_for_draft(form_data)
    formatted_answers = format_question_answers(question_answers)
    
    # Mappa il modello
    gemini_model = map_model_name(form_data.llm_model)
    
    # Crea il prompt
    if previous_draft and user_feedback:
        # Modifica della bozza esistente
        system_prompt = SystemMessage(content=agent_context)
        user_prompt_content = f"""Hai già generato una bozza estesa per questo romanzo. L'utente ha richiesto delle modifiche.

**Dati originali del romanzo:**
{formatted_form_data}

{formatted_answers}

**Bozza precedente (versione da modificare):**
{previous_draft}

**Feedback dell'utente per le modifiche:**
{user_feedback}

Genera una nuova versione della bozza estesa che incorpori le modifiche richieste dall'utente, mantenendo tutti gli elementi che non sono stati richiesti di modificare. La nuova bozza deve essere coerente e completa."""
    else:
        # Generazione iniziale
        system_prompt = SystemMessage(content=agent_context)
        user_prompt_content = f"""Genera una bozza estesa e dettagliata dello svolgimento della trama per il seguente romanzo.

**Dati del romanzo:**
{formatted_form_data}

{formatted_answers}

Genera una bozza estesa che sviluppi in dettaglio la trama, incorporando tutte le specifiche indicate e le informazioni emerse dalle risposte. La bozza deve essere strutturata come indicato nel contesto e fornire sufficiente dettaglio per guidare la scrittura successiva."""
    
    user_prompt = HumanMessage(content=user_prompt_content)
    
    # Inizializza il modello Gemini
    llm = ChatGoogleGenerativeAI(
        model=gemini_model,
        google_api_key=api_key,
        temperature=form_data.temperature if form_data.temperature is not None else 0.7,
    )
    
    # Genera la bozza
    try:
        response = await llm.ainvoke([system_prompt, user_prompt])
        llm_output = _coerce_llm_content_to_text(response.content).strip()
        
        # Estrai titolo e trama dall'output
        title, draft_text = parse_draft_output(llm_output)
        
        # Recupera la sessione per determinare la versione
        session_store = get_session_store()
        session = session_store.get_session(session_id)
        
        if session:
            new_version = session.current_version + 1
        else:
            new_version = 1
        
        return draft_text, title, new_version
        
    except Exception as e:
        raise Exception(f"Errore nella generazione della bozza: {str(e)}")



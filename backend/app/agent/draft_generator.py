import json
import os
from pathlib import Path
from typing import Optional
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


async def generate_draft(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    session_id: str,
    api_key: Optional[str] = None,
    previous_draft: Optional[str] = None,
    user_feedback: Optional[str] = None,
) -> tuple[str, int]:
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
        Tupla (draft_text, version)
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
        temperature=0.7,
    )
    
    # Genera la bozza
    try:
        response = await llm.ainvoke([system_prompt, user_prompt])
        draft_text = response.content.strip()
        
        # Recupera la sessione per determinare la versione
        session_store = get_session_store()
        session = session_store.get_session(session_id)
        
        if session:
            new_version = session.current_version + 1
        else:
            new_version = 1
        
        return draft_text, new_version
        
    except Exception as e:
        raise Exception(f"Errore nella generazione della bozza: {str(e)}")


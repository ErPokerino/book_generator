import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.models import SubmissionRequest, Question, QuestionsResponse
from app.agent.state import AgentState
from app.core.config import get_temperature_for_agent


def load_agent_context() -> str:
    """Carica il contesto dell'agente dal file Markdown."""
    # In locale: __file__ = backend/app/agent/question_generator.py -> root = .parent.parent.parent.parent
    # Nel container: __file__ = /app/app/agent/question_generator.py -> root = .parent.parent.parent
    base_path = Path(__file__).parent.parent.parent
    config_path = base_path / "config" / "agent_context.md"
    
    # Se non esiste, prova un livello sopra (per ambiente locale)
    if not config_path.exists():
        base_path = base_path.parent
        config_path = base_path / "config" / "agent_context.md"
    
    if not config_path.exists():
        raise FileNotFoundError(f"File di contesto agente non trovato: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return f.read()


def format_form_data(form_data: SubmissionRequest) -> str:
    """Formatta i dati del form in una stringa leggibile per il prompt."""
    lines = [f"**Modello LLM**: {form_data.llm_model}"]
    lines.append(f"**Trama**: {form_data.plot}")
    
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
                # Gemini può restituire parti tipo {"type": "...", "text": "..."}
                txt = item.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    # fallback per dict / altri tipi
    return str(content)


def parse_questions_from_llm_response(response_text: Any) -> list[Question]:
    """Parsa le domande dal response del LLM."""
    questions = []
    response_text = _coerce_llm_content_to_text(response_text)
    
    # Cerca un blocco JSON nel response
    try:
        # Prova a estrarre JSON se è racchiuso in markdown code blocks
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            # Cerca direttamente un oggetto JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_text = response_text[json_start:json_end]
        
        data = json.loads(json_text)
        
        # Estrae le domande
        questions_data = data.get("questions", [])
        for i, q_data in enumerate(questions_data, 1):
            question = Question(
                id=q_data.get("id", f"q{i}"),
                text=q_data.get("text", ""),
                type=q_data.get("type", "text"),
                options=q_data.get("options") if q_data.get("type") == "multiple_choice" else None,
            )
            questions.append(question)
    
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Fallback: genera domande di default se il parsing fallisce
        questions = [
            Question(
                id="q1",
                text="Quale è l'età approssimativa del protagonista principale?",
                type="text"
            ),
            Question(
                id="q2",
                text="Quante pagine dovrebbe avere approssimativamente il romanzo?",
                type="multiple_choice",
                options=["100-200", "200-300", "300-400", "400+"]
            ),
        ]
    
    return questions


async def generate_questions(
    form_data: SubmissionRequest,
    api_key: Optional[str] = None
) -> QuestionsResponse:
    """
    Genera domande usando LangGraph e Gemini.
    
    Args:
        form_data: Dati del form compilato dall'utente
        api_key: API key per Gemini (se None, usa variabile d'ambiente)
    
    Returns:
        QuestionsResponse con le domande generate
    """
    # Usa la variabile d'ambiente se api_key non è fornita
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError("GOOGLE_API_KEY non configurata. Imposta la variabile d'ambiente o passa api_key.")
    
    # Carica il contesto
    context = load_agent_context()
    
    # Formatta i dati del form
    formatted_data = format_form_data(form_data)
    
    # Crea il prompt
    system_prompt = f"{context}\n\nAnalizza le seguenti informazioni fornite dall'utente e genera domande appropriate."
    
    user_prompt = f"""Informazioni fornite dall'utente:

{formatted_data}

Genera domande pertinenti in formato JSON come specificato nel contesto. Rispondi SOLO con il JSON, senza testo aggiuntivo."""

    # Inizializza il modello Gemini
    # Mappa i nomi dei modelli al formato corretto per Gemini API
    # Nomi corretti dalla documentazione ufficiale: https://ai.google.dev/gemini-api/docs/models
    model_name = form_data.llm_model or ""  # Default a stringa vuota se None
    if model_name and "gemini-2.5-flash" in model_name:
        gemini_model = "gemini-2.5-flash"  # Modello stabile
    elif model_name and "gemini-2.5-pro" in model_name:
        gemini_model = "gemini-2.5-pro"  # Modello stabile
    elif model_name and "gemini-3-flash" in model_name:
        gemini_model = "gemini-3-flash-preview"  # Modello in preview
    elif model_name and "gemini-3-pro" in model_name:
        gemini_model = "gemini-3-pro-preview"  # Modello in preview
    else:
        gemini_model = "gemini-2.5-flash"  # default: modello stabile
    
    temperature = get_temperature_for_agent("question_generator", gemini_model)
    llm = ChatGoogleGenerativeAI(
        model=gemini_model,
        google_api_key=api_key,
        temperature=temperature,
    )
    
    # Genera le domande
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    
    response = await llm.ainvoke(messages)
    response_text = _coerce_llm_content_to_text(response.content)
    
    # Parsa le domande
    questions = parse_questions_from_llm_response(response_text)
    
    # Genera session_id
    session_id = str(uuid.uuid4())
    
    return QuestionsResponse(
        success=True,
        session_id=session_id,
        questions=questions,
        message="Domande generate con successo",
    )


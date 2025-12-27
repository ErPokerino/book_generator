import os
from pathlib import Path
from typing import Optional, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.models import SubmissionRequest, QuestionAnswer
from app.agent.session_store import get_session_store


def load_outline_agent_context() -> str:
    """Carica il contesto dell'agente di outline dal file Markdown."""
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "outline_agent_context.md"
    
    if not config_path.exists():
        raise FileNotFoundError(f"File di contesto agente outline non trovato: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return f.read()


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
    
    if question_answers:
        lines.append("\n**Risposte alle domande preliminari:**")
        for qa in question_answers:
            if qa.answer:
                lines.append(f"- {qa.answer}")
    
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


async def generate_outline(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    session_id: str,
    draft_title: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
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
        Outline text in Markdown format
    """
    # Usa la variabile d'ambiente se api_key non è fornita
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError("GOOGLE_API_KEY non configurata. Imposta la variabile d'ambiente o passa api_key.")
    
    # Carica il contesto dell'agente
    agent_context = load_outline_agent_context()
    
    # Formatta i dati
    formatted_input = format_input_for_outline(
        form_data,
        question_answers,
        validated_draft,
        draft_title,
    )
    
    # Mappa il modello
    gemini_model = map_model_name(form_data.llm_model)
    
    # Crea il prompt
    system_prompt = SystemMessage(content=agent_context)
    user_prompt_content = f"""Genera la struttura completa (indice) del romanzo basandoti sulle seguenti informazioni.

{formatted_input}

Genera una struttura dettagliata in formato Markdown che organizzi tutta la narrazione in capitoli e sezioni, con descrizioni di alto livello per ciascun elemento. La struttura deve essere ampia e includere non solo gli eventi principali, ma anche approfondimenti su personaggi, temi, atmosfere e sviluppi narrativi."""
    
    user_prompt = HumanMessage(content=user_prompt_content)
    
    # Inizializza il modello Gemini
    llm = ChatGoogleGenerativeAI(
        model=gemini_model,
        google_api_key=api_key,
        temperature=0.7,
    )
    
    # Genera l'outline
    try:
        response = await llm.ainvoke([system_prompt, user_prompt])
        outline_text = _coerce_llm_content_to_text(response.content).strip()
        
        return outline_text
        
    except Exception as e:
        raise Exception(f"Errore nella generazione della struttura: {str(e)}")


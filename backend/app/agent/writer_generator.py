import os
import re
from pathlib import Path
from typing import Any, Optional, List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.models import SubmissionRequest, QuestionAnswer
from app.agent.session_store import get_session_store


def load_writer_agent_context() -> str:
    """Carica il contesto dell'agente scrittore dal file Markdown."""
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "writer_agent_context.md"
    
    if not config_path.exists():
        raise FileNotFoundError(f"File di contesto agente scrittore non trovato: {config_path}")
    
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
                txt = item.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


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
    print(f"[PARSE OUTLINE] Trovate {len(sections)} sezioni totali (prima del filtro)")
    for i, s in enumerate(sections[:5]):  # Mostra prime 5 per debug
        print(f"[PARSE OUTLINE] Sezione {i+1}: livello {s['level']}, titolo: {s['title'][:50]}...")
    
    # Filtra solo le sezioni di livello 2 o 3 (capitoli, non parti)
    # Se ci sono parti (livello 2), prendiamo i capitoli (livello 3)
    # Altrimenti prendiamo le sezioni di livello 2
    has_parts = any(s['level'] == 2 for s in sections if 'Parte' in s['title'] or 'Part' in s['title'] or 'Part I' in s['title'] or 'Part II' in s['title'])
    
    if has_parts:
        # Prendi solo i capitoli (livello 3)
        filtered_sections = [s for s in sections if s['level'] == 3]
        print(f"[PARSE OUTLINE] Struttura con Parti: filtrate {len(filtered_sections)} sezioni di livello 3")
    else:
        # Prendi le sezioni di livello 2 (capitoli diretti)
        filtered_sections = [s for s in sections if s['level'] == 2]
        print(f"[PARSE OUTLINE] Struttura diretta: filtrate {len(filtered_sections)} sezioni di livello 2")
    
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
    
    print(f"[PARSE OUTLINE] Restituisco {len(filtered_sections)} sezioni da scrivere")
    return filtered_sections


def format_writer_context(
    form_data: SubmissionRequest,
    question_answers: List[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    previous_chapters: List[Dict[str, Any]],
    current_section: Dict[str, str],
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
        "Tema": form_data.theme,
        "Protagonista": form_data.protagonist,
        "Punto di vista": form_data.point_of_view,
        "Voce narrante": form_data.narrative_voice,
        "Ritmo": form_data.pace,
        "Realismo": form_data.realism,
    }
    
    for label, value in optional_fields.items():
        if value:
            lines.append(f"**{label}**: {value}")
    
    lines.append("\n---\n")
    
    # Trama Estesa Validata
    lines.append("## TRAMA ESTESA VALIDATA")
    lines.append("Questa è la fonte di verità per gli eventi principali e lo sviluppo narrativo.")
    lines.append(validated_draft)
    lines.append("\n---\n")
    
    # Struttura Completa (per riferimento)
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
        
        for i, chapter in enumerate(previous_chapters, 1):
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
    lines.append("**Istruzioni**:")
    lines.append("- Scrivi questa sezione seguendo la descrizione fornita.")
    lines.append("- Mantieni coerenza assoluta con i capitoli precedenti.")
    lines.append("- Elabora tutti i temi e sviluppi narrativi indicati nella descrizione.")
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
    elif "gemini-3-pro" in model_name.lower():
        return "gemini-3-pro-preview"
    else:
        return "gemini-2.5-flash"  # default


async def generate_chapter(
    form_data: SubmissionRequest,
    question_answers: List[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    previous_chapters: List[Dict[str, Any]],
    current_section: Dict[str, str],
    api_key: str,
) -> str:
    """
    Genera il testo di un singolo capitolo/sezione usando il contesto completo.
    
    Args:
        form_data: Dati del form iniziale
        question_answers: Risposte alle domande preliminari
        validated_draft: Bozza estesa validata
        draft_title: Titolo del romanzo
        outline_text: Struttura completa del romanzo
        previous_chapters: Lista di capitoli già scritti (per autoregressione)
        current_section: Dizionario con 'title' e 'description' della sezione corrente
        api_key: API key per Gemini
    
    Returns:
        Testo del capitolo generato
    """
    # Carica il contesto dell'agente
    agent_context = load_writer_agent_context()
    
    # Formatta il contesto completo
    formatted_context = format_writer_context(
        form_data=form_data,
        question_answers=question_answers,
        validated_draft=validated_draft,
        draft_title=draft_title,
        outline_text=outline_text,
        previous_chapters=previous_chapters,
        current_section=current_section,
    )
    
    # Mappa il modello
    gemini_model = map_model_name(form_data.llm_model)
    
    # Crea il prompt
    system_prompt = SystemMessage(content=agent_context)
    user_prompt_content = f"""Scrivi la sezione del romanzo indicata di seguito.

{formatted_context}

Scrivi SOLO il testo narrativo della sezione, senza titoli o numerazioni. Inizia direttamente con la narrazione."""
    
    user_prompt = HumanMessage(content=user_prompt_content)
    
    # Inizializza il modello Gemini
    llm = ChatGoogleGenerativeAI(
        model=gemini_model,
        google_api_key=api_key,
        temperature=form_data.temperature if form_data.temperature is not None else 0.0,  # Usa temperatura dall'utente o default
        max_output_tokens=8192,  # Aumenta il limite di output per permettere capitoli più lunghi
    )
    
    # Genera il capitolo
    try:
        response = await llm.ainvoke([system_prompt, user_prompt])
        chapter_text = _coerce_llm_content_to_text(response.content).strip()
        
        return chapter_text
        
    except Exception as e:
        raise Exception(f"Errore nella generazione del capitolo '{current_section['title']}': {str(e)}")


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
    existing_progress = session_store.get_session(session_id)
    if existing_progress and existing_progress.writing_progress:
        existing_total = existing_progress.writing_progress.get('total_steps', 0)
        if existing_total != total_sections:
            print(f"[WRITER] WARNING: total_steps nel progresso ({existing_total}) != sezioni trovate ({total_sections}). Aggiorno.")
            session_store.update_writing_progress(
                session_id=session_id,
                current_step=0,
                total_steps=total_sections,
                current_section_name=sections[0]['title'] if sections else None,
                is_complete=False,
            )
    else:
        # Progresso non inizializzato, lo inizializziamo qui
        print(f"[WRITER] Progresso non trovato, inizializzazione...")
        session_store.update_writing_progress(
            session_id=session_id,
            current_step=0,
            total_steps=total_sections,
            current_section_name=sections[0]['title'] if sections else None,
            is_complete=False,
        )
    
    completed_chapters = []
    
    # Loop autoregressivo: per ogni sezione
    for index, section in enumerate(sections):
        print(f"[WRITER] === Scrittura sezione {index + 1}/{total_sections}: {section['title']} ===")
        
        # Aggiorna il progresso PRIMA di iniziare la generazione
        session_store.update_writing_progress(
            session_id=session_id,
            current_step=index,
            total_steps=total_sections,
            current_section_name=section['title'],
            is_complete=False,
        )
        print(f"[WRITER] Progresso aggiornato: {index}/{total_sections}")
        
        try:
            # Genera il capitolo con contesto autoregressivo
            print(f"[WRITER] Chiamata a generate_chapter per '{section['title']}'...")
            chapter_content = await generate_chapter(
                form_data=form_data,
                question_answers=question_answers,
                validated_draft=validated_draft,
                draft_title=draft_title,
                outline_text=outline_text,
                previous_chapters=completed_chapters,  # Passa i capitoli già scritti
                current_section=section,
                api_key=api_key,
            )
            
            print(f"[WRITER] Capitolo generato: {len(chapter_content)} caratteri")
            
            # Salva il capitolo completato
            chapter_dict = {
                'title': section['title'],
                'content': chapter_content,
                'section_index': index,
            }
            
            session_store.update_book_chapter(
                session_id=session_id,
                chapter_title=section['title'],
                chapter_content=chapter_content,
                section_index=index,
            )
            print(f"[WRITER] Capitolo salvato nella sessione")
            
            completed_chapters.append(chapter_dict)
            print(f"[WRITER] OK - Sezione {index + 1}/{total_sections} completata: {len(chapter_content)} caratteri")
            
        except Exception as e:
            error_msg = f"Errore nella generazione della sezione '{section['title']}': {str(e)}"
            print(f"[WRITER] ERRORE: {error_msg}")
            import traceback
            traceback.print_exc()
            
            # Salva l'errore nel progresso
            session_store.update_writing_progress(
                session_id=session_id,
                current_step=index,
                total_steps=total_sections,
                current_section_name=section['title'],
                is_complete=False,
                error=error_msg,
            )
            # Rilancia l'eccezione per interrompere il processo
            raise
    
    # Marca come completato
    session_store.update_writing_progress(
        session_id=session_id,
        current_step=total_sections,
        total_steps=total_sections,
        current_section_name=None,
        is_complete=True,
    )
    
    print(f"[WRITER] Scrittura completata: {total_sections} sezioni scritte")
    
    return completed_chapters


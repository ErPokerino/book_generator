import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.models import SubmissionRequest, QuestionAnswer
from app.agent.session_store import get_session_store
from app.config import get_app_config, get_temperature_for_agent


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
    elif "gemini-3-pro" in model_name.lower():
        return "gemini-3-pro-preview"
    else:
        return "gemini-2.5-flash"  # default


def get_max_output_tokens(model_name: str) -> int:
    """
    Determina il max_output_tokens in base al modello.
    
    Args:
        model_name: Nome del modello Gemini (dopo mappatura)
    
    Returns:
        Numero massimo di token di output
    """
    app_config = get_app_config()
    tokens_config = app_config.get("llm_models", {}).get("max_output_tokens", {})
    
    # Flash 2.5 ha limite più basso
    if "gemini-2.5-flash" in model_name.lower():
        return tokens_config.get("gemini_2_5_flash", 8192)
    
    # Tutti gli altri modelli (Pro 2.5, Flash 3, Pro 3) usano il default
    return tokens_config.get("default", 65536)


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
    
    # Determina max_output_tokens in base al modello
    max_tokens = get_max_output_tokens(gemini_model)
    print(f"[WRITER] Modello: {gemini_model}, max_output_tokens: {max_tokens}")
    
    # Crea il prompt
    system_prompt = SystemMessage(content=agent_context)
    user_prompt_content = f"""Scrivi la sezione del romanzo indicata di seguito.

{formatted_context}

Scrivi SOLO il testo narrativo della sezione, senza titoli o numerazioni. Inizia direttamente con la narrazione."""
    
    user_prompt = HumanMessage(content=user_prompt_content)
    
    # Inizializza il modello Gemini
    temperature = get_temperature_for_agent("writer_generator", gemini_model)
    llm = ChatGoogleGenerativeAI(
        model=gemini_model,
        google_api_key=api_key,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    
    # Genera il capitolo
    try:
        response = await llm.ainvoke([system_prompt, user_prompt])
        chapter_text = _coerce_llm_content_to_text(response.content).strip()
        
        # Validazione: considera vuoto anche output tipo "..." o solo punteggiatura
        import re
        alnum_count = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]", chapter_text))
        # Se contiene pochissimi caratteri alfanumerici, è di fatto vuoto/degradato
        is_effectively_empty = (alnum_count < 20)

        app_config = get_app_config()
        min_chapter_length = app_config.get("validation", {}).get("min_chapter_length", 50)
        
        if not chapter_text or len(chapter_text.strip()) < min_chapter_length or is_effectively_empty:
            raise ValueError(
                f"Capitolo generato vuoto o troppo corto per '{current_section['title']}': "
                f"{len(chapter_text) if chapter_text else 0} caratteri, {alnum_count} alfanumerici "
                f"(minimo richiesto: {min_chapter_length} caratteri e contenuto significativo)"
            )
        
        print(f"[WRITER] Capitolo '{current_section['title']}' generato con successo: {len(chapter_text)} caratteri")
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
                is_paused=False,
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
            is_paused=False,
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
        session_store.start_chapter_timing(session_id)
        
        for retry in range(max_retries):
            try:
                # Genera il capitolo con contesto autoregressivo
                if retry > 0:
                    print(f"[WRITER] Retry {retry}/{max_retries - 1} per capitolo '{section['title']}'...")
                else:
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
                
                # Verifica che il contenuto sia valido
                app_config = get_app_config()
                min_chapter_length = app_config.get("validation", {}).get("min_chapter_length", 50)
                
                if chapter_content and len(chapter_content.strip()) >= min_chapter_length:
                    print(f"[WRITER] Capitolo generato con successo: {len(chapter_content)} caratteri")
                    # Termina tracciamento tempo capitolo
                    session_store.end_chapter_timing(session_id)
                    session = session_store.get_session(session_id)
                    if session and session.chapter_timings:
                        print(f"[WRITER] Tempo capitolo salvato: {session.chapter_timings[-1]:.1f} secondi. Totale timings: {len(session.chapter_timings)}")
                    break
                else:
                    # Contenuto ancora vuoto o troppo corto
                    if retry < max_retries - 1:
                        print(f"[WRITER] WARNING: Capitolo vuoto o troppo corto ({len(chapter_content) if chapter_content else 0} caratteri), retry...")
                        continue
                    else:
                        # Ultimo tentativo fallito, usa placeholder
                        print(f"[WRITER] ERRORE: Impossibile generare contenuto valido dopo {max_retries} tentativi")
                        # Termina tracciamento tempo anche in caso di errore
                        session_store.end_chapter_timing(session_id)
                        chapter_content = (
                            f"[ERRORE: Impossibile generare contenuto per la sezione '{section['title']}'. "
                            f"Questo potrebbe essere dovuto a limitazioni temporanee del modello. "
                            f"Si prega di rigenerare il libro o contattare il supporto.]"
                        )
                        break
                        
            except ValueError as ve:
                # Errore di validazione (capitolo vuoto)
                if retry < max_retries - 1:
                    print(f"[WRITER] WARNING: {str(ve)}, retry {retry + 1}/{max_retries - 1}...")
                    continue
                else:
                    # Ultimo tentativo fallito
                    print(f"[WRITER] ERRORE: {str(ve)} dopo {max_retries} tentativi")
                    # Termina tracciamento tempo anche in caso di errore
                    session_store.end_chapter_timing(session_id)
                    chapter_content = (
                        f"[ERRORE: Impossibile generare contenuto per la sezione '{section['title']}'. "
                        f"Questo potrebbe essere dovuto a limitazioni temporanee del modello. "
                        f"Si prega di rigenerare il libro o contattare il supporto.]"
                    )
                    break
                    
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
                    session_store.end_chapter_timing(session_id)
                    import traceback
                    traceback.print_exc()
                    
                    # Metti in pausa la generazione invece di rilanciare l'eccezione
                    session_store.pause_writing(
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
            
            session_store.update_book_chapter(
                session_id=session_id,
                chapter_title=section['title'],
                chapter_content=chapter_content,
                section_index=index,
            )
            print(f"[WRITER] Capitolo salvato nella sessione")
            
            completed_chapters.append(chapter_dict)
            print(f"[WRITER] OK - Sezione {index + 1}/{total_sections} completata: {len(chapter_content)} caratteri")
    
    # Marca come completato
    session_store.update_writing_progress(
        session_id=session_id,
        current_step=total_sections,
        total_steps=total_sections,
        current_section_name=None,
        is_complete=True,
        is_paused=False,
    )
    
    print(f"[WRITER] Scrittura completata: {total_sections} sezioni scritte")
    
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
    session = session_store.get_session(session_id)
    
    if not session:
        raise ValueError(f"Sessione {session_id} non trovata")
    
    if not session.writing_progress:
        raise ValueError(f"Sessione {session_id} non ha uno stato di scrittura")
    
    progress = session.writing_progress
    if not progress.get("is_paused", False):
        raise ValueError(f"Sessione {session_id} non è in stato di pausa")
    
    # Riprendi lo stato di pausa
    session_store.resume_writing(session_id)
    
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
        session_store.update_writing_progress(
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
        session_store.start_chapter_timing(session_id)
        
        for retry in range(max_retries):
            try:
                # Genera il capitolo con contesto autoregressivo
                if retry > 0:
                    print(f"[WRITER] Retry {retry}/{max_retries - 1} per capitolo '{section['title']}'...")
                else:
                    print(f"[WRITER] Chiamata a generate_chapter per '{section['title']}'...")
                
                chapter_content = await generate_chapter(
                    form_data=form_data,
                    question_answers=question_answers,
                    validated_draft=validated_draft,
                    draft_title=draft_title,
                    outline_text=outline_text,
                    previous_chapters=completed_chapters,
                    current_section=section,
                    api_key=api_key,
                )
                
                # Verifica che il contenuto sia valido
                min_chapter_length = app_config.get("validation", {}).get("min_chapter_length", 50)
                
                if chapter_content and len(chapter_content.strip()) >= min_chapter_length:
                    print(f"[WRITER] Capitolo generato con successo: {len(chapter_content)} caratteri")
                    session_store.end_chapter_timing(session_id)
                    session = session_store.get_session(session_id)
                    if session and session.chapter_timings:
                        print(f"[WRITER] Tempo capitolo salvato: {session.chapter_timings[-1]:.1f} secondi. Totale timings: {len(session.chapter_timings)}")
                    break
                else:
                    if retry < max_retries - 1:
                        print(f"[WRITER] WARNING: Capitolo vuoto o troppo corto ({len(chapter_content) if chapter_content else 0} caratteri), retry...")
                        continue
                    else:
                        print(f"[WRITER] ERRORE: Impossibile generare contenuto valido dopo {max_retries} tentativi")
                        session_store.end_chapter_timing(session_id)
                        chapter_content = (
                            f"[ERRORE: Impossibile generare contenuto per la sezione '{section['title']}'. "
                            f"Questo potrebbe essere dovuto a limitazioni temporanee del modello. "
                            f"Si prega di rigenerare il libro o contattare il supporto.]"
                        )
                        break
                        
            except ValueError as ve:
                if retry < max_retries - 1:
                    print(f"[WRITER] WARNING: {str(ve)}, retry {retry + 1}/{max_retries - 1}...")
                    continue
                else:
                    print(f"[WRITER] ERRORE: {str(ve)} dopo {max_retries} tentativi")
                    session_store.end_chapter_timing(session_id)
                    chapter_content = (
                        f"[ERRORE: Impossibile generare contenuto per la sezione '{section['title']}'. "
                        f"Questo potrebbe essere dovuto a limitazioni temporanee del modello. "
                        f"Si prega di rigenerare il libro o contattare il supporto.]"
                    )
                    break
                    
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"[WRITER] WARNING: Errore nella generazione: {str(e)}, retry {retry + 1}/{max_retries - 1}...")
                    continue
                else:
                    # Ultimo tentativo fallito: metti in pausa invece di rilanciare
                    error_msg = f"Errore nella generazione della sezione '{section['title']}': {str(e)}"
                    print(f"[WRITER] ERRORE: {error_msg} - Mettendo in pausa la generazione")
                    session_store.end_chapter_timing(session_id)
                    import traceback
                    traceback.print_exc()
                    
                    # Metti in pausa la generazione invece di rilanciare l'eccezione
                    session_store.pause_writing(
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
            session_store.update_book_chapter(
                session_id=session_id,
                chapter_title=section['title'],
                chapter_content=chapter_content,
                section_index=index,
            )
            completed_chapters.append(chapter_dict)
            print(f"[WRITER] OK - Sezione {index + 1}/{total_sections} completata: {len(chapter_content)} caratteri")
    
    # Marca come completato
    session_store.update_writing_progress(
        session_id=session_id,
        current_step=total_sections,
        total_steps=total_sections,
        current_section_name=None,
        is_complete=True,
        is_paused=False,
    )
    
    print(f"[WRITER] Scrittura completata: {total_sections} sezioni scritte")
    
    return completed_chapters


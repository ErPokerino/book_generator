"""Costruzione del contesto autoregressivo per la scrittura capitoli."""

from __future__ import annotations

from typing import Any, Optional

from app.agent.story_bible import (
    get_nearby_chapter_cards,
    get_recent_full_chapters,
    get_relevant_continuity_notes,
)
from app.agent.writer.common import format_question_answers_for_writer
from app.models import QuestionAnswer, SubmissionRequest


def format_writer_context(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    previous_chapters: list[dict[str, Any]],
    current_section: dict[str, str],
    story_bible: Optional[dict[str, Any]] = None,
    is_long_form_part1: bool = False,
    is_long_form_part2: bool = False,
    part1_text: Optional[str] = None,
) -> str:
    """
    Formatta tutto il contesto per la scrittura di un capitolo.
    Include configurazione, trama, struttura, capitoli precedenti e sezione corrente.
    """
    lines: list[str] = []

    if draft_title:
        lines.append(f"# TITOLO DEL ROMANZO: {draft_title}\n")

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

    formatted_answers = format_question_answers_for_writer(question_answers)
    if formatted_answers:
        lines.append("## RISPOSTE ALLE DOMANDE PRELIMINARI")
        lines.append("Questi chiarimenti esprimono preferenze e vincoli specifici dell'utente.")
        lines.append(formatted_answers)
        lines.append("\n---\n")

    if story_bible:
        lines.append("## STORY BIBLE DEL ROMANZO")
        lines.append(
            "Usa questa memoria strutturata come guida primaria per mantenere continuità, vincoli e direzione narrativa."
        )

        creative_brief = story_bible.get("creative_brief", [])
        if creative_brief:
            lines.append("### Brief creativo")
            for item in creative_brief:
                lines.append(f"- {item}")

        character_profiles = story_bible.get("character_profiles")
        if character_profiles:
            lines.append("\n### Profili Personaggi")
            lines.append("Usa questi profili per mantenere voce, tratti e arco coerenti per ogni personaggio.")
            lines.append(character_profiles)

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
        lines.append("## TRAMA ESTESA VALIDATA")
        lines.append("Questa è la fonte di verità per gli eventi principali e lo sviluppo narrativo.")
        lines.append(validated_draft)
        lines.append("\n---\n")

        lines.append("## STRUTTURA COMPLETA DEL ROMANZO")
        lines.append("Questa è la struttura completa. La sezione che devi scrivere è indicata di seguito.")
        lines.append(outline_text)
        lines.append("\n---\n")

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
            lines.append(
                "Per evitare ridondanza, hai il testo integrale solo degli ultimi capitoli; "
                "per il resto usa la continuità sintetica della story bible.\n"
            )

        for index, chapter in enumerate(chapters_for_prompt, start=1):
            title = chapter.get("title", f"Capitolo {index}")
            content = chapter.get("content", "")
            lines.append(f"### {title}")
            lines.append(content)
            lines.append("\n")

        lines.append("---\n")

    lines.append("## SEZIONE DA SCRIVERE ORA")
    lines.append(f"**Titolo**: {current_section['title']}")
    lines.append("**Descrizione**:")
    lines.append(current_section["description"])
    lines.append("\n")

    if is_long_form_part1:
        lines.append("**Istruzioni (Modalità Estesa - Parte 1 di 2)**:")
        lines.append("- Scrivi SOLO la prima parte (circa 50-60%) di questa sezione.")
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

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


def _format_initial_configuration(form_data: SubmissionRequest) -> list[str]:
    lines = ["## CONFIGURAZIONE INIZIALE"]
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
    return lines


def format_writer_prefix(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    story_bible: Optional[dict[str, Any]] = None,
    **_: Any,
) -> str:
    """Prefisso stabile: identico per tutti i capitoli finché bozza/outline non cambiano."""
    lines: list[str] = []
    if draft_title:
        lines.append(f"# TITOLO DEL ROMANZO: {draft_title}\n")

    if story_bible:
        lines.append("## STORY BIBLE DEL ROMANZO")
        lines.append(
            "Usa questa memoria per continuità, vincoli e direzione. Non contraddire i capitoli già scritti."
        )
        creative_brief = story_bible.get("creative_brief", [])
        if creative_brief:
            lines.append("### Brief creativo")
            for item in creative_brief:
                lines.append(f"- {item}")

        character_profiles = story_bible.get("character_profiles")
        if character_profiles:
            lines.append("\n### Profili Personaggi")
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
        lines.append("\n---\n")
        return "\n".join(lines)

    lines.extend(_format_initial_configuration(form_data))
    lines.append("\n---\n")
    formatted_answers = format_question_answers_for_writer(question_answers)
    if formatted_answers:
        lines.append("## RISPOSTE ALLE DOMANDE PRELIMINARI")
        lines.append("Questi chiarimenti esprimono preferenze e vincoli specifici dell'utente.")
        lines.append(formatted_answers)
        lines.append("\n---\n")
    lines.append("## TRAMA ESTESA VALIDATA")
    lines.append("Questa è la fonte di verità per gli eventi principali e lo sviluppo narrativo.")
    lines.append(validated_draft)
    lines.append("\n---\n")
    lines.append("## STRUTTURA COMPLETA DEL ROMANZO")
    lines.append("Questa è la struttura completa. La sezione che devi scrivere è indicata di seguito.")
    lines.append(outline_text)
    lines.append("\n---\n")
    return "\n".join(lines)


def format_writer_turn(
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
    **_: Any,
) -> str:
    """Parte variabile: card vicine, continuità, ultimo capitolo, sezione corrente."""
    lines: list[str] = []
    if story_bible:
        nearby_cards = get_nearby_chapter_cards(
            story_bible,
            current_section.get("section_index"),
        )
        if nearby_cards:
            lines.append("### Chapter Cards Rilevanti")
            current_index = current_section.get("section_index")
            for card in nearby_cards:
                card_index = int(card.get("section_index", -1))
                if current_index is not None and card_index < int(current_index):
                    relation = "Contesto immediatamente precedente"
                else:
                    relation = "Sviluppo immediatamente successivo"
                lines.append(
                    f"- [{relation}] {card.get('title', '')}: {card.get('description', '')}"
                )

        continuity_notes = get_relevant_continuity_notes(story_bible, previous_chapters)
        if continuity_notes:
            lines.append("\n### Continuità Consolidata")
            for note in continuity_notes:
                lines.append(f"- {note.get('title', '')}: {note.get('summary', '')}")
            lines.append("")

    if previous_chapters:
        lines.append("## CAPITOLI PRECEDENTI SCRITTI")
        lines.append("Mantieni coerenza con eventi, voci, tono, ambientazione e stile già usati.\n")
        chapters_for_prompt = previous_chapters
        if story_bible:
            chapters_for_prompt = get_recent_full_chapters(previous_chapters)
            lines.append(
                "Testo integrale solo degli ultimi capitoli; per il resto usa la continuità sintetica.\n"
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
        lines.append("**Istruzioni (Parte 1 di 2)**:")
        lines.append("- Scrivi solo la prima parte (circa 50-60%) di questa sezione.")
        lines.append("- Non concludere la sezione e non risolvere tutti gli eventi dell'outline.")
        lines.append("- Fermati a un punto intermedio logico.")
        lines.append("- Inizia direttamente con la narrazione.")
    elif is_long_form_part2:
        lines.append("**Istruzioni (Parte 2 di 2)**:")
        lines.append("- Prima parte già scritta:")
        lines.append("\n[INIZIO PARTE 1]")
        lines.append(part1_text or "")
        lines.append("[FINE PARTE 1]\n")
        lines.append("- Continua esattamente da dove si interrompe la Parte 1, stesso stile e ritmo.")
        lines.append("- Non riassumere la Parte 1. Completa gli eventi dell'outline ancora da narrare.")
        lines.append("- Porta la sezione a una chiusura naturale.")
    else:
        lines.append("**Istruzioni**:")
        lines.append("- Scrivi questa sezione seguendo la descrizione.")
        lines.append("- Inizia direttamente con la narrazione, senza titoli o numerazioni.")

    return "\n".join(lines)


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
    """Contesto completo: prefisso stabile + turno del capitolo."""
    prefix = format_writer_prefix(
        form_data=form_data,
        question_answers=question_answers,
        validated_draft=validated_draft,
        draft_title=draft_title,
        outline_text=outline_text,
        story_bible=story_bible,
    )
    turn = format_writer_turn(
        form_data=form_data,
        question_answers=question_answers,
        validated_draft=validated_draft,
        draft_title=draft_title,
        outline_text=outline_text,
        previous_chapters=previous_chapters,
        current_section=current_section,
        story_bible=story_bible,
        is_long_form_part1=is_long_form_part1,
        is_long_form_part2=is_long_form_part2,
        part1_text=part1_text,
    )
    return f"{prefix}\n{turn}"

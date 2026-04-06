"""Parsing e rendering dell'outline markdown del romanzo."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger("writer-outline-ast")


def parse_outline_sections(outline_text: str) -> list[dict[str, Any]]:
    """
    Analizza il testo Markdown della struttura e estrae le sezioni scrivibili.

    Restituisce una lista di dizionari con:
    - `title`
    - `description`
    - `level`
    - `section_index`
    """
    if not outline_text or not outline_text.strip():
        raise ValueError("L'outline è vuoto. Genera prima la struttura del romanzo.")

    sections: list[dict[str, Any]] = []
    lines = outline_text.split("\n")
    current_section: dict[str, Any] | None = None
    current_description: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#"):
            if current_section:
                current_section["description"] = "\n".join(current_description).strip()
                sections.append(current_section)

            level = 0
            while level < len(line) and line[level] == "#":
                level += 1

            title = line[level:].strip()
            if not title:
                continue

            if (
                level == 1
                and len(sections) == 0
                and any(keyword in title.lower() for keyword in ("struttura", "indice", "outline"))
            ):
                current_section = None
                current_description = []
                continue

            current_section = {"title": title, "description": "", "level": level}
            current_description = []
            continue

        if current_section:
            current_description.append(line)

    if current_section:
        current_section["description"] = "\n".join(current_description).strip()
        sections.append(current_section)

    level2_sections = [section for section in sections if section["level"] == 2]
    level3_sections = [section for section in sections if section["level"] == 3]

    structural_keywords = [
        "Parte",
        "Part",
        "Atto",
        "Act",
        "Introduzione",
        "Introduction",
        "Conclusione",
        "Conclusion",
        "Prologo",
        "Prologue",
        "Epilogo",
        "Epilogue",
        "Sezione",
        "Section",
    ]
    structural_containers = [
        section
        for section in sections
        if section["level"] == 2
        and any(keyword.lower() in section["title"].lower() for keyword in structural_keywords)
    ]
    explicit_chapters_level2 = [
        section
        for section in sections
        if section["level"] == 2
        and any(keyword in section["title"].lower() for keyword in ("capitolo", "chapter"))
    ]
    has_level3_sections = bool(level3_sections)

    if (structural_containers and has_level3_sections) or (
        not explicit_chapters_level2 and has_level3_sections
    ):
        filtered_sections = [section for section in sections if section["level"] == 3]
        selection_mode = "level3"
    elif explicit_chapters_level2:
        filtered_sections = [section for section in sections if section["level"] == 2]
        selection_mode = "level2-explicit"
    else:
        filtered_sections = [section for section in sections if section["level"] == 2]
        selection_mode = "level2-fallback"

    if not filtered_sections:
        filtered_sections = [section for section in sections if section["level"] in [2, 3]]
        selection_mode = "level2-or-level3"
    if not filtered_sections:
        filtered_sections = [section for section in sections if section["level"] > 1]
        selection_mode = "level>1"
    if not filtered_sections:
        raise ValueError(
            "Nessuna sezione scrivibile trovata nella struttura. "
            "Verifica che l'outline contenga capitoli con intestazioni Markdown (`##` o `###`)."
        )

    for index, section in enumerate(filtered_sections):
        section["section_index"] = index

    logger.info(
        "Outline parsato",
        context={
            "total_sections": len(sections),
            "level2_sections": len(level2_sections),
            "level3_sections": len(level3_sections),
            "selected_sections": len(filtered_sections),
            "selection_mode": selection_mode,
        },
    )
    return filtered_sections


def regenerate_outline_markdown(sections: list[dict[str, Any]]) -> str:
    """Rigenera il markdown dell'outline da un array di sezioni modificate."""
    if not sections:
        raise ValueError("La lista di sezioni non può essere vuota")

    sorted_sections = sorted(sections, key=lambda section: section.get("section_index", 0))
    lines: list[str] = []

    for section in sorted_sections:
        title = section.get("title", "").strip()
        description = section.get("description", "").strip()
        level = int(section.get("level", 2) or 2)
        if not title:
            continue
        header_prefix = "#" * level
        lines.append(f"{header_prefix} {title}")
        lines.append("")
        if description:
            lines.append(description)
            lines.append("")

    markdown = "\n".join(lines).strip()
    if not markdown:
        raise ValueError("Nessuna sezione valida da convertire in markdown")
    return markdown

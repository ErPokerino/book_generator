"""Loader centralizzati per i prompt del writer package."""

from app.llm import load_prompt_file


def load_writer_agent_context() -> str:
    """Carica il contesto dell'agente scrittore dal file Markdown."""
    return load_prompt_file("writer_agent_context.md", "writer", anchor_file=__file__)


def load_chapter_reviewer_context() -> str:
    """Carica il contesto dell'agente reviewer del capitolo dal file Markdown."""
    return load_prompt_file(
        "chapter_reviewer_context.md",
        "chapter reviewer",
        anchor_file=__file__,
    )

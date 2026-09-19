"""Loader centralizzati per i prompt del writer package."""

from app.llm.prompts import compose_prompt_files


def load_writer_agent_context() -> str:
    """Carica mestiere condiviso e istruzioni operative dello scrittore."""
    return compose_prompt_files(
        "narrative_craft.md",
        "writer_agent_context.md",
        agent_label="writer",
        anchor_file=__file__,
    )

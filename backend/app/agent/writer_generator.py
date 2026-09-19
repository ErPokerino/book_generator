"""Facciata compatibile per il nuovo writer package modulare."""

from app.agent.writer.book_orchestrator import generate_full_book, resume_book_generation
from app.agent.writer.chapter_generator import generate_chapter
from app.agent.writer.common import refresh_story_bible_for_session, validate_generated_chapter_text
from app.agent.writer.context_builder import format_writer_context
from app.agent.writer.outline_ast import parse_outline_sections, regenerate_outline_markdown
from app.agent.writer.prompts import load_writer_agent_context
from app.llm import get_max_output_tokens, map_book_model_name

map_model_name = map_book_model_name

__all__ = [
    "format_writer_context",
    "generate_chapter",
    "generate_full_book",
    "get_max_output_tokens",
    "load_writer_agent_context",
    "map_model_name",
    "parse_outline_sections",
    "refresh_story_bible_for_session",
    "regenerate_outline_markdown",
    "resume_book_generation",
    "validate_generated_chapter_text",
]

"""Primitive condivise per il runtime LLM applicativo."""

from app.llm.contracts import (
    ChapterReviewPayload,
    DraftGenerationPayload,
    OutlineGenerationPayload,
    OutlineSectionPayload,
    QuestionsPayload,
)
from app.llm.model_routing import (
    get_max_output_tokens,
    get_stage_model,
    get_structured_output_method,
    map_book_model_name,
    resolve_generation_mode,
)
from app.llm.prompts import append_contract_instructions, load_prompt_file
from app.llm.runtime import (
    DEFAULT_RETRY_DELAY_SECONDS,
    DEFAULT_STRUCTURED_REPAIR_ATTEMPTS,
    DEFAULT_TIMEOUT_SECONDS,
    build_google_chat_model,
    invoke_chat_model,
    invoke_structured_chat_model,
    is_retryable_llm_error,
)
from app.llm.structured_outputs import (
    build_json_schema_prompt,
    coerce_llm_content_to_text,
    parse_json_model,
)
from app.llm.tracing import LLMTraceRecorder

__all__ = [
    "ChapterReviewPayload",
    "DEFAULT_RETRY_DELAY_SECONDS",
    "DEFAULT_STRUCTURED_REPAIR_ATTEMPTS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DraftGenerationPayload",
    "LLMTraceRecorder",
    "OutlineGenerationPayload",
    "OutlineSectionPayload",
    "QuestionsPayload",
    "append_contract_instructions",
    "build_google_chat_model",
    "build_json_schema_prompt",
    "coerce_llm_content_to_text",
    "get_max_output_tokens",
    "get_stage_model",
    "get_structured_output_method",
    "invoke_chat_model",
    "invoke_structured_chat_model",
    "is_retryable_llm_error",
    "load_prompt_file",
    "map_book_model_name",
    "parse_json_model",
    "resolve_generation_mode",
]

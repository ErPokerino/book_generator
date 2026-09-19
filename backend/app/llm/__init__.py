"""Primitive condivise per il runtime LLM applicativo."""

from app.llm.contracts import (
    DraftGenerationPayload,
    OutlineGenerationPayload,
    OutlineSectionPayload,
    QuestionsPayload,
)
from app.llm.google_backend import (
    build_google_genai_client,
    get_google_backend_config,
    get_google_structured_output_method,
)
from app.llm.model_routing import (
    get_max_output_tokens,
    get_stage_model,
    get_structured_output_method,
    get_writer_split_calls,
    is_known_text_model,
    map_book_model_name,
    public_llm_catalog,
    resolve_generation_mode,
    image_size_for_model,
)
from app.llm.prompts import append_contract_instructions, compose_prompt_files, load_prompt_file
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
    "DEFAULT_RETRY_DELAY_SECONDS",
    "DEFAULT_STRUCTURED_REPAIR_ATTEMPTS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DraftGenerationPayload",
    "LLMTraceRecorder",
    "OutlineGenerationPayload",
    "OutlineSectionPayload",
    "QuestionsPayload",
    "append_contract_instructions",
    "compose_prompt_files",
    "build_google_chat_model",
    "build_google_genai_client",
    "build_json_schema_prompt",
    "coerce_llm_content_to_text",
    "get_google_backend_config",
    "get_google_structured_output_method",
    "get_max_output_tokens",
    "get_stage_model",
    "get_structured_output_method",
    "get_writer_split_calls",
    "image_size_for_model",
    "is_known_text_model",
    "invoke_chat_model",
    "invoke_structured_chat_model",
    "is_retryable_llm_error",
    "load_prompt_file",
    "map_book_model_name",
    "parse_json_model",
    "public_llm_catalog",
    "resolve_generation_mode",
]

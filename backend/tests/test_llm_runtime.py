import json

import pytest
from langchain_core.messages import HumanMessage

from app.agent.draft_generator import parse_draft_output
from app.agent.outline_generator import render_outline_markdown
from app.agent.question_generator import parse_questions_from_llm_response
from app.agent.writer_generator import parse_outline_sections
from app.llm import (
    OutlineGenerationPayload,
    OutlineSectionPayload,
    QuestionsPayload,
    invoke_chat_model,
    invoke_structured_chat_model,
)
from app.llm.model_routing import get_stage_model
from app.llm.tracing import LLMTraceRecorder


class FakeResponse:
    def __init__(self, content: str, *, prompt_tokens: int = 0, completion_tokens: int = 0):
        self.content = content
        self.response_metadata = {
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        }


class FakeLlm:
    def __init__(self, responses):
        self._responses = list(responses)

    async def ainvoke(self, _messages):
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeStructuredLlm:
    def __init__(self, responses):
        self._responses = list(responses)
        self.structured_calls = []

    def with_structured_output(self, schema, method="json_schema", include_raw=False):
        self.structured_calls.append(
            {
                "schema": schema,
                "method": method,
                "include_raw": include_raw,
            }
        )
        return self

    async def ainvoke(self, _messages):
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _require_non_empty_questions(payload: QuestionsPayload) -> QuestionsPayload:
    if not payload.questions:
        raise ValueError("questions must not be empty")
    return payload


def test_parse_questions_from_llm_response_normalizes_missing_ids() -> None:
    questions = parse_questions_from_llm_response(
        """{
          "questions": [
            {"text": "Qual e il tono dominante?", "type": "text"},
            {
              "id": "q_custom",
              "text": "Quanti POV vuoi usare?",
              "type": "multiple_choice",
              "options": ["uno", "due", "tre o piu"]
            }
          ]
        }"""
    )

    assert [question.id for question in questions] == ["q1", "q_custom"]
    assert questions[1].options == ["uno", "due", "tre o piu"]


def test_parse_draft_output_reads_structured_json_contract() -> None:
    title, draft_text, character_profiles = parse_draft_output(
        """{
          "title": "Le mappe del porto",
          "character_profiles": "Ada: cartografa ostinata",
          "draft_text": "Ada scopre un sabotaggio nelle chiuse."
        }"""
    )

    assert title == "Le mappe del porto"
    assert "sabotaggio" in draft_text
    assert "cartografa" in character_profiles


def test_render_outline_markdown_round_trips_with_outline_parser() -> None:
    payload = OutlineGenerationPayload(
        sections=[
            OutlineSectionPayload(
                title="Capitolo 1: Apertura",
                description="- Presentazione del conflitto.",
                level=2,
            ),
            OutlineSectionPayload(
                title="Capitolo 2: Soglia",
                description="- La protagonista accetta il rischio.",
                level=2,
            ),
        ]
    )

    markdown = render_outline_markdown(payload)
    parsed = parse_outline_sections(markdown)

    assert [section["title"] for section in parsed] == [
        "Capitolo 1: Apertura",
        "Capitolo 2: Soglia",
    ]


def test_trace_recorder_persists_jsonl_events(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    recorder = LLMTraceRecorder(stage="draft", session_id="session-1", request_id="unit")
    recorder.record("started", payload={"foo": "bar"})

    assert recorder.file_path.exists()
    events = [json.loads(line) for line in recorder.file_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["event_type"] == "started"
    assert events[0]["session_id"] == "session-1"
    assert events[0]["schema_version"] == 2
    assert events[0]["export_target"] == "jsonl"


@pytest.mark.asyncio
async def test_invoke_chat_model_records_success_trace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_TRACE_RECORD_MESSAGE_PREVIEWS", "0")
    monkeypatch.setenv("LLM_TRACE_RECORD_RESPONSE_PREVIEWS", "0")
    llm = FakeLlm([FakeResponse("risposta finale", prompt_tokens=13, completion_tokens=21)])

    response_text, token_usage = await invoke_chat_model(
        llm=llm,
        messages=[HumanMessage(content="ciao")],
        model_name="fake-model",
        stage="runtime-test",
        request_label="success-path",
        max_retries=1,
    )

    assert response_text == "risposta finale"
    assert token_usage == {"input_tokens": 13, "output_tokens": 21, "model": "fake-model"}

    trace_files = list(tmp_path.glob("*.jsonl"))
    assert len(trace_files) == 1
    events = [json.loads(line) for line in trace_files[0].read_text(encoding="utf-8").splitlines()]
    assert [event["event_type"] for event in events] == [
        "invocation_started",
        "invocation_succeeded",
    ]
    assert "preview" not in events[0]["payload"]["messages"][0]
    assert events[1]["payload"]["response_preview"] is None


@pytest.mark.asyncio
async def test_invoke_chat_model_records_failure_trace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    llm = FakeLlm([RuntimeError("boom")])

    with pytest.raises(RuntimeError, match="boom"):
        await invoke_chat_model(
            llm=llm,
            messages=[HumanMessage(content="ciao")],
            model_name="fake-model",
            stage="runtime-test",
            request_label="failure-path",
            max_retries=1,
        )

    trace_files = list(tmp_path.glob("*.jsonl"))
    assert len(trace_files) == 1
    events = [json.loads(line) for line in trace_files[0].read_text(encoding="utf-8").splitlines()]
    assert [event["event_type"] for event in events] == [
        "invocation_started",
        "invocation_failed",
    ]


@pytest.mark.asyncio
async def test_invoke_structured_chat_model_returns_parsed_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_TRACE_RECORD_MESSAGE_PREVIEWS", "0")
    monkeypatch.setenv("LLM_TRACE_RECORD_RESPONSE_PREVIEWS", "0")
    llm = FakeStructuredLlm(
        [
            {
                "raw": FakeResponse(
                    '{"questions":[{"id":"q1","text":"Qual e il conflitto?","type":"text"}]}',
                    prompt_tokens=9,
                    completion_tokens=4,
                ),
                "parsed": QuestionsPayload.model_validate(
                    {
                        "questions": [
                            {"id": "q1", "text": "Qual e il conflitto?", "type": "text"}
                        ]
                    }
                ),
                "parsing_error": None,
            }
        ]
    )

    payload, token_usage, raw_text = await invoke_structured_chat_model(
        llm=llm,
        schema=QuestionsPayload,
        messages=[HumanMessage(content="genera una domanda")],
        model_name="fake-structured-model",
        stage="questions",
        request_label="structured-success",
        max_retries=1,
        repair_attempts=0,
    )

    assert raw_text.startswith('{"questions"')
    assert payload.questions[0].text == "Qual e il conflitto?"
    assert token_usage == {
        "input_tokens": 9,
        "output_tokens": 4,
        "model": "fake-structured-model",
    }
    assert llm.structured_calls[0]["method"] == "json_schema"

    trace_files = list(tmp_path.glob("*.jsonl"))
    events = [json.loads(line) for line in trace_files[0].read_text(encoding="utf-8").splitlines()]
    assert [event["event_type"] for event in events] == [
        "structured_invocation_started",
        "structured_invocation_succeeded",
    ]


@pytest.mark.asyncio
async def test_invoke_structured_chat_model_repairs_parse_failures(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_TRACE_RECORD_MESSAGE_PREVIEWS", "0")
    monkeypatch.setenv("LLM_TRACE_RECORD_RESPONSE_PREVIEWS", "0")
    llm = FakeStructuredLlm(
        [
            {
                "raw": FakeResponse(
                    '{"questions":[{"text":"Che tono desideri?","type":"essay"}]}',
                    prompt_tokens=10,
                    completion_tokens=5,
                ),
                "parsed": None,
                "parsing_error": ValueError("type must be text or multiple_choice"),
            },
            {
                "raw": FakeResponse(
                    '{"questions":[{"id":"q1","text":"Che tono desideri?","type":"text"}]}',
                    prompt_tokens=2,
                    completion_tokens=3,
                ),
                "parsed": QuestionsPayload.model_validate(
                    {
                        "questions": [
                            {"id": "q1", "text": "Che tono desideri?", "type": "text"}
                        ]
                    }
                ),
                "parsing_error": None,
            },
        ]
    )

    payload, token_usage, _raw_text = await invoke_structured_chat_model(
        llm=llm,
        schema=QuestionsPayload,
        messages=[HumanMessage(content="genera una domanda")],
        model_name="fake-structured-model",
        stage="questions",
        request_label="structured-repair",
        max_retries=1,
        repair_attempts=1,
    )

    assert payload.questions[0].type == "text"
    assert token_usage == {
        "input_tokens": 12,
        "output_tokens": 8,
        "model": "fake-structured-model",
    }

    trace_files = list(tmp_path.glob("*.jsonl"))
    events = [json.loads(line) for line in trace_files[0].read_text(encoding="utf-8").splitlines()]
    assert [event["event_type"] for event in events] == [
        "structured_invocation_started",
        "structured_invocation_parse_failed",
        "structured_repair_attempt_succeeded",
        "structured_repair_completed",
    ]


@pytest.mark.asyncio
async def test_invoke_structured_chat_model_revalidates_repaired_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    llm = FakeStructuredLlm(
        [
            {
                "raw": FakeResponse(
                    '{"questions":[{"text":"Che tono desideri?","type":"essay"}]}',
                    prompt_tokens=7,
                    completion_tokens=3,
                ),
                "parsed": None,
                "parsing_error": ValueError("invalid enum"),
            },
            {
                "raw": FakeResponse('{"questions":[]}', prompt_tokens=2, completion_tokens=1),
                "parsed": QuestionsPayload.model_validate({"questions": []}),
                "parsing_error": None,
            },
        ]
    )

    with pytest.raises(ValueError, match="questions must not be empty"):
        await invoke_structured_chat_model(
            llm=llm,
            schema=QuestionsPayload,
            messages=[HumanMessage(content="genera una domanda")],
            model_name="fake-structured-model",
            stage="questions",
            request_label="structured-repair-semantic-validation",
            max_retries=1,
            repair_attempts=1,
            parsed_validator=_require_non_empty_questions,
        )


@pytest.mark.asyncio
async def test_invoke_structured_chat_model_accumulates_token_usage_across_retries(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    llm = FakeStructuredLlm(
        [
            {
                "raw": FakeResponse(
                    '{"questions":[{"text":"Che tono desideri?","type":"essay"}]}',
                    prompt_tokens=10,
                    completion_tokens=5,
                ),
                "parsed": None,
                "parsing_error": ValueError("invalid enum"),
            },
            {
                "raw": FakeResponse(
                    '{"questions":[{"id":"q1","text":"Che tono desideri?","type":"text"}]}',
                    prompt_tokens=4,
                    completion_tokens=6,
                ),
                "parsed": QuestionsPayload.model_validate(
                    {
                        "questions": [
                            {"id": "q1", "text": "Che tono desideri?", "type": "text"}
                        ]
                    }
                ),
                "parsing_error": None,
            },
        ]
    )

    payload, token_usage, _raw_text = await invoke_structured_chat_model(
        llm=llm,
        schema=QuestionsPayload,
        messages=[HumanMessage(content="genera una domanda")],
        model_name="fake-structured-model",
        stage="questions",
        request_label="structured-retry-usage",
        max_retries=2,
        repair_attempts=0,
    )

    assert payload.questions[0].id == "q1"
    assert token_usage == {
        "input_tokens": 14,
        "output_tokens": 11,
        "model": "fake-structured-model",
    }


def test_trace_recorder_ignores_invalid_numeric_env_values(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_TRACE_SCHEMA_VERSION", "not-an-int")
    monkeypatch.setenv("LLM_TRACE_PREVIEW_CHAR_LIMIT", "not-an-int")

    recorder = LLMTraceRecorder(stage="draft", session_id="session-1", request_id="env-fallbacks")
    recorder.record("started")

    events = [json.loads(line) for line in recorder.file_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["schema_version"] == 2


def test_get_stage_model_reads_overrides_from_config(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.llm.model_routing.get_app_config",
        lambda: {
            "llm_models": {
                "stage_model_overrides": {"questions": "gemini-custom-json"},
            }
        },
    )

    assert get_stage_model("questions", "gemini-2.5-flash") == "gemini-custom-json"
    assert get_stage_model("book", "gemini-3-flash") == "gemini-3-flash-preview"

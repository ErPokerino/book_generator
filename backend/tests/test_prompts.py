from app.agent.draft_generator import load_draft_agent_context
from app.agent.outline_generator import load_outline_agent_context
from app.agent.question_generator import load_agent_context
from app.agent.writer.prompts import load_writer_agent_context


def test_draft_prompt_drops_legacy_markdown_contract() -> None:
    prompt = load_draft_agent_context()

    assert "TITOLO: [Titolo del libro]" not in prompt
    assert "APPROCCIO CHIRURGICO" not in prompt
    assert "250+ pagine" not in prompt


def test_writer_prompt_is_operational_not_an_inventory() -> None:
    prompt = load_writer_agent_context()

    assert "Esempio di Struttura del Contesto Ricevuto" not in prompt
    assert "Riceverai:" not in prompt
    assert "Scrivi SOLO il testo" in prompt or "solo il testo narrativo" in prompt.lower()


def test_outline_prompt_does_not_hardcode_novel_length() -> None:
    prompt = load_outline_agent_context()

    assert "250+ pagine" not in prompt
    assert "non condensare" in prompt.lower() or "Non condensare" in prompt


def test_question_prompt_does_not_embed_json_examples() -> None:
    prompt = load_agent_context()

    assert "```json" not in prompt
    assert "100-200 / 200-300" not in prompt

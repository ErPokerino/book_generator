import pytest

from app.agent.session_store import SessionData
from app.agent.literary_critic import parse_critique_response
from app.agent.story_bible import build_story_bible
from app.agent.writer_generator import (
    format_writer_context,
    parse_chapter_review_response,
    parse_outline_sections,
    should_run_chapter_review,
    validate_generated_chapter_text,
)
from app.models import QuestionAnswer, SubmissionRequest


@pytest.fixture
def rich_submission_request(submission_request: SubmissionRequest) -> SubmissionRequest:
    return submission_request.model_copy(
        update={
            "genre": "fantasy",
            "subgenre": "epico",
            "style": "lirico",
            "theme": "identità",
            "target_audience": "adulti",
            "protagonist": "singolo",
            "protagonist_archetype": "prescelto riluttante",
            "character_arc": "crescita",
            "point_of_view": "terza limitata",
            "narrative_voice": "soggettiva",
            "pace": "medio",
            "temporal_structure": "frammentata",
            "realism": "fantastico",
            "ambiguity": "aperto",
            "intentionality": "letterario",
            "user_name": "Ada",
        }
    )


def test_format_writer_context_includes_question_answers_and_story_controls(
    rich_submission_request: SubmissionRequest,
) -> None:
    context = format_writer_context(
        form_data=rich_submission_request,
        question_answers=[
            QuestionAnswer(question_id="eta_protagonista", answer="La protagonista ha diciassette anni."),
            QuestionAnswer(question_id="tono", answer="Tono malinconico ma non disperato."),
        ],
        validated_draft="Una bozza molto estesa e dettagliata della storia.",
        draft_title="La Citta delle Maree",
        outline_text="## Capitolo 1\n- Apertura della storia",
        previous_chapters=[],
        current_section={"title": "Capitolo 1", "description": "Inizio del viaggio."},
    )

    assert "## RISPOSTE ALLE DOMANDE PRELIMINARI" in context
    assert "- eta_protagonista: La protagonista ha diciassette anni." in context
    assert "- tono: Tono malinconico ma non disperato." in context
    assert "**Arco del personaggio**: crescita" in context
    assert "**Struttura temporale**: frammentata" in context
    assert "**Ambiguità**: aperto" in context
    assert "**Intenzionalità**: letterario" in context


def test_parse_outline_sections_prefers_level3_chapters_under_structural_parts() -> None:
    outline_text = """
# Struttura del Romanzo: Esempio

## Parte I: L'inizio

### Capitolo 1: La promessa
- La protagonista lascia il villaggio.

### Capitolo 2: La soglia
- Primo ostacolo reale.
""".strip()

    sections = parse_outline_sections(outline_text)

    assert [section["title"] for section in sections] == [
        "Capitolo 1: La promessa",
        "Capitolo 2: La soglia",
    ]
    assert [section["section_index"] for section in sections] == [0, 1]


def test_story_bible_tracks_versions_cards_and_continuity(
    rich_submission_request: SubmissionRequest,
) -> None:
    outline_sections = parse_outline_sections(
        """
## Capitolo 1: La promessa
- Apertura nel villaggio.

## Capitolo 2: Il ponte
- La protagonista lascia casa e attraversa il confine.
""".strip()
    )

    story_bible = build_story_bible(
        form_data=rich_submission_request,
        question_answers=[QuestionAnswer(question_id="tono", answer="Visionario ma leggibile.")],
        validated_draft="La bozza racconta la caduta di una città anfibia e il viaggio di Ada verso la capitale sommersa.",
        draft_title="La Citta delle Maree",
        outline_sections=outline_sections,
        completed_chapters=[
            {
                "title": "Capitolo 1: La promessa",
                "content": "Ada osserva le maree artificiali del villaggio. Capisce che l'equilibrio del luogo si sta spezzando. "
                "Promette alla sorella di partire per trovare l'origine del disastro.",
                "section_index": 0,
            }
        ],
        draft_version=2,
        outline_version=3,
    )

    assert story_bible["source_versions"] == {"draft_version": 2, "outline_version": 3}
    assert len(story_bible["chapter_cards"]) == 2
    assert story_bible["chapter_cards"][0]["title"] == "Capitolo 1: La promessa"
    assert story_bible["user_constraints"] == ["tono: Visionario ma leggibile."]
    assert story_bible["continuity_notes"][0]["title"] == "Capitolo 1: La promessa"


def test_format_writer_context_uses_story_bible_and_recent_chapters_only(
    rich_submission_request: SubmissionRequest,
) -> None:
    outline_sections = parse_outline_sections(
        """
## Capitolo 1: La promessa
- Ada scopre il problema del villaggio.

## Capitolo 2: Il ponte
- Ada attraversa il confine e incontra una guida ambigua.

## Capitolo 3: La capitale sommersa
- Ada entra nella città e capisce che il disastro è stato pianificato.

## Capitolo 4: Il cuore della marea
- Ada affronta la mente dietro al complotto.
""".strip()
    )

    previous_chapters = [
        {
            "title": "Capitolo 1: La promessa",
            "content": "TESTO INTEGRALE CAPITOLO UNO. Ada vive nel villaggio e comprende che le maree stanno cambiando.",
            "section_index": 0,
        },
        {
            "title": "Capitolo 2: Il ponte",
            "content": "TESTO INTEGRALE CAPITOLO DUE. Ada attraversa il ponte e incontra la guida ambigua.",
            "section_index": 1,
        },
        {
            "title": "Capitolo 3: La capitale sommersa",
            "content": "TESTO INTEGRALE CAPITOLO TRE. Ada entra nella capitale e scopre la cospirazione.",
            "section_index": 2,
        },
    ]

    story_bible = build_story_bible(
        form_data=rich_submission_request,
        question_answers=[QuestionAnswer(question_id="tono", answer="Malinconico ma epico.")],
        validated_draft="La bozza sviluppa la crisi del villaggio e il viaggio verso la capitale sommersa.",
        draft_title="La Citta delle Maree",
        outline_sections=outline_sections,
        completed_chapters=previous_chapters,
        draft_version=1,
        outline_version=1,
    )

    context = format_writer_context(
        form_data=rich_submission_request,
        question_answers=[QuestionAnswer(question_id="tono", answer="Malinconico ma epico.")],
        validated_draft="Bozza lunga",
        draft_title="La Citta delle Maree",
        outline_text="placeholder",
        previous_chapters=previous_chapters,
        current_section=outline_sections[3],
        story_bible=story_bible,
    )

    assert "## STORY BIBLE DEL ROMANZO" in context
    assert "### Chapter Cards Rilevanti" in context
    assert "### Capitolo 1: La promessa\nTESTO INTEGRALE CAPITOLO UNO" not in context
    assert "TESTO INTEGRALE CAPITOLO DUE" in context
    assert "TESTO INTEGRALE CAPITOLO TRE" in context
    assert "Capitolo 1: La promessa:" in context


def test_session_data_serializes_story_bible(submission_request: SubmissionRequest) -> None:
    session = SessionData("session-story-bible", submission_request, [])
    session.story_bible = {"title": "Romanzo", "creative_brief": ["Genere: fantasy"]}

    restored = SessionData.from_dict(session.to_dict())

    assert restored.story_bible == session.story_bible


def test_should_run_chapter_review_only_for_enabled_modes_and_lengths(
    submission_request: SubmissionRequest,
) -> None:
    review_config = {
        "review": {
            "chapters": {
                "enabled": True,
                "target_modes": ["pro", "ultra"],
                "min_chapter_words": 10,
            }
        }
    }
    long_text = " ".join(["parola"] * 20)

    flash_request = submission_request.model_copy(update={"llm_model": "gemini-2.5-flash"})
    pro_request = submission_request.model_copy(update={"llm_model": "gemini-3-pro"})

    assert should_run_chapter_review(flash_request, long_text, review_config) is False
    assert should_run_chapter_review(pro_request, long_text, review_config) is True
    assert should_run_chapter_review(pro_request, "troppo breve", review_config) is False


def test_parse_chapter_review_response_reads_json_payload() -> None:
    response_text = """```json
{
  "needs_revision": true,
  "issues": [
    "La transizione tra l'arrivo in citta e il confronto finale e troppo brusca.",
    "Il capitolo dimentica il vincolo sul tono malinconico stabilito all'inizio."
  ],
  "preserve": [
    "La voce della protagonista rimane molto credibile."
  ]
}
```"""

    parsed = parse_chapter_review_response(response_text, max_issues=5)

    assert parsed["needs_revision"] is True
    assert len(parsed["issues"]) == 2
    assert parsed["preserve"] == ["La voce della protagonista rimane molto credibile."]


def test_validate_generated_chapter_text_rejects_placeholder_and_short_outputs() -> None:
    strict_config = {
        "validation": {
            "min_chapter_length": 40,
            "min_chapter_words": 8,
            "disallowed_output_markers": ["[ERRORE:"],
        }
    }

    with pytest.raises(ValueError, match="marker non narrativo"):
        validate_generated_chapter_text(
            "[ERRORE: impossibile generare contenuto]",
            "Capitolo 3",
            app_config=strict_config,
        )

    with pytest.raises(ValueError, match="parole"):
        validate_generated_chapter_text(
            "Troppo breve per essere un capitolo vero.",
            "Capitolo 3",
            app_config=strict_config,
        )


def test_parse_critique_response_accepts_json_in_code_fence() -> None:
    response_text = """```json
{
  "score": 7.6,
  "pros": ["Buona tenuta del conflitto", "Personaggi credibili"],
  "cons": ["Finale troppo rapido"],
  "summary": "Romanzo solido, con buona coerenza interna e un finale da sviluppare meglio."
}
```"""

    critique = parse_critique_response(response_text)

    assert critique["score"] == pytest.approx(7.6)
    assert critique["pros"] == ["Buona tenuta del conflitto", "Personaggi credibili"]
    assert critique["cons"] == ["Finale troppo rapido"]
    assert critique["summary"].startswith("Romanzo solido")


def test_parse_critique_response_requires_valid_json_structure() -> None:
    with pytest.raises(ValueError, match="Nessun JSON valido trovato"):
        parse_critique_response(
            "Valutazione: 8/10\nPregi: buona struttura\nDifetti: pochi\nSintesi: testo promettente."
        )

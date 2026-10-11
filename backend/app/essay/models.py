"""Contratti del dominio saggistico: nessun campo narrativo nell'API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix: str) -> str:
    return prefix + uuid4().hex[:12]


class CompactModel(BaseModel):
    """Keep the provider grammar small; enforce bounds with Pydantic locally."""
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def model_json_schema(cls, *args, **kwargs):
        schema = super().model_json_schema(*args, **kwargs)
        def compact(node):
            if isinstance(node, dict):
                return {k: compact(v) for k, v in node.items()
                        if k not in {"minLength", "maxLength", "minItems", "maxItems", "default", "additionalProperties"}}
            if isinstance(node, list):
                return [compact(v) for v in node]
            return node
        return compact(schema)


class EssayBrief(CompactModel):
    topic: str = Field(min_length=3, max_length=8000)
    profile: Literal["argumentative", "popular", "academic"] = "argumentative"
    ai_role: Literal["challenge", "support", "explore"] = "challenge"
    question: str = Field(default="", max_length=4000)
    thesis: str = Field(default="", max_length=8000)
    discipline: str = Field(default="", max_length=400)
    reader_level: Literal["general", "informed", "specialist"] = "general"
    reader_needs: str = Field(default="", max_length=2000)
    target_words: int = Field(default=35000, ge=1000, le=120000)
    concepts: str = Field(default="", max_length=3000)
    premises: str = Field(default="", max_length=5000)
    scope: str = Field(default="", max_length=4000)
    exclusions: str = Field(default="", max_length=3000)
    purpose: str = Field(default="argomentare", max_length=300)
    approach: Literal["analytical", "critical", "comparative", "propositive"] = "analytical"
    voice: Literal["impersonal", "first_singular", "first_plural"] = "impersonal"
    tone: Literal["analytical", "reflective", "dialogic", "assertive", "polemical"] = "analytical"
    language_register: Literal["clear", "essayistic", "technical", "academic"] = "clear"
    structure: Literal["problem", "thesis", "comparative", "thematic", "chronological"] = "thesis"
    density: Literal["concise", "balanced", "deep"] = "balanced"
    example_policy: Literal["documented", "hypothetical", "mixed"] = "mixed"
    methodology: str = Field(default="", max_length=5000)
    corpus: str = Field(default="", max_length=5000)
    source_criteria: str = Field(default="", max_length=3000)
    source_period: str = Field(default="", max_length=300)
    editorial_references: str = Field(default="", max_length=3000)
    author_name: str = Field(default="", max_length=200)
    title: str = Field(default="", max_length=300)
    subtitle: str = Field(default="", max_length=500)
    back_cover_text: str = Field(default="", max_length=1500)
    citation_style: Literal["numeric", "author_date"] = "numeric"
    revision_mode: Literal["writing", "reviewed"] = "reviewed"
    cover_style: Literal["typographic", "conceptual", "photographic", "illustrated"] = "typographic"
    llm_model: str = "gemini-3.8-flash"
    model_overrides: dict[str, str] = Field(default_factory=dict, max_length=8)
    budget_eur: float | None = Field(default=None, gt=0, le=10000)

    @field_validator("topic")
    @classmethod
    def topic_not_blank(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Descrivi il tema con almeno tre caratteri.")
        return value.strip()

    @model_validator(mode="after")
    def validate_models(self):
        from app.essay.settings import settings
        config = settings()
        for key, value in config["profiles"][self.profile]["defaults"].items():
            if key not in self.model_fields_set:
                setattr(self, key, value)
        allowed = {m["id"] for m in config["models"]}
        if self.llm_model not in allowed:
            raise ValueError("Modello testo non disponibile nel catalogo.")
        if any(k not in config["stages"] or v not in allowed for k, v in self.model_overrides.items()):
            raise ValueError("Personalizzazione del modello non valida.")
        return self


class Question(CompactModel):
    id: str
    text: str


class QuestionSet(CompactModel):
    questions: list[Question] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def valid_questions(self):
        ids = [q.id for q in self.questions]
        if len(ids) != len(set(ids)) or any(not q.id.strip() or not q.text.strip() for q in self.questions):
            raise ValueError("Le domande devono avere testo e identificativi distinti.")
        return self


class EvidenceExcerpt(CompactModel):
    id: str
    source_id: str
    quote: str
    locator: str
    start: int
    end: int
    stance: Literal["supports", "contradicts", "mixed", "context"] = "context"
    explanation: str = ""
    reviewed: bool = False


class SourceRecord(CompactModel):
    id: str
    title: str
    author: str = ""
    published: str = ""
    url: str = ""
    filename: str = ""
    kind: Literal["web", "document", "author_notes"] = "document"
    text: str = ""
    content_hash: str = ""
    acquired_at: str = ""
    status: Literal["proposed", "acquired", "analyzed", "failed", "excluded"] = "proposed"
    error: str = ""
    evidence: list[EvidenceExcerpt] = Field(default_factory=list)
    selection_reason: str = ""
    version: int = 1


class ExtractedEvidence(CompactModel):
    quote: str = Field(min_length=8, max_length=1800)
    stance: Literal["supports", "contradicts", "mixed", "context"]
    explanation: str


class EvidenceSet(CompactModel):
    excerpts: list[ExtractedEvidence] = Field(default_factory=list, max_length=5)


class ArgumentClaim(CompactModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: Literal["factual", "interpretive", "normative", "hypothesis", "experience"]
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    objection: str = ""
    response: str = ""
    gap: str = ""


class EssaySectionPlan(CompactModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    description: str = Field(min_length=1)
    claim_ids: list[str] = Field(default_factory=list)
    word_target: int = Field(ge=200, le=8000)


class EssayPlan(CompactModel):
    title: str = Field(min_length=1)
    subtitle: str = ""
    back_cover_text: str = Field(default="", max_length=1500)
    direction: str = Field(min_length=1)
    method: str = ""
    definitions: list[str] = Field(default_factory=list)
    claims: list[ArgumentClaim] = Field(min_length=1, max_length=80)
    sections: list[EssaySectionPlan] = Field(min_length=2, max_length=60)
    limits: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_ids(self):
        for collection in (self.claims, self.sections):
            ids = [x.id for x in collection]
            if len(ids) != len(set(ids)):
                raise ValueError("Identificativi duplicati nel piano.")
        claims = {c.id for c in self.claims}
        if any(c not in claims for s in self.sections for c in s.claim_ids):
            raise ValueError("L'indice richiama un argomento inesistente.")
        return self


class GeneratedEssayPlan(EssayPlan):
    """Editorial bounds apply to AI proposals, never to manual edits."""
    @model_validator(mode="after")
    def concise_titles(self, info):
        brief = (info.context or {}).get("brief")
        if not (brief and brief.title.strip()):
            if len(self.title.split()) > 8 or len(self.title) > 64:
                raise ValueError("Il titolo generato deve avere al massimo 8 parole e 64 caratteri.")
        if any(len(section.title.split()) > 10 or len(section.title) > 85 for section in self.sections):
            raise ValueError("I titoli dei capitoli devono avere al massimo 10 parole e 85 caratteri.")
        if not self.back_cover_text.strip():
            raise ValueError("Scrivi anche la presentazione per la quarta di copertina.")
        return self


class PublicationEdit(CompactModel):
    author_name: str = Field(default="", max_length=200)
    title: str = Field(default="", max_length=300)
    subtitle: str = Field(default="", max_length=500)
    back_cover_text: str = Field(default="", max_length=1500)
    expected_version: int


class ReviewIssue(CompactModel):
    section_id: str = ""
    quote: str = ""
    category: Literal["logic", "evidence", "objection", "method", "style"]
    severity: Literal["blocking", "important", "suggestion"]
    explanation: str
    suggestion: str


class EssayReview(CompactModel):
    summary: str
    strengths: list[str] = Field(default_factory=list)
    issues: list[ReviewIssue] = Field(default_factory=list, max_length=35)


class ChapterPayload(CompactModel):
    content: str = Field(min_length=100)
    unresolved: list[str] = Field(default_factory=list)
    summary: str


class RevisionInput(CompactModel):
    expected_version: int
    expected_hashes: dict[str, str]
    expected_review_at: str = ""
    resume: bool = False


class ChapterEdit(CompactModel):
    content: str = Field(min_length=1, max_length=500000)
    expected_hash: str


class PlanEdit(CompactModel):
    plan: EssayPlan
    expected_version: int


class BriefEdit(CompactModel):
    brief: EssayBrief
    expected_version: int


class SourceInput(CompactModel):
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(default="", max_length=500)
    published: str = Field(default="", max_length=100)
    text: str = Field(default="", max_length=250000)
    url: str = Field(default="", max_length=2000)
    kind: Literal["web", "document", "author_notes"] = "author_notes"


class SourceEdit(CompactModel):
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(default="", max_length=500)
    published: str = Field(default="", max_length=100)
    expected_version: int


class EvidenceInput(CompactModel):
    quote: str = Field(min_length=8, max_length=4000)
    stance: Literal["supports", "contradicts", "mixed", "context"] = "context"
    explanation: str = Field(default="", max_length=2000)


class SearchInput(CompactModel):
    query: str = Field(min_length=3, max_length=1500)


class AnswersInput(CompactModel):
    answers: dict[str, str] = Field(default_factory=dict, max_length=7)


class ApprovalInput(CompactModel):
    expected_version: int


class EssaySession:
    """Reuse transactional chapters/jobs/revisions with an essay-only payload."""
    def __init__(self, session_id, brief):
        self.session_id = session_id
        self.form_data = brief
        self.product_id = "saggia"
        self.current_version = 1
        self.outline_version = 0
        self.generated_questions = []
        self.answers = {}
        self.plan = None
        self.validated = False
        self.sources = []
        self.research_log = []
        self.review = None
        self.book_chapters = []
        self.pause_requested = False
        self.questions_progress = None
        self.draft_progress = None
        self.memory_progress = None
        self.outline_progress = None
        self.writing_progress = None
        self.review_progress = None
        self.revision_progress = None
        self.revision_request = None
        self.cover_image_path = None
        self.cover_progress = None
        self.part_checkpoint = None
        self.research_request = None
        self.created_at = now()
        self.updated_at = now()
        self.user_id = None
        self.legacy_cost_unverifiable = False
        self.token_usage = {}
        self.real_cost_eur = None

    def update_timestamp(self):
        self.updated_at = now()

    def get_status(self):
        if self.writing_progress:
            return self.writing_progress.get("status", "draft")
        return "planned" if self.plan else "draft"

    def to_dict(self):
        return {k: (v.model_dump() if isinstance(v, BaseModel) else v)
                for k, v in vars(self).items() if not k.startswith("_")}

    @classmethod
    def from_dict(cls, data):
        if data.get("product_id") != "saggia":
            raise ValueError("Questo archivio contiene progetti di un altro prodotto.")
        session = cls(data["session_id"], EssayBrief(**data["form_data"]))
        for key, value in data.items():
            if key != "form_data" and not key.startswith("_"):
                setattr(session, key, value)
        return session

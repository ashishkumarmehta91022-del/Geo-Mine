"""AI Query API schemas (Step 10) — mirror of the service result contract."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AIQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    mode: str = Field(default="hybrid")
    limit: int | None = Field(default=None, ge=1, le=20)


class ConflictNotice(BaseModel):
    entity: str | None = None
    metric: str | None = None
    reporting_period: str | None = None
    values: list[str]
    evidence_ids: list[int]


class EvidenceItem(BaseModel):
    # Full provenance — mirrors app/ai/evidence.py to_payload().
    evidence_id: int
    unit_type: str
    document_id: int
    document_name: str | None = None
    page_id: int | None = None
    page_number: int | None = None
    record_id: int | None = None
    validation_id: int | None = None
    source_reference: str | None = None
    extraction_method: str | None = None
    validation_status: str | None = None
    ocr_confidence: float | None = None
    entity: str | None = None
    metric: str | None = None
    unit: str | None = None
    reporting_period: str | None = None
    value_raw: str | None = None
    normalized_value: str | None = None
    snippet: str | None = None
    # Retrieval metrics — relevance, never trust.
    lexical_score: float | None = None
    semantic_similarity: float | None = None
    relevance: float | None = None


class AIQueryResponse(BaseModel):
    status: str                      # ok | insufficient_evidence | llm_unavailable | llm_error
    question: str
    answer: str | None = None        # None when the LLM could not be used
    evidence: list[EvidenceItem] = []
    evidence_ids: list[int] = []
    retrieval_mode: str
    retrieval_total: int | None = None
    conflict_detected: bool = False
    conflicts: list[ConflictNotice] = []
    insufficient_evidence: bool = False
    provider: str | None = None
    model: str | None = None
    limitations: str | None = None
    error: str | None = None
    retrieval_note: str | None = None
    latency_ms: int | None = None
    invalid_citations_dropped: list[int] = []
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Honest labeling, always attached for AI answers.
    grounding_note: str = (
        "Answers are generated only from the cited project evidence below — "
        "not general knowledge. Scores are retrieval metrics, not trust. "
        "Verify every value against its source document."
    )

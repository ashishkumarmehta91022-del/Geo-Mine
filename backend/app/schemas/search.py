"""Search API schemas (Step 8)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    # Provenance (always present).
    unit_type: str
    document_id: int
    document_name: str | None = None
    page_id: int | None = None
    page_number: int | None = None
    record_id: int | None = None
    validation_id: int | None = None
    source_reference: str | None = None
    extraction_method: str | None = None
    # Content.
    title: str | None = None
    snippet: str | None = None
    # Structured-record metadata when applicable.
    entity: str | None = None
    metric: str | None = None
    value_raw: str | None = None
    normalized_value: str | None = None
    unit: str | None = None
    reporting_period: str | None = None
    validation_status: str | None = None
    ocr_confidence: float | None = None
    # Deterministic lexical score (Step 8 arithmetic — relevance, not trust).
    rank_score: float | None = None
    # Step 9: cosine similarity in [-1, 1] — a relevance metric, never truth.
    semantic_similarity: float | None = None
    # Step 9 hybrid: explicit weighted combination (0.6·lexical_norm + 0.4·semantic_norm).
    relevance: float | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    limit: int
    offset: int
    results: list[SearchResultItem]
    # Present for semantic/hybrid modes (or when semantic failed in hybrid).
    mode: str | None = None
    semantic_available: bool | None = None
    semantic_error: str | None = None
    # Honest labeling of what scores mean (retrieval metrics, not trust).
    retrieval_note: str | None = None


class KnowledgeStatsResponse(BaseModel):
    documents_indexed: int
    pages_indexed: int
    records_indexed: int
    validation_results_indexed: int
    total_units: int
    last_index_update: datetime | None
    # Step 9 facts.
    embedded_units: int = 0
    embedding_error_units: int = 0
    embedding_models: list[str] = []

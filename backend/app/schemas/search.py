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
    # Deterministic ranking score (documented arithmetic, not a trust score).
    rank_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    limit: int
    offset: int
    results: list[SearchResultItem]


class KnowledgeStatsResponse(BaseModel):
    documents_indexed: int
    pages_indexed: int
    records_indexed: int
    validation_results_indexed: int
    total_units: int
    last_index_update: datetime | None

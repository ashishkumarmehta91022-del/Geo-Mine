"""Dashboard API schemas (Step 14) — read-only operational aggregation.

All values come from existing source-of-truth tables/services. When the
database is unreachable the response is still 200 with `data_available=False`
and metric sections set to None — the UI shows an honest offline state
instead of fabricated zeroes.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DashboardStatus(BaseModel):
    component: str
    status: str                    # OPERATIONAL | CONNECTED | UNAVAILABLE | NOT CONFIGURED | DEGRADED
    detail: str | None = None


class RecentDocumentItem(BaseModel):
    document_id: int
    filename: str
    document_type: str
    status: str
    validation_status: str | None
    extraction_status: str | None
    uploaded_at: datetime | None
    processed_at: datetime | None
    record_count: int
    requires_review: bool


class RecentActivityItem(BaseModel):
    action: str
    entity_type: str | None
    created_at: datetime


class DocumentMetrics(BaseModel):
    total: int
    processed: int
    failed: int
    processing: int
    uploaded: int
    by_status: dict[str, int]


class RecordMetrics(BaseModel):
    total: int
    by_status: dict[str, int]
    validated: int               # pass/valid statuses
    pending: int
    flagged: int                 # warning/error/review_required/failed


class ValidationMetrics(BaseModel):
    total: int
    by_status: dict[str, int]
    review_required: int
    errors: int
    warnings: int


class KnowledgeMetrics(BaseModel):
    total_units: int
    pages: int
    records: int
    validations: int
    embedded_units: int
    embedding_coverage: float    # 0..1 over indexed units
    documents_indexed: int


class IntelligenceAvailability(BaseModel):
    available: bool              # DB reachable AND indexed documents exist
    indexed_documents: int
    detail: str | None = None
    topic_count: int | None = None
    top_topics: list[dict[str, Any]] = []
    top_terms: list[dict[str, Any]] = []


class DashboardSummary(BaseModel):
    """Operational dashboard payload (metadata only — no document contents)."""

    data_available: bool
    message: str | None = None
    database: DashboardStatus
    api: DashboardStatus
    retrieval: DashboardStatus
    embeddings: DashboardStatus
    llm: DashboardStatus
    documents: DocumentMetrics | None = None
    records: RecordMetrics | None = None
    validation: ValidationMetrics | None = None
    knowledge: KnowledgeMetrics | None = None
    intelligence: IntelligenceAvailability | None = None
    recent_documents: list[RecentDocumentItem] = []
    recent_activity: list[RecentActivityItem] = []
    limitations: list[str] = []


class DashboardStatuses(BaseModel):
    """Status-only summary for lightweight polling."""

    data_available: bool
    api: DashboardStatus
    database: DashboardStatus
    retrieval: DashboardStatus
    embeddings: DashboardStatus
    llm: DashboardStatus

"""Dashboard aggregation service (Step 14).

Read-only composition of existing source-of-truth data. Pure builders
(document/record/validation metrics, recent-document items, component
statuses) accept plain data and are unit-testable without a database.
Nothing here writes to the database; the API layer appends one audit row.
"""

import logging
from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import DocumentStatus
from app.exceptions import AppError, DatabaseUnavailableError
from app.schemas.dashboard import (
    DashboardStatus,
    DocumentMetrics,
    IntelligenceAvailability,
    KnowledgeMetrics,
    RecentActivityItem,
    RecentDocumentItem,
    RecordMetrics,
    ValidationMetrics,
)

logger = logging.getLogger(__name__)

# Bounds (bounded dashboard queries; metadata only).
MAX_RECENT_DOCUMENTS = 8
MAX_RECENT_ACTIVITY = 8
MAX_TOP_TOPICS = 5
MAX_TOP_TERMS = 8
MAX_STATUS_SAMPLE = 5000

VALIDATED_STATUSES = {"pass", "valid"}
FLAGGED_STATUSES = {"warning", "error", "review_required", "failed"}
DOCUMENT_REVIEW_STATUSES = {"warning", "error", "review_required"}


def pure_document_metrics(by_status: dict[str, int]) -> DocumentMetrics:
    """Deterministic document metrics from a status -> count mapping."""
    by_status = {str(k): int(v) for k, v in by_status.items()}
    return DocumentMetrics(
        total=sum(by_status.values()),
        processed=by_status.get(DocumentStatus.PROCESSED.value, 0),
        failed=by_status.get(DocumentStatus.FAILED.value, 0),
        processing=by_status.get(DocumentStatus.PROCESSING.value, 0),
        uploaded=by_status.get(DocumentStatus.UPLOADED.value, 0),
        by_status=by_status,
    )


def pure_record_metrics(by_status: dict[str, int]) -> RecordMetrics:
    """Deterministic record metrics from a validation-status -> count mapping."""
    by_status = {str(k): int(v) for k, v in by_status.items()}
    return RecordMetrics(
        total=sum(by_status.values()),
        by_status=by_status,
        validated=sum(count for status, count in by_status.items()
                      if status in VALIDATED_STATUSES),
        pending=by_status.get("pending", 0),
        flagged=sum(count for status, count in by_status.items()
                    if status in FLAGGED_STATUSES),
    )


def pure_validation_metrics(by_status: dict[str, int]) -> ValidationMetrics:
    """Deterministic validation-result metrics from a status -> count mapping."""
    by_status = {str(k): int(v) for k, v in by_status.items()}
    return ValidationMetrics(
        total=sum(by_status.values()),
        by_status=by_status,
        review_required=by_status.get("review_required", 0),
        errors=by_status.get("error", 0),
        warnings=by_status.get("warning", 0),
    )


def build_recent_documents(rows: list[dict[str, Any]]) -> list[RecentDocumentItem]:
    """Deterministic recent-document items (metadata only, bounded)."""
    return [
        RecentDocumentItem(
            document_id=row["document_id"],
            filename=row["filename"],
            document_type=row["document_type"],
            status=row["status"],
            validation_status=row["validation_status"],
            extraction_status=row["extraction_status"],
            uploaded_at=row["uploaded_at"],
            processed_at=row["processed_at"],
            record_count=row["record_count"],
            requires_review=row["requires_review"],
        )
        for row in rows[:MAX_RECENT_DOCUMENTS]
    ]


def compute_statuses(
    *,
    db_connected: bool,
    db_detail: str | None,
    index_stats: dict[str, Any] | None,
    llm_configured: bool,
) -> dict[str, DashboardStatus]:
    """Honest component statuses — an unavailable dependency is never healthy."""
    database = (
        DashboardStatus(component="database", status="CONNECTED", detail=db_detail)
        if db_connected
        else DashboardStatus(
            component="database", status="UNAVAILABLE",
            detail=db_detail or "PostgreSQL is not reachable.",
        )
    )
    if not db_connected:
        retrieval = DashboardStatus(
            component="retrieval", status="UNAVAILABLE",
            detail="Retrieval requires the database.",
        )
        embeddings = DashboardStatus(
            component="embeddings", status="UNAVAILABLE",
            detail="Embedding coverage requires the database.",
        )
    else:
        total_units = int((index_stats or {}).get("total_units", 0) or 0)
        if total_units == 0:
            retrieval = DashboardStatus(
                component="retrieval", status="DEGRADED",
                detail="No indexed content yet — process documents to populate the index.",
            )
            embeddings = DashboardStatus(
                component="embeddings", status="NOT CONFIGURED",
                detail="No embedded units yet.",
            )
        else:
            retrieval = DashboardStatus(component="retrieval", status="OPERATIONAL")
            embedded = int((index_stats or {}).get("embedded_units", 0) or 0)
            if embedded == 0:
                embeddings = DashboardStatus(
                    component="embeddings", status="NOT CONFIGURED",
                    detail="No units embedded yet.",
                )
            elif embedded < total_units:
                embeddings = DashboardStatus(
                    component="embeddings", status="DEGRADED",
                    detail=f"{embedded}/{total_units} indexed units embedded.",
                )
            else:
                embeddings = DashboardStatus(
                    component="embeddings", status="OPERATIONAL"
                )
    llm = (
        DashboardStatus(component="llm", status="NOT CONFIGURED")
        if not llm_configured
        else DashboardStatus(component="llm", status="OPERATIONAL")
    )
    return {"database": database, "retrieval": retrieval,
            "embeddings": embeddings, "llm": llm}


def _grouped_counts(db: Session, column) -> dict[str, int]:
    """One grouped COUNT over an existing table (read-only, bounded by data)."""
    rows = db.execute(
        select(column, func.count()).group_by(column)
    ).all()
    return {str(status): int(count) for status, count in rows}


def build_dashboard_summary(db: Session) -> dict[str, Any]:
    """Compose the full dashboard payload (read-only, offline-safe)."""
    from app.db import probe_database
    from app.intelligence.corpus import MAX_CORPUS_DOCUMENTS, build_corpus
    from app.intelligence.topics import identify_topics
    from app.intelligence.wordcloud import generate_word_cloud
    from app.llm.config import default_config
    from app.llm.service import llm_available
    from app.models import (
        AuditLog,
        Document,
        ExtractedRecord,
        ValidationResult,
    )
    from app.services import knowledge_service

    llm_configured = llm_available(default_config())
    connected, detail = probe_database()
    limitations = [
        "Dashboard is read-only aggregation over source-of-truth tables.",
        "No authentication yet — the API is unauthenticated in this "
        "prototype; do not expose it publicly.",
        "Aggregates are computed on request and not persisted.",
    ]

    if not connected:
        statuses = compute_statuses(
            db_connected=False, db_detail=detail, index_stats=None,
            llm_configured=llm_configured,
        )
        return {
            "data_available": False,
            "message": (
                "Database unavailable — live operational metrics cannot be "
                "queried. No demo values are shown."
            ),
            "database": statuses["database"],
            "api": DashboardStatus(component="api", status="OPERATIONAL"),
            "retrieval": statuses["retrieval"],
            "embeddings": statuses["embeddings"],
            "llm": statuses["llm"],
            "documents": None,
            "records": None,
            "validation": None,
            "knowledge": None,
            "intelligence": None,
            "recent_documents": [],
            "recent_activity": [],
            "limitations": limitations,
        }

    try:
        document_by_status = _grouped_counts(db, Document.status)
        record_by_status = _grouped_counts(db, ExtractedRecord.validation_status)
        validation_by_status = _grouped_counts(db, ValidationResult.status)
        recent_rows = db.execute(
            select(
                Document.id, Document.filename, Document.document_type,
                Document.status, Document.validation_status,
                Document.extraction_status, Document.uploaded_at,
                Document.processed_at,
            ).order_by(Document.id.desc()).limit(MAX_RECENT_DOCUMENTS)
        ).all()
        recent_ids = [row.id for row in recent_rows]
        record_counts: dict[int, int] = {}
        if recent_ids:
            record_counts = {
                document_id: int(count)
                for document_id, count in db.execute(
                    select(
                        ExtractedRecord.document_id, func.count()
                    )
                    .where(ExtractedRecord.document_id.in_(recent_ids))
                    .group_by(ExtractedRecord.document_id)
                ).all()
            }
        audit_rows = db.execute(
            select(AuditLog.action, AuditLog.entity_type, AuditLog.created_at)
            .order_by(AuditLog.created_at.desc())
            .limit(MAX_RECENT_ACTIVITY)
        ).all()
        index_stats = knowledge_service.index_statistics(db)
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc

    documents = pure_document_metrics(document_by_status)
    records = pure_record_metrics(record_by_status)
    validation = pure_validation_metrics(validation_by_status)
    total_units = int(index_stats.get("total_units", 0) or 0)
    embedded_units = int(index_stats.get("embedded_units", 0) or 0)
    knowledge = KnowledgeMetrics(
        total_units=total_units,
        pages=int(index_stats.get("pages_indexed", 0) or 0),
        records=int(index_stats.get("records_indexed", 0) or 0),
        validations=int(index_stats.get("validation_results_indexed", 0) or 0),
        embedded_units=embedded_units,
        embedding_coverage=(embedded_units / total_units) if total_units else 0.0,
        documents_indexed=int(index_stats.get("documents_indexed", 0) or 0),
    )

    indexed_documents = knowledge.documents_indexed
    if indexed_documents == 0:
        intelligence = IntelligenceAvailability(
            available=False, indexed_documents=0,
            detail="No indexed documents yet — intelligence is unavailable.",
        )
    else:
        try:
            corpus_ids = sorted(
                db.scalars(
                    select(Document.id).order_by(Document.id.desc())
                    .limit(MAX_CORPUS_DOCUMENTS)
                ).all()
            )
            corpus = build_corpus(db, corpus_ids)
            topics = identify_topics(corpus)["topics"][:MAX_TOP_TOPICS]
            cloud = generate_word_cloud(corpus)[:MAX_TOP_TERMS]
            intelligence = IntelligenceAvailability(
                available=bool(topics or cloud),
                indexed_documents=indexed_documents,
                topic_count=len(topics),
                top_topics=[
                    {"topic_id": t.topic_id, "label": t.label,
                     "score": round(t.score, 2)}
                    for t in topics
                ],
                top_terms=[
                    {"term": w.term, "display_term": w.display_term,
                     "frequency": w.frequency}
                    for w in cloud
                ],
            )
        except (AppError, DatabaseUnavailableError):
            raise
        except Exception as exc:  # noqa: BLE001 — intelligence is best-effort
            logger.warning("Intelligence summary unavailable: %s", exc.__class__.__name__)
            intelligence = IntelligenceAvailability(
                available=False, indexed_documents=indexed_documents,
                detail="Intelligence summary could not be computed.",
            )

    statuses = compute_statuses(
        db_connected=True, db_detail=detail, index_stats=index_stats,
        llm_configured=llm_configured,
    )
    recent_documents = build_recent_documents([
        {
            "document_id": row.id,
            "filename": row.filename,
            "document_type": row.document_type,
            "status": row.status,
            "validation_status": row.validation_status,
            "extraction_status": row.extraction_status,
            "uploaded_at": row.uploaded_at,
            "processed_at": row.processed_at,
            "record_count": record_counts.get(row.id, 0),
            "requires_review": (row.validation_status or "") in DOCUMENT_REVIEW_STATUSES,
        }
        for row in recent_rows
    ])
    recent_activity = [
        RecentActivityItem(
            action=row.action, entity_type=row.entity_type, created_at=row.created_at
        )
        for row in audit_rows
    ]

    return {
        "data_available": True,
        "message": None,
        "database": statuses["database"],
        "api": DashboardStatus(component="api", status="OPERATIONAL"),
        "retrieval": statuses["retrieval"],
        "embeddings": statuses["embeddings"],
        "llm": statuses["llm"],
        "documents": documents,
        "records": records,
        "validation": validation,
        "knowledge": knowledge,
        "intelligence": intelligence,
        "recent_documents": recent_documents,
        "recent_activity": recent_activity,
        "limitations": limitations + [
            "Validation/record status distributions are live grouped counts.",
        ],
    }


def audit_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Safe audit metadata — counts only, never document contents."""
    return {
        "data_available": payload.get("data_available"),
        "document_total": (payload.get("documents") or {}).get("total"),
        "record_total": (payload.get("records") or {}).get("total"),
        "validation_review_required": (payload.get("validation") or {}).get(
            "review_required"
        ),
        "intelligence_available": (payload.get("intelligence") or {}).get(
            "available"
        ),
        "recent_document_count": len(payload.get("recent_documents", []) or []),
        "recent_activity_count": len(payload.get("recent_activity", []) or []),
    }

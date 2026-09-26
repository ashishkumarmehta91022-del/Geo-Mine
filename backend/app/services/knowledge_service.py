"""Knowledge service: index lifecycle + deterministic search.

Index lifecycle (idempotent):
- index_document: rebuild one document's entries (delete-replace) — call
  after processing/validation so entries reflect current derived data.
- remove_document: explicit cleanup (CASCADE also covers document deletion).
- reindex_all: rebuild every document's entries.

Search: SQLAlchemy expression trees only (no string SQL). Ranking uses the
deterministic scoring in app/knowledge/ranking.py; ties break by
(unit priority, document_id, id). Every result carries provenance.
"""

import logging
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import RetrievalUnitType
from app.exceptions import AppError, DatabaseUnavailableError
from app.knowledge.query_parser import SearchQuery
from app.knowledge.ranking import rank_unit
from app.knowledge.units import units_from_rows
from app.models import Document, DocumentPage, ExtractedRecord, KnowledgeIndex, ValidationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Index lifecycle (idempotent)
# ---------------------------------------------------------------------------


def _load_document_rows(db: Session, document_id: int) -> tuple[Document, list, list, list]:
    document = db.get(Document, document_id)
    if document is None:
        raise AppError(status_code=404, code="document_not_found", message="Document not found.")
    pages = db.execute(
        select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number)
    ).scalars().all()
    records = db.execute(
        select(ExtractedRecord).where(ExtractedRecord.document_id == document_id).order_by(ExtractedRecord.id)
    ).scalars().all()
    validations = db.execute(
        select(ValidationResult).where(ValidationResult.document_id == document_id).order_by(ValidationResult.id)
    ).scalars().all()
    return document, list(pages), list(records), list(validations)


def _write_units(db: Session, document: Document, drafts) -> int:
    """Delete-replace one document's index entries (no commit — caller owns tx)."""
    db.execute(delete(KnowledgeIndex).where(KnowledgeIndex.document_id == document.id))
    for draft in drafts:
        db.add(
            KnowledgeIndex(
                document_id=draft.document_id,
                page_id=draft.page_id,
                record_id=draft.record_id,
                validation_id=draft.validation_id,
                unit_type=draft.unit_type,
                title=draft.title,
                content=draft.content,
                source_reference=draft.source_reference,
                entity=draft.entity,
                metric=draft.metric,
                reporting_period=draft.reporting_period,
                extraction_method=draft.extraction_method,
                validation_status=draft.validation_status,
                ocr_confidence=draft.ocr_confidence,
            )
        )
    # PostgreSQL-native full-text vectors, computed in-database.
    db.execute(
        text(
            """
            UPDATE knowledge_index
            SET search_vector = to_tsvector('english',
                coalesce(title, '') || ' ' || coalesce(content, '') || ' ' ||
                coalesce(entity, '') || ' ' || coalesce(metric, ''))
            WHERE document_id = :document_id
            """
        ),
        {"document_id": document.id},
    )
    return len(drafts)


def index_document(db: Session, document_id: int) -> int:
    """Rebuild one document's retrieval entries. Idempotent (delete-replace)."""
    try:
        document, pages, records, validations = _load_document_rows(db, document_id)
        drafts = units_from_rows(pages, records, validations, document.filename)
        created = _write_units(db, document, drafts)
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Indexing failed for document %s", document_id)
        raise AppError(
            status_code=500, code="indexing_failed", message="Could not update the search index."
        ) from exc
    return created


def remove_document(db: Session, document_id: int) -> int:
    """Remove a document's retrieval entries (explicit cleanup). Idempotent."""
    try:
        result = db.execute(
            delete(KnowledgeIndex).where(KnowledgeIndex.document_id == document_id)
        )
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Index removal failed for document %s", document_id)
        raise AppError(
            status_code=500, code="indexing_failed", message="Could not clean the search index."
        ) from exc
    return int(result.rowcount or 0)


def reindex_all(db: Session) -> dict[str, int]:
    """Rebuild the whole index from current source data. Returns counts."""
    try:
        document_ids = db.execute(select(Document.id).order_by(Document.id)).scalars().all()
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not list documents."
        ) from exc

    total_units = 0
    for document_id in document_ids:
        total_units += index_document(db, int(document_id))
    return {"documents": len(document_ids), "units": total_units}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _apply_filters(stmt, query: SearchQuery):
    if query.document_id is not None:
        stmt = stmt.where(KnowledgeIndex.document_id == query.document_id)
    if query.entity is not None:
        stmt = stmt.where(KnowledgeIndex.entity == query.entity)
    if query.metric is not None:
        stmt = stmt.where(KnowledgeIndex.metric == query.metric)
    if query.reporting_period is not None:
        stmt = stmt.where(KnowledgeIndex.reporting_period == query.reporting_period)
    if query.extraction_method is not None:
        stmt = stmt.where(KnowledgeIndex.extraction_method == query.extraction_method)
    if query.validation_status is not None:
        stmt = stmt.where(KnowledgeIndex.validation_status == query.validation_status)
    if query.page is not None:
        # Page filter applies to page-type units via their source reference
        # or page_id join; page_id is stored directly on entries.
        stmt = stmt.where(KnowledgeIndex.page_id.is_not(None)).where(
            KnowledgeIndex.source_reference.ilike(f"%{query.page}%")
        )
    return stmt


def _text_conditions(query: SearchQuery):
    """Text conditions: exact phrases (LIKE on indexed text) + keyword ANDs."""
    conditions = []
    for phrase in query.phrases:
        pattern = f"%{phrase.lower()}%"
        conditions.append(
            func.lower(func.coalesce(KnowledgeIndex.title, "") + " " + func.coalesce(KnowledgeIndex.content, "")).like(pattern)
        )
    for keyword in query.keywords:
        needle = f"%{keyword.lower()}%"
        conditions.append(
            func.lower(func.coalesce(KnowledgeIndex.title, "") + " " + func.coalesce(KnowledgeIndex.content, "")).like(needle)
        )
    return conditions


def search(db: Session, query: SearchQuery) -> dict[str, Any]:
    """Deterministic search over the retrieval index.

    No text and no filters → empty result set (not the whole index).
    Results always carry provenance; ranking is documented arithmetic.
    """
    if not query.has_text and not query.has_filters:
        return {"query": query.text, "total": 0, "results": []}

    try:
        base = select(KnowledgeIndex)
        base = _apply_filters(base, query)
        for condition in _text_conditions(query):
            base = base.where(condition)

        total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()

        rows = db.execute(
            base.order_by(KnowledgeIndex.document_id, KnowledgeIndex.id)
            .offset(query.offset)
            .limit(query.limit)
        ).scalars().all()

        # Deterministic in-memory ranking of the fetched page (stable keys).
        ranked = sorted(
            rows,
            key=lambda row: (
                -rank_unit(
                    phrases=query.phrases,
                    keywords=query.keywords,
                    title=row.title,
                    content=row.content,
                    entity=row.entity,
                    metric=row.metric,
                    unit_type=row.unit_type,
                ),
                UNIT_ORDER.get(row.unit_type, 0),
                row.document_id,
                row.id,
            ),
        )
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(status_code=500, code="database_error", message="Search failed.") from exc

    return {"query": query.text, "total": int(total), "results": ranked}


UNIT_ORDER = {
    RetrievalUnitType.RECORD: 0,
    RetrievalUnitType.PAGE: 1,
    RetrievalUnitType.VALIDATION: 2,
}


# ---------------------------------------------------------------------------
# Statistics (actual database values only)
# ---------------------------------------------------------------------------


def index_statistics(db: Session) -> dict[str, Any]:
    try:
        by_type = db.execute(
            select(KnowledgeIndex.unit_type, func.count())
            .group_by(KnowledgeIndex.unit_type)
        ).all()
        documents = db.execute(select(func.count()).select_from(KnowledgeIndex.document_id.distinct())).scalar_one()
        last_update = db.execute(select(func.max(KnowledgeIndex.updated_at))).scalar_one()
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not load index statistics."
        ) from exc

    counts = {unit_type: int(count) for unit_type, count in by_type}
    return {
        "documents_indexed": int(documents),
        "pages_indexed": counts.get(RetrievalUnitType.PAGE, 0),
        "records_indexed": counts.get(RetrievalUnitType.RECORD, 0),
        "validation_results_indexed": counts.get(RetrievalUnitType.VALIDATION, 0),
        "total_units": int(sum(counts.values())),
        "last_index_update": last_update.isoformat() if last_update else None,
    }

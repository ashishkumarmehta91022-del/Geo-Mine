"""Knowledge service: index lifecycle + deterministic + semantic search.

Index lifecycle (idempotent):
- index_document: rebuild one document's entries (delete-replace) — call
  after processing/validation so entries reflect current derived data.
- embed_document: best-effort semantic embedding of entries (Step 9) — never
  fails processing; failures recorded honestly per row.
- remove_document: explicit cleanup (CASCADE also covers document deletion).
- reindex_all: rebuild every document's entries.

Search: SQLAlchemy expression trees only (no string SQL). Lexical ranking uses
the deterministic scoring in app/knowledge/ranking.py; semantic mode uses
cosine similarity over stored provider vectors; hybrid merges both with an
explicit, documented formula. Every result carries provenance.
"""

import logging
import math
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import EmbeddingStatus, RetrievalUnitType
from app.embeddings import default_config as default_embedding_config
from app.embeddings.inputs import build_embedding_input
from app.embeddings.service import embedding_available, timed_embed
from app.exceptions import AppError, DatabaseUnavailableError
from app.knowledge.query_parser import SearchQuery
from app.knowledge.ranking import rank_unit
from app.knowledge.units import units_from_rows
from app.models import Document, DocumentPage, ExtractedRecord, KnowledgeIndex, ValidationResult

logger = logging.getLogger(__name__)

# Hybrid merge weights — explicit, deterministic, documented in the report.
HYBRID_LEXICAL_WEIGHT = 0.6
HYBRID_SEMANTIC_WEIGHT = 0.4
HYBRID_MAX_SEMANTIC_CANDIDATES = 100


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
                unit=draft.unit,
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
    """Deterministic LEXICAL search over the retrieval index (Step 8 contract).

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
# Semantic embeddings (Step 9) — best-effort, honest, never fake
# ---------------------------------------------------------------------------


def embed_document(db: Session, document_id: int) -> dict[str, Any]:
    """Embed a document's index entries. Best-effort: never raises for
    provider problems — failures are recorded per-row (embedding_status).

    Returns a factual summary: {embedded, failed, unavailable, skipped, total}.
    """
    config = default_embedding_config()
    summary: dict[str, Any] = {
        "document_id": document_id,
        "embedded": 0,
        "failed": 0,
        "unavailable": 0,
        "skipped": 0,
        "total": 0,
        "elapsed_seconds": None,
    }
    try:
        if db.get(Document, document_id) is None:
            raise AppError(status_code=404, code="document_not_found", message="Document not found.")
        rows = db.execute(
            select(KnowledgeIndex)
            .where(KnowledgeIndex.document_id == document_id)
            .order_by(KnowledgeIndex.id)
        ).scalars().all()
        # Deterministic order; bounded units per run.
        targets = [row for row in rows if row.content or row.title][: config.max_units_per_document]
        summary["total"] = len(rows)
        summary["skipped"] = len(rows) - len(targets)
        if not targets:
            return summary

        # Mark pending so state is visible; single commit per stage.
        for row in targets:
            row.embedding_status = EmbeddingStatus.PENDING
        db.commit()

        inputs = [build_embedding_input(_row_to_draft(row)) for row in targets]
        result, error, elapsed = timed_embed(inputs, config)
        summary["elapsed_seconds"] = round(elapsed, 2)

        if result is None:
            # Honest per-row state: unavailable vs failed.
            status = (
                EmbeddingStatus.UNAVAILABLE
                if error and error.startswith("unavailable")
                else EmbeddingStatus.FAILED
            )
            for row in targets:
                row.embedding_status = status
                row.embedding_error = error
            summary["failed" if status == EmbeddingStatus.FAILED else "unavailable"] = len(targets)
            db.commit()
            return summary

        for row, vector in zip(targets, result.vectors, strict=True):
            row.embedding = vector
            row.embedding_provider = result.provider
            row.embedding_model = result.model
            row.embedding_dimensions = result.dimensions
            row.embedding_status = EmbeddingStatus.EMBEDDED
            row.embedding_error = None
            row.embedded_at = func.now()
        summary["embedded"] = len(result.vectors)
        db.commit()
        return summary
    except OperationalError as exc:
        db.rollback()
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Embedding persistence failed for document %s", document_id)
        raise AppError(
            status_code=500,
            code="embedding_persistence_failed",
            message="Embeddings ran but could not be saved.",
        ) from exc


def _row_to_draft(row: KnowledgeIndex):
    """Rebuild the unit draft shape from a stored index row (for input text)."""
    from app.knowledge.units import IndexUnitDraft

    return IndexUnitDraft(
        unit_type=row.unit_type,
        document_id=row.document_id,
        page_id=row.page_id,
        record_id=row.record_id,
        validation_id=row.validation_id,
        title=row.title,
        content=row.content,
        source_reference=row.source_reference,
        entity=row.entity,
        metric=row.metric,
        unit=row.unit,
        reporting_period=row.reporting_period,
        extraction_method=row.extraction_method,
        validation_status=row.validation_status,
        ocr_confidence=float(row.ocr_confidence) if row.ocr_confidence is not None else None,
    )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity for equal-dimension vectors. Deterministic."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _semantic_candidates(
    db: Session, query: SearchQuery, query_vector: list[float], limit: int
) -> list[tuple[KnowledgeIndex, float]]:
    """Top-N semantically similar embedded rows, filters applied.

    Deterministic: brute-force cosine over embedded rows in the filter scope,
    ties broken by (document_id, id). Bounded candidate window.
    """
    base = select(KnowledgeIndex).where(
        KnowledgeIndex.embedding_status == EmbeddingStatus.EMBEDDED,
        KnowledgeIndex.embedding.is_not(None),
    )
    base = _apply_filters(base, query)
    rows = db.execute(
        base.order_by(KnowledgeIndex.document_id, KnowledgeIndex.id)
        .limit(HYBRID_MAX_SEMANTIC_CANDIDATES)
    ).scalars().all()

    scored = [
        (row, _cosine_similarity(query_vector, list(row.embedding)))
        for row in rows
    ]
    scored.sort(key=lambda pair: (-pair[1], pair[0].document_id, pair[0].id))
    return scored[:limit]


def search_semantic(db: Session, query: SearchQuery, query_vector: list[float]) -> dict[str, Any]:
    """Semantic-only search over embedded entries.

    Scores are cosine similarity in [-1, 1], labeled `semantic_similarity` —
    a relevance metric, never truth/correctness/trust.
    """
    if not query.has_text and not query.has_filters:
        return {"query": query.text, "total": 0, "results": [], "semantic_available": True}
    try:
        pairs = _semantic_candidates(
            db, query, query_vector, query.offset + query.limit
        )
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(status_code=500, code="database_error", message="Semantic search failed.") from exc

    window = pairs[query.offset : query.offset + query.limit]
    return {
        "query": query.text,
        "total": len(pairs),
        "results": [row for row, _score in window],
        # Same merge-entry shape as search_hybrid so the route layer and the
        # hybrid merge read one uniform contract (row + component scores).
        "scores": {
            row.id: {"row": row, "lexical": None, "semantic": score, "combined": None}
            for row, score in window
        },
        "semantic_available": True,
    }


def search_hybrid(db: Session, query: SearchQuery, query_vector: list[float]) -> dict[str, Any]:
    """Hybrid search: lexical ∪ semantic, merged deterministically.

    Combined score = HYBRID_LEXICAL_WEIGHT * normalized_lexical
                   + HYBRID_SEMANTIC_WEIGHT * normalized_semantic
    where lexical is min-max normalized within the candidate set and semantic
    is cosine mapped to [0,1] via (1 + cos) / 2. Both raw scores stay exposed;
    the formula is explicit and deterministic. Provenance and conflicts are
    untouched — similarity never overrides validation state.
    """
    lexical = search(db, query)
    semantic = search_semantic(db, query, query_vector)

    combined: dict[int, dict[str, Any]] = {}
    lexical_scores: list[float] = [
        rank_unit(
            phrases=query.phrases,
            keywords=query.keywords,
            title=row.title,
            content=row.content,
            entity=row.entity,
            metric=row.metric,
            unit_type=row.unit_type,
        )
        for row in lexical["results"]
    ]
    # Min-max normalize lexical scores within this result page (deterministic).
    lo = min(lexical_scores, default=0.0)
    hi = max(lexical_scores, default=0.0)
    span = (hi - lo) or 1.0

    for row, lexical_score in zip(lexical["results"], lexical_scores, strict=True):
        normalized_lexical = (lexical_score - lo) / span
        combined[row.id] = {
            "row": row,
            "lexical": lexical_score,
            "semantic": None,
            "combined": HYBRID_LEXICAL_WEIGHT * normalized_lexical,
        }
    for entry in semantic.get("scores", {}).values():
        row = entry["row"]
        similarity = entry["semantic"]
        if row.id in combined:
            merged = combined[row.id]
            merged["semantic"] = similarity
            merged["combined"] += HYBRID_SEMANTIC_WEIGHT * ((1.0 + similarity) / 2.0)
        else:
            combined[row.id] = {
                "row": row,
                "lexical": None,
                "semantic": similarity,
                "combined": HYBRID_SEMANTIC_WEIGHT * ((1.0 + similarity) / 2.0),
            }

    ordered = sorted(
        combined.values(),
        key=lambda entry: (
            -entry["combined"],
            UNIT_ORDER.get(entry["row"].unit_type, 0),
            entry["row"].document_id,
            entry["row"].id,
        ),
    )
    total = max(lexical["total"], semantic["total"])
    window = ordered[query.offset : query.offset + query.limit]
    return {
        "query": query.text,
        "total": total,
        "results": [entry["row"] for entry in window],
        "scores": {entry["row"].id: entry for entry in window},
        "semantic_available": semantic["semantic_available"],
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
        documents = db.execute(func.count(func.distinct(KnowledgeIndex.document_id))).scalar_one()
        last_update = db.execute(select(func.max(KnowledgeIndex.updated_at))).scalar_one()
        embedded = db.execute(
            select(func.count()).select_from(KnowledgeIndex).where(
                KnowledgeIndex.embedding_status == EmbeddingStatus.EMBEDDED
            )
        ).scalar_one()
        embedding_errors = db.execute(
            select(func.count()).select_from(KnowledgeIndex).where(
                KnowledgeIndex.embedding_status.in_([EmbeddingStatus.FAILED, EmbeddingStatus.UNAVAILABLE])
            )
        ).scalar_one()
        # (counts use select_from(KnowledgeIndex) — same pattern as every other service)
        embedding_models = db.execute(
            select(KnowledgeIndex.embedding_model).distinct().where(
                KnowledgeIndex.embedding_model.is_not(None)
            )
        ).scalars().all()
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not load index statistics."
        ) from exc

    counts = {unit_type: int(count) for unit_type, count in by_type}
    return {
        "documents_indexed": int(documents),
        "embedded_units": int(embedded),
        "embedding_error_units": int(embedding_errors),
        "embedding_models": sorted(model or "unknown" for model in embedding_models),
        "pages_indexed": counts.get(RetrievalUnitType.PAGE, 0),
        "records_indexed": counts.get(RetrievalUnitType.RECORD, 0),
        "validation_results_indexed": counts.get(RetrievalUnitType.VALIDATION, 0),
        "total_units": int(sum(counts.values())),
        "last_index_update": last_update.isoformat() if last_update else None,
    }

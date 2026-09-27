"""Search routes — lexical (Step 8), semantic and hybrid retrieval (Step 9).

Mode contract:
- mode omitted / "lexical" → exact Step 8 behavior (backward compatible).
- "semantic" → cosine similarity over embedded entries (requires text).
- "hybrid" → lexical ∪ semantic, explicit documented merge.

Scores are retrieval/relevance metrics — never truth, correctness or trust.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import RetrievalMode
from app.db import get_db
from app.exceptions import AppError
from app.embeddings import default_config as default_embedding_config
from app.embeddings.service import embedding_available, timed_embed
from app.knowledge.query_parser import MAX_LIMIT, parse_search_query
from app.knowledge.ranking import rank_unit
from app.models import Document, DocumentPage, ExtractedRecord
from app.schemas.search import KnowledgeStatsResponse, SearchResponse, SearchResultItem
from app.services import knowledge_service

router = APIRouter(prefix="/api/search", tags=["search"])


def _snippet(content: str | None, phrases: tuple[str, ...], keywords: tuple[str, ...], length: int = 220) -> str | None:
    """Deterministic snippet: first match window, else the opening text."""
    if not content:
        return None
    lowered = content.lower()
    needles = [p.lower() for p in phrases] + [k.lower() for k in keywords]
    position = next((lowered.find(n) for n in needles if n in lowered), -1)
    if position < 0:
        return content[:length]
    start = max(0, position - length // 4)
    return ("…" if start > 0 else "") + content[start : start + length]


def _query_vector(text: str) -> tuple[list[float] | None, str | None]:
    """Embed the query for semantic/hybrid modes. (vector, error)."""
    config = default_embedding_config()
    result, error, _elapsed = timed_embed([text], config)
    if error or result is None or not result.vectors:
        return None, error or "embedding produced no vector"
    return result.vectors[0], None


@router.get("", response_model=SearchResponse)
def search_route(
    q: str | None = Query(default=None, max_length=300),
    mode: str = Query(default=RetrievalMode.LEXICAL, description="lexical | semantic | hybrid"),
    document_id: int | None = Query(default=None, ge=1),
    page: int | None = Query(default=None, ge=1),
    entity: str | None = Query(default=None, max_length=256),
    metric: str | None = Query(default=None, max_length=128),
    reporting_period: str | None = Query(default=None, max_length=64),
    extraction_method: str | None = Query(default=None, max_length=32),
    validation_status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=20, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Retrieval over pages, records and validation results.

    Scores (`rank_score`, `semantic_similarity`, `relevance`) are retrieval
    metrics — never truth/correctness/trust. Conflicts stay visible; no
    automatic winner is ever selected.
    """
    if mode not in RetrievalMode.values():
        raise AppError(
            status_code=422,
            code="unsupported_mode",
            message=f"mode must be one of {sorted(RetrievalMode.values())}.",
        )
    parsed = parse_search_query(
        q=q,
        document_id=document_id,
        page=page,
        entity=entity,
        metric=metric,
        reporting_period=reporting_period,
        extraction_method=extraction_method,
        validation_status=validation_status,
        limit=limit,
        offset=offset,
    )

    semantic_error: str | None = None
    if mode in (RetrievalMode.SEMANTIC, RetrievalMode.HYBRID):
        if not parsed.has_text:
            raise AppError(
                status_code=422,
                code="empty_semantic_query",
                message=f"mode={mode} requires a text query (q).",
            )
        query_vector, embed_error = _query_vector(parsed.text)
        if query_vector is None:
            semantic_error = embed_error
            if mode == RetrievalMode.SEMANTIC:
                # Honest failure — no fake results.
                raise AppError(
                    status_code=503,
                    code="semantic_unavailable",
                    message=f"Semantic search is unavailable: {semantic_error}",
                )
            # hybrid falls back to lexical with the reason attached.

    if mode == RetrievalMode.SEMANTIC and query_vector is not None:
        data = knowledge_service.search_semantic(db, parsed, query_vector)
    elif mode == RetrievalMode.HYBRID and query_vector is not None:
        data = knowledge_service.search_hybrid(db, parsed, query_vector)
    else:
        data = knowledge_service.search(db, parsed)

    return _build_response(db, parsed, data, mode, semantic_error)


def _build_response(db: Session, parsed, data: dict, mode: str, semantic_error: str | None) -> SearchResponse:
    rows: list = data["results"]
    scores: dict = data.get("scores", {}) or {}

    document_ids = {row.document_id for row in rows}
    filenames: dict[int, str] = {}
    if document_ids:
        filenames = dict(
            db.execute(select(Document.id, Document.filename).where(Document.id.in_(document_ids))).all()
        )

    items: list[SearchResultItem] = []
    for row in rows:
        record_meta = _record_metadata(db, row)
        score_entry = scores.get(row.id) or {}
        lexical_score = score_entry.get("lexical")
        semantic_score = score_entry.get("semantic")
        combined = score_entry.get("combined")
        rank_score = (
            round(float(lexical_score), 2)
            if lexical_score is not None
            else round(
                rank_unit(
                    phrases=parsed.phrases,
                    keywords=parsed.keywords,
                    title=row.title,
                    content=row.content,
                    entity=row.entity,
                    metric=row.metric,
                    unit_type=row.unit_type,
                ),
                2,
            )
            if mode == RetrievalMode.LEXICAL
            else None
        )
        items.append(
            SearchResultItem(
                unit_type=row.unit_type,
                document_id=row.document_id,
                document_name=filenames.get(row.document_id),
                page_id=row.page_id,
                page_number=_page_number(db, row.page_id),
                record_id=row.record_id,
                validation_id=row.validation_id,
                source_reference=row.source_reference,
                extraction_method=row.extraction_method,
                title=row.title,
                snippet=_snippet(row.content, parsed.phrases, parsed.keywords),
                entity=row.entity,
                metric=row.metric,
                value_raw=record_meta.get("value_raw"),
                normalized_value=record_meta.get("normalized_value"),
                unit=record_meta.get("unit"),
                reporting_period=row.reporting_period,
                validation_status=row.validation_status,
                ocr_confidence=float(row.ocr_confidence) if row.ocr_confidence is not None else None,
                rank_score=rank_score,
                semantic_similarity=round(float(semantic_score), 4) if semantic_score is not None else None,
                relevance=round(float(combined), 4) if combined is not None else None,
            )
        )

    response = SearchResponse(
        query=data["query"],
        total=data["total"],
        limit=parsed.limit,
        offset=parsed.offset,
        results=items,
    )
    if mode != RetrievalMode.LEXICAL or semantic_error:
        response.mode = mode
        response.semantic_available = data.get("semantic_available", embedding_available())
        response.semantic_error = semantic_error
        response.retrieval_note = (
            "Scores are retrieval/relevance metrics (rank_score=lexical arithmetic, "
            "semantic_similarity=cosine, relevance=weighted hybrid) — NOT truth, "
            "correctness or trust. Conflicts remain visible; no winner is selected."
        )
    return response


def _page_number(db: Session, page_id: int | None) -> int | None:
    if page_id is None:
        return None
    page = db.get(DocumentPage, page_id)
    return page.page_number if page else None


def _record_metadata(db: Session, row) -> dict[str, str | None]:
    if row.unit_type != "record" or row.record_id is None:
        return {}
    record = db.get(ExtractedRecord, row.record_id)
    if record is None:
        return {}
    return {
        "value_raw": record.value_raw,
        "normalized_value": record.normalized_value,
        "unit": record.unit,
    }


@router.get("/stats", response_model=KnowledgeStatsResponse)
def search_stats_route(db: Session = Depends(get_db)) -> KnowledgeStatsResponse:
    """Factual index statistics from actual database values."""
    return KnowledgeStatsResponse(**knowledge_service.index_statistics(db))


@router.post("/embed/{document_id}")
def embed_document_route(document_id: int, db: Session = Depends(get_db)) -> dict:
    """Best-effort semantic embedding of a document's index entries.

    Never fails because embeddings are unavailable (e.g. offline environment):
    returns a factual summary with per-row status recorded in the index.
    Idempotent — re-running replaces embeddings for the same entries.
    """
    return knowledge_service.embed_document(db, document_id)

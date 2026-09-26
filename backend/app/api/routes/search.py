"""Search routes — deterministic retrieval over the knowledge index.

IMPORTANT: /api/search/stats is registered BEFORE /api/search's parameterized
routes; there is no /{id} collision here, but keeping static paths first is
the project convention.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.knowledge.query_parser import MAX_LIMIT, parse_search_query
from app.knowledge.ranking import rank_unit
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


@router.get("", response_model=SearchResponse)
def search_route(
    q: str | None = Query(default=None, max_length=300),
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
    """Deterministic search over pages, structured records and validation results.

    Every result carries provenance. Ranking is documented arithmetic — a
    higher rank never implies factual correctness.
    """
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
    data = knowledge_service.search(db, parsed)

    # Resolve document filenames + page numbers for provenance display.
    rows: list = data["results"]
    document_ids = {row.document_id for row in rows}
    filenames: dict[int, str] = {}
    if document_ids:
        from app.models import Document

        filenames = dict(
            db.execute(select(Document.id, Document.filename).where(Document.id.in_(document_ids))).all()
        )
    page_numbers = {
        row.page_id: number
        for row in rows
        if row.page_id
        for number in [_page_number(db, row.page_id)]
        if number
    }

    items = []
    for row in rows:
        record_meta = _record_metadata(db, row)
        items.append(
            SearchResultItem(
                unit_type=row.unit_type,
                document_id=row.document_id,
                document_name=filenames.get(row.document_id),
                page_id=row.page_id,
                page_number=page_numbers.get(row.page_id),
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
                rank_score=round(
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
                ),
            )
        )
    return SearchResponse(
        query=data["query"],
        total=data["total"],
        limit=parsed.limit,
        offset=parsed.offset,
        results=items,
    )


def _page_number(db: Session, page_id: int) -> int | None:
    from app.models import DocumentPage

    return db.get(DocumentPage, page_id).page_number if db.get(DocumentPage, page_id) else None


def _record_metadata(db: Session, row) -> dict[str, str | None]:
    if row.unit_type != "record" or row.record_id is None:
        return {}
    from app.models import ExtractedRecord

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

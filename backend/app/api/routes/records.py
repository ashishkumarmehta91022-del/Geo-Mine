"""Structured-record routes: per-document records + cross-document explorer.

Read-only foundation for the future Knowledge Base / RAG / reporting layers —
exact-match filtering only (no fuzzy entity resolution, no LLM).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.exceptions import AppError, DatabaseUnavailableError
from app.models import Document, ExtractedRecord
from app.schemas.records import RecordListResponse, RecordResponse

router = APIRouter(prefix="/api/records", tags=["records"])


def _to_response(row: ExtractedRecord, filename: str | None, page_number: int | None) -> RecordResponse:
    return RecordResponse(
        id=row.id,
        document_id=row.document_id,
        document_filename=filename,
        page_id=row.page_id,
        page_number=page_number,
        entity_name=row.entity_name,
        metric_name=row.metric_name,
        value_raw=row.value_raw,
        metric_value=row.metric_value,
        normalized_value=row.normalized_value,
        unit=row.unit,
        reporting_period=row.reporting_period,
        source_reference=row.source_reference,
        extraction_method=row.extraction_method,
        confidence=float(row.confidence) if row.confidence is not None else None,
        validation_status=row.validation_status,
        record_metadata=row.record_metadata,
    )


@router.get("", response_model=RecordListResponse)
def list_records_route(
    entity: str | None = Query(default=None, description="exact match"),
    metric: str | None = Query(default=None, description="exact match"),
    reporting_period: str | None = Query(default=None, description="exact match"),
    extraction_method: str | None = Query(default=None),
    document_id: int | None = Query(default=None),
    validation_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> RecordListResponse:
    """Cross-document structured records with exact-match dimension filters."""
    try:
        base = select(ExtractedRecord, Document.filename).join(
            Document, ExtractedRecord.document_id == Document.id
        )
        count_base = select(func.count()).select_from(ExtractedRecord)

        if document_id is not None:
            base = base.where(ExtractedRecord.document_id == document_id)
            count_base = count_base.where(ExtractedRecord.document_id == document_id)
        if entity is not None:
            base = base.where(ExtractedRecord.entity_name == entity)
            count_base = count_base.where(ExtractedRecord.entity_name == entity)
        if metric is not None:
            base = base.where(ExtractedRecord.metric_name == metric)
            count_base = count_base.where(ExtractedRecord.metric_name == metric)
        if reporting_period is not None:
            base = base.where(ExtractedRecord.reporting_period == reporting_period)
            count_base = count_base.where(ExtractedRecord.reporting_period == reporting_period)
        if extraction_method is not None:
            base = base.where(ExtractedRecord.extraction_method == extraction_method)
            count_base = count_base.where(ExtractedRecord.extraction_method == extraction_method)
        if validation_status is not None:
            base = base.where(ExtractedRecord.validation_status == validation_status)
            count_base = count_base.where(ExtractedRecord.validation_status == validation_status)

        total = db.execute(count_base).scalar_one()
        rows = db.execute(
            base.order_by(ExtractedRecord.document_id, ExtractedRecord.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(status_code=500, code="database_error", message="Could not query records.") from exc

    return RecordListResponse(
        items=[_to_response(record, filename, None) for record, filename in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )

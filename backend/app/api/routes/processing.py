"""Document processing routes: trigger, status, extracted content.

Step 7: processing now also creates structured records and runs validation
automatically; the status endpoint exposes the combined derived-data state
(records count + validation summary) from actual database values.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import DocumentStatus
from app.db import get_db
from app.exceptions import AppError
from app.models import ExtractedRecord, ValidationResult
from app.schemas.processing import (
    ContentSection,
    DocumentContentResponse,
    ExtractionStats,
    ProcessingStatusResponse,
    ValidationSummaryInfo,
)
from app.services import processing_service
from app.services.document_service import get_document
from app.services.document_storage import LocalFileStorage
from app.config import settings

router = APIRouter(prefix="/api/documents", tags=["processing"])

_storage = LocalFileStorage(settings.document_storage_path)


def _validation_summary(db: Session, document_id: int) -> ValidationSummaryInfo:
    counts = db.execute(
        select(ValidationResult.status, func.count())
        .where(ValidationResult.document_id == document_id)
        .group_by(ValidationResult.status)
    ).all()
    by_status = {status: int(count) for status, count in counts}
    return ValidationSummaryInfo(
        total_checks=int(sum(by_status.values())),
        passed=by_status.get("pass", 0),
        warnings=by_status.get("warning", 0),
        errors=by_status.get("error", 0),
        review_required=by_status.get("review_required", 0),
    )


def _records_count(db: Session, document_id: int) -> int:
    return int(
        db.execute(
            select(func.count()).select_from(ExtractedRecord).where(
                ExtractedRecord.document_id == document_id
            )
        ).scalar_one()
    )


def _status_response(db: Session, document) -> ProcessingStatusResponse:
    stats = processing_service.extraction_statistics(db, document.id)
    return ProcessingStatusResponse(
        document_id=document.id,
        status=document.status,
        processed_at=document.processed_at,
        extraction_status=document.extraction_status,
        extractor={"name": document.extractor_name, "version": document.extractor_version},
        statistics=ExtractionStats(**stats),
        error_message=document.error_message,
        validation_status=document.validation_status,
        records_extracted=_records_count(db, document.id),
        validation=_validation_summary(db, document.id),
    )


@router.post("/{document_id}/process", response_model=ProcessingStatusResponse, status_code=202)
def process_document_route(document_id: int, db: Session = Depends(get_db)) -> ProcessingStatusResponse:
    """Full derived-data workflow: extract → structure → validate (synchronous).

    202 = completed for this request. Failures surface honestly (422 with the
    real error; 503 when the database is unavailable).
    """
    document = processing_service.process_document(db, document_id, _storage)
    return _status_response(db, document)


@router.get("/{document_id}/processing-status", response_model=ProcessingStatusResponse)
def processing_status_route(document_id: int, db: Session = Depends(get_db)) -> ProcessingStatusResponse:
    """Combined processing + validation state, from actual database values."""
    return _status_response(db, get_document(db, document_id))


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
def document_content_route(document_id: int, db: Session = Depends(get_db)) -> DocumentContentResponse:
    """Normalized extracted content, structured by unit, source references kept.

    No AI-generated summaries — content is exactly what extraction produced.
    """
    from app.services.document_service import get_document

    document = get_document(db, document_id)
    if document.status != DocumentStatus.PROCESSED:
        raise AppError(
            status_code=409,
            code="not_processed",
            message="Document has not been processed yet (or processing failed).",
        )

    sections = [
        ContentSection(
            type=page.content_type,
            number=page.page_number,
            reference=page.section_reference,
            text=page.extracted_text,
            extraction_status=page.extraction_status,
            structured=page.structured_metadata,
            ocr=(page.structured_metadata or {}).get("ocr")
            if isinstance(page.structured_metadata, dict)
            else None,
        )
        for page in processing_service.iter_document_sections(db, document.id)
    ]
    return DocumentContentResponse(
        document_id=document.id,
        status=document.status,
        extraction_status=document.extraction_status,
        sections=sections,
    )

"""Document processing routes: trigger, status, extracted content."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants import DocumentStatus
from app.db import get_db
from app.exceptions import AppError
from app.schemas.processing import (
    ContentSection,
    DocumentContentResponse,
    ExtractionStats,
    ProcessingStatusResponse,
)
from app.services import processing_service
from app.services.document_service import get_document
from app.services.document_storage import LocalFileStorage
from app.config import settings

router = APIRouter(prefix="/api/documents", tags=["processing"])

_storage = LocalFileStorage(settings.document_storage_path)


@router.post("/{document_id}/process", response_model=ProcessingStatusResponse, status_code=202)
def process_document_route(document_id: int, db: Session = Depends(get_db)) -> ProcessingStatusResponse:
    """Run deterministic extraction for a stored document (synchronous prototype).

    Returns the final status. 202 signals "processing completed for this
    request"; failures surface as 422 with the real error message preserved.
    """
    document = processing_service.process_document(db, document_id, _storage)
    stats = processing_service.extraction_statistics(db, document.id)
    return ProcessingStatusResponse(
        document_id=document.id,
        status=document.status,
        processed_at=document.processed_at,
        extraction_status=document.extraction_status,
        extractor={"name": document.extractor_name, "version": document.extractor_version},
        statistics=ExtractionStats(**stats),
        error_message=document.error_message,
    )


@router.get("/{document_id}/processing-status", response_model=ProcessingStatusResponse)
def processing_status_route(document_id: int, db: Session = Depends(get_db)) -> ProcessingStatusResponse:
    """Current processing state, extractor info, statistics and error info."""
    document = get_document(db, document_id)
    stats = processing_service.extraction_statistics(db, document.id)
    return ProcessingStatusResponse(
        document_id=document.id,
        status=document.status,
        processed_at=document.processed_at,
        extraction_status=document.extraction_status,
        extractor={"name": document.extractor_name, "version": document.extractor_version},
        statistics=ExtractionStats(**stats),
        error_message=document.error_message,
    )


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
def document_content_route(document_id: int, db: Session = Depends(get_db)) -> DocumentContentResponse:
    """Normalized extracted content, structured by unit, source references kept.

    No AI-generated summaries — content is exactly what extraction produced.
    """
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
        )
        for page in processing_service.iter_document_sections(db, document.id)
    ]
    return DocumentContentResponse(
        document_id=document.id,
        status=document.status,
        extraction_status=document.extraction_status,
        sections=sections,
    )

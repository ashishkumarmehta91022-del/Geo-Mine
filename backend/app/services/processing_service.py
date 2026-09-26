"""Processing service: runs the deterministic extraction pipeline.

Transaction/state guarantees:
- `processing` is committed before extraction starts, so the state is visible.
- On extractor failure the document is marked `failed` with the real error
  preserved in `error_message` — never silently swallowed.
- On success, existing page rows are replaced and new rows inserted in one
  transaction together with the `processed` transition (no partial writes,
  no duplicate page records on re-processing).
"""

import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from io import BytesIO

from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import DocumentStatus, TextExtractionStatus
from app.config import settings
from app.exceptions import AppError, DatabaseUnavailableError, NotFoundError
from app.models import Document, DocumentPage
from app.processing.base import DocumentExtractor, ExtractionResult
from app.processing.registry import get_extractor
from app.services.document_service import get_document
from app.services.document_storage import DocumentStorage

logger = logging.getLogger(__name__)


class AlreadyProcessingError(AppError):
    status_code = 409
    code = "already_processing"
    message = "Document is already being processed."


class ProcessingFailedError(AppError):
    status_code = 422
    code = "processing_failed"
    message = "Document processing failed."


def _mark_failed(db: Session, document: Document, error: Exception | str) -> None:
    """Best-effort transition to `failed` with the real error preserved."""
    message = f"{error.__class__.__name__}: {error}" if isinstance(error, Exception) else str(error)
    document.status = DocumentStatus.FAILED
    document.error_message = message[:2000]
    document.processed_at = None
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not persist `failed` state for document %s", document.id)


def process_document(db: Session, document_id: int, storage: DocumentStorage) -> Document:
    """Run extraction for one document, synchronously (async-ready design)."""
    document = get_document(db, document_id)

    if document.status == DocumentStatus.PROCESSING:
        raise AlreadyProcessingError()

    if not storage.exists(document.storage_reference):
        raise NotFoundError("Stored file for this document is missing.")

    try:
        extractor = get_extractor(
            extension=document.storage_reference.rsplit(".", 1)[-1] if "." in document.storage_reference else None,
            document_type=document.document_type,
        )
    except LookupError as exc:
        raise AppError(
            status_code=422, code="no_extractor", message="No extractor supports this document type."
        ) from exc

    # State transition: processing (committed so the lifecycle is observable).
    document.status = DocumentStatus.PROCESSING
    document.error_message = None
    try:
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise DatabaseUnavailableError from exc

    # Extractors need a seekable stream; uploads are capped at
    # MAX_UPLOAD_SIZE_MB, so buffering the stored original is bounded.
    try:
        content = b"".join(storage.open(document.storage_reference))
    except NotFoundError:
        _mark_failed(db, document, "Stored file disappeared during processing.")
        raise
    except Exception as exc:  # noqa: BLE001
        _mark_failed(db, document, exc)
        raise ProcessingFailedError(message=f"Could not read stored file: {exc}") from exc

    try:
        extraction = extractor.extract(BytesIO(content))
    except Exception as exc:  # noqa: BLE001 — corrupted/unsupported content
        logger.warning("Extraction failed for document %s: %s", document.id, exc)
        _mark_failed(db, document, exc)
        raise ProcessingFailedError(message=f"Extraction failed: {exc}") from exc

    _persist_extraction(db, document, extraction, extractor)
    return document


def _persist_extraction(
    db: Session,
    document: Document,
    extraction: ExtractionResult,
    extractor: DocumentExtractor,
) -> None:
    """Replace page rows and finalize the `processed` state in one transaction."""
    extracted_at = datetime.now(timezone.utc)
    try:
        # Replacement logic: old rows go, new rows come in, atomically.
        db.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
        for section in extraction.sections:
            db.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=section.index,
                    content_type=section.content_type,
                    section_reference=section.section_reference,
                    extracted_text=section.text,
                    extraction_status=section.extraction_status,
                    processing_status=section.extraction_status,  # legacy column, kept in sync
                    extractor_name=extraction.extractor_name,
                    extractor_version=extraction.extractor_version,
                    extracted_at=extracted_at,
                    error_message=section.error_message,
                    structured_metadata=section.structured_metadata,
                )
            )
        document.status = DocumentStatus.PROCESSED
        document.processed_at = extracted_at
        document.extraction_status = extraction.aggregate_text_status
        document.extractor_name = extraction.extractor_name
        document.extractor_version = extraction.extractor_version
        document.error_message = None
        db.commit()
    except OperationalError as exc:
        db.rollback()
        logger.exception("Database unavailable while persisting extraction for document %s", document.id)
        _mark_failed_quietly_if_possible(db, document.id)
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Persisting extraction failed for document %s", document.id)
        _mark_failed(db, document, exc)
        raise ProcessingFailedError(message="Extraction succeeded but results could not be saved.") from exc


def _mark_failed_quietly_if_possible(db: Session, document_id: int) -> None:
    """After a rollback, try to at least leave an honest `failed` status."""
    try:
        document = db.get(Document, document_id)
        if document is not None:
            document.status = DocumentStatus.FAILED
            document.error_message = "Database error while saving extraction results."
            db.commit()
    except SQLAlchemyError:
        db.rollback()


def extraction_statistics(db: Session, document_id: int) -> dict[str, int]:
    """Per-status counts of the document's extraction units."""
    rows = db.execute(
        select(DocumentPage.extraction_status, func.count())
        .where(DocumentPage.document_id == document_id)
        .group_by(DocumentPage.extraction_status)
    ).all()
    stats: dict[str, int] = {status.value: 0 for status in TextExtractionStatus}
    for status, count in rows:
        stats[status] = int(count)
    stats["total_units"] = int(sum(count for _, count in rows))
    return stats


def iter_document_sections(db: Session, document_id: int) -> Iterable[DocumentPage]:
    """Yield the document's extraction units in source order."""
    return db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    ).scalars()

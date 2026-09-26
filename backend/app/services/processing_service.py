"""Processing service: extraction + structured records + automatic validation.

Transaction/state guarantees (Step 7):
- `processing` is committed before extraction starts, so state is observable.
- On extractor failure the document is marked `failed` with the real error —
  never silently swallowed.
- On success, ONE transaction replaces page rows and structured records,
  then embeds validation (load → compute → write) and sets the document's
  `processed` + `validation_status` together. No partial derived data,
  no duplicate rows on re-processing. Original files are never touched.
"""

import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from io import BytesIO

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import DocumentStatus, TextExtractionStatus, ValidationStatus
from app.config import settings
from app.exceptions import AppError, DatabaseUnavailableError, NotFoundError
from app.models import Document, DocumentPage, ExtractedRecord, KnowledgeIndex
from app.processing.base import DocumentExtractor, ExtractionResult
from app.processing.registry import get_extractor
from app.knowledge.units import units_from_rows
from app.models import ValidationResult
from app.services import validation_service
from app.services.document_service import get_document
from app.services.document_storage import DocumentStorage
from app.structuring.builder import StructuredRecordBuilder
from app.structuring.config import demo_config as demo_structuring_config
from app.knowledge.units import units_from_rows

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

    # Structured records are built deterministically before any DB writes;
    # a builder bug must not leave half-created derived data.
    from app.structuring.builder import RecordDraft  # noqa: F401 — typing only

    try:
        drafts = StructuredRecordBuilder(demo_structuring_config()).build(extraction, document.id)
    except Exception as exc:  # noqa: BLE001 — structuring failure is honest
        logger.exception("Structuring failed for document %s", document.id)
        _mark_failed(db, document, exc)
        raise ProcessingFailedError(message=f"Structuring failed: {exc}") from exc

    _persist_derived_data(db, document, extraction, drafts, extractor)
    return document


def _persist_derived_data(
    db: Session,
    document: Document,
    extraction: ExtractionResult,
    drafts,
    extractor: DocumentExtractor,
) -> None:
    """Replace derived data (pages + records + validation) in ONE transaction.

    Raw extraction (document_pages) is preserved as-is; structured records
    and validation results are derived layers, replaced idempotently.
    """
    extracted_at = datetime.now(timezone.utc)
    try:
        # --- raw extraction layer (replaced, as in Steps 4–5) ---
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

        # --- structured layer (Step 7; idempotent delete-replace) ---
        db.execute(delete(ExtractedRecord).where(ExtractedRecord.document_id == document.id))
        for draft in drafts:
            db.add(
                ExtractedRecord(
                    document_id=document.id,
                    entity_name=draft.entity_name,
                    metric_name=draft.metric_name,
                    metric_value=draft.numeric_value,
                    unit=draft.unit,
                    reporting_period=draft.reporting_period,
                    source_reference=draft.source_reference,
                    confidence=draft.confidence,
                    validation_status="pending",
                    value_raw=draft.raw_value,
                    normalized_value=draft.normalized_value,
                    extraction_method=draft.extraction_method,
                    record_metadata={
                        **draft.record_metadata,
                        "review_required": draft.review_required,
                        "page_number": draft.page_number,
                    },
                )
            )

        # Flush so validation/indexing can see this document's fresh rows
        # before the commit — still inside the same transaction.
        db.flush()

        # --- automatic validation (Step 6 engine reused, no second engine) ---
        scope = validation_service.load_validation_scope(db, document.id)
        outcomes = validation_service.compute_outcomes(scope)
        validation_service.write_outcomes(db, document, outcomes)  # no commit inside
        worst = validation_service._worst_status(outcomes)

        # --- retrieval index refresh (Step 8; delete-replace, same tx) ---
        # Re-read rows now that pages/records/validations are final in-session.
        _, pages, records, validations = _load_rows_for_index(db, document.id)
        db.execute(delete(KnowledgeIndex).where(KnowledgeIndex.document_id == document.id))
        for draft in units_from_rows(pages, records, validations, document.filename):
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

        # --- finalize document state: processing ≠ validation ---
        document.status = DocumentStatus.PROCESSED
        document.processed_at = extracted_at
        document.extraction_status = extraction.aggregate_text_status
        document.extractor_name = extraction.extractor_name
        document.extractor_version = extraction.extractor_version
        document.error_message = None
        # Validation problems must stay visible on the document itself.
        document.validation_status = worst
        db.commit()
    except OperationalError as exc:
        db.rollback()
        logger.exception("Database unavailable while persisting derived data for document %s", document.id)
        _mark_failed_quietly_if_possible(db, document.id)
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Persisting derived data failed for document %s", document.id)
        _mark_failed(db, document, exc)
        raise ProcessingFailedError(message="Extraction succeeded but derived data could not be saved.") from exc


def _load_rows_for_index(db: Session, document_id: int) -> tuple[Document, list, list, list]:
    """In-session rows for index building (used by _persist_derived_data)."""
    document = db.get(Document, document_id)
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

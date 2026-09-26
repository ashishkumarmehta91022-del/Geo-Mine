"""Validation service: bridges the DB-free engine to extracted/OCR data.

Guarantees:
- Original extracted values are NEVER modified — results only describe.
- Deterministic: same data + config ⇒ same results (rule order is fixed).
- Idempotent per document: a run replaces that document's previous results
  in one transaction (re-running resets that document's review state).
- Honest 503 semantics when PostgreSQL is unavailable.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import ReviewStatus, ValidationStatus
from app.exceptions import AppError, DatabaseUnavailableError
from app.models import AuditLog, Document, DocumentPage, ExtractedRecord, ValidationResult
from app.validation.config import ValidationConfig, demo_config
from app.validation.models import ValueCandidate
from app.validation.rules import (
    CrossDocumentConsistencyRule,
    DuplicateRule,
    OCRConfidenceRule,
    RequiredFieldRule,
)

logger = logging.getLogger(__name__)

# Rules that need candidates from OTHER documents as well (cross-document scope).
_CROSS_DOCUMENT_RULES = (DuplicateRule, CrossDocumentConsistencyRule)


def _record_candidate(record: ExtractedRecord, filename: str | None) -> ValueCandidate:
    """ValueCandidate from an extracted_records row (verbatim values)."""
    return ValueCandidate(
        document_id=record.document_id,
        metric_name=record.metric_name,
        raw_value=str(record.metric_value) if record.metric_value is not None else None,
        numeric_value=record.metric_value,
        record_id=record.id,
        page_id=record.page_id,
        entity_name=record.entity_name,
        unit=record.unit,
        reporting_period=record.reporting_period,
        source_reference=record.source_reference,
        confidence=float(record.confidence) if record.confidence is not None else None,
        document_filename=filename,
    )


def _ocr_candidate(page: DocumentPage, filename: str | None) -> ValueCandidate | None:
    """ValueCandidate for an OCR-processed page (feeds the OCR rule only)."""
    meta = page.structured_metadata or {}
    ocr = meta.get("ocr") if isinstance(meta, dict) else None
    if not isinstance(ocr, dict):
        return None
    confidence_raw = ocr.get("confidence")
    try:
        confidence = float(confidence_raw) if confidence_raw is not None else None
    except (TypeError, ValueError):
        confidence = None
    review_required = bool(ocr.get("review_required"))
    if confidence is None and not review_required:
        return None  # nothing OCR-related to validate on this page
    return ValueCandidate(
        document_id=page.document_id,
        metric_name="ocr_page",
        raw_value=page.extracted_text,  # verbatim OCR text for the reviewer
        page_id=page.id,
        source_reference=page.section_reference,
        confidence=confidence,
        review_required=review_required,
        ocr_metadata=ocr,
        document_filename=filename,
    )


def _persist_outcomes(
    db: Session,
    document: Document,
    outcomes,
    config: ValidationConfig,
) -> int:
    """Replace the document's previous results and write the new ones atomically."""
    extracted_at = datetime.now(timezone.utc)
    try:
        db.execute(delete(ValidationResult).where(ValidationResult.document_id == document.id))

        for outcome in outcomes:
            candidate = outcome.candidate
            db.add(
                ValidationResult(
                    document_id=candidate.document_id,
                    page_id=candidate.page_id,
                    extracted_record_id=candidate.record_id,
                    source_reference=candidate.source_reference,
                    rule_code=outcome.rule_code,
                    status=outcome.status,
                    severity=outcome.severity,
                    message=outcome.message,
                    original_value=candidate.raw_value,
                    expected_value=outcome.expected,
                    details={
                        **outcome.details,
                        "candidate": {
                            "document_id": candidate.document_id,
                            "record_id": candidate.record_id,
                            "metric_name": candidate.metric_name,
                            "entity_name": candidate.entity_name,
                            "reporting_period": candidate.reporting_period,
                            "confidence": candidate.confidence,
                        },
                    },
                )
            )

        # Record-level rollup: record status reflects its worst outcome,
        # but the record's VALUE is untouched.
        record_ids = {
            outcome.candidate.record_id for outcome in outcomes if outcome.candidate.record_id
        }
        if record_ids:
            rows = db.execute(
                select(ExtractedRecord).where(ExtractedRecord.id.in_(record_ids))
            ).scalars().all()
            outcome_by_record: dict[int, list] = {}
            for outcome in outcomes:
                if outcome.candidate.record_id:
                    outcome_by_record.setdefault(outcome.candidate.record_id, []).append(outcome)
            for record in rows:
                outcomes_for_record = outcome_by_record.get(record.id, [])
                statuses = {o.status for o in outcomes_for_record}
                if ValidationStatus.ERROR in statuses:
                    record.validation_status = "failed"
                elif statuses & {ValidationStatus.WARNING, ValidationStatus.REVIEW_REQUIRED}:
                    record.validation_status = "warning"
                else:
                    record.validation_status = "valid"

        db.add(
            AuditLog(
                action="validation.run",
                entity_type="document",
                entity_id=document.id,
                details={"outcomes": len(outcomes), "config": "demo"},
            )
        )
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Validation persistence failed for document %s", document.id)
        raise AppError(
            status_code=500, code="validation_persistence_failed",
            message="Validation ran but results could not be saved.",
        ) from exc
    return len(outcomes)


def run_document_validation(
    db: Session, document_id: int, config: ValidationConfig | None = None
) -> dict[str, Any]:
    """Run the full rule set for one document. Returns a summary dict."""
    config = config or demo_config()

    try:
        document = db.get(Document, document_id)
        if document is None:
            raise AppError(status_code=404, code="document_not_found", message="Document not found.")

        # This document's record-level candidates.
        records = db.execute(
            select(ExtractedRecord).where(ExtractedRecord.document_id == document.id).order_by(ExtractedRecord.id)
        ).scalars().all()
        record_candidates = [_record_candidate(r, document.filename) for r in records]

        # OCR-page candidates (only pages the OCR layer flagged/produced).
        pages = db.execute(
            select(DocumentPage)
            .where(
                DocumentPage.document_id == document.id,
                DocumentPage.extraction_status.in_(["ocr_extracted", "no_text", "failed"]),
            )
            .order_by(DocumentPage.page_number)
        ).scalars().all()
        ocr_candidates = [c for c in (_ocr_candidate(p, document.filename) for p in pages) if c]

        # Cross-document scope: record candidates from ALL documents.
        all_rows = db.execute(
            select(ExtractedRecord, Document.filename)
            .join(Document, ExtractedRecord.document_id == Document.id)
            .order_by(ExtractedRecord.id)
        ).all()
        all_candidates = [_record_candidate(r, filename) for r, filename in all_rows]
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not load data for validation."
        ) from exc

    # Fixed rule order ⇒ deterministic outcome order.
    rule_instances = (
        RequiredFieldRule(),
        NumericRule(),
        RangeRule(),
        DateRule(),
        OCRConfidenceRule(),
        DuplicateRule(),
        CrossDocumentConsistencyRule(),
    )
    outcomes: list = []
    for rule in rule_instances:
        if isinstance(rule, _CROSS_DOCUMENT_RULES):
            outcomes.extend(rule.validate(all_candidates, config))
        else:
            outcomes.extend(rule.validate(record_candidates, config))
    # OCR-page candidates flow through the OCR rule only.
    outcomes.extend(OCRConfidenceRule().validate(ocr_candidates, config))

    created = _persist_outcomes(db, document, outcomes, config)
    summary = {
        "document_id": document.id,
        "total_checks": len(outcomes),
        "passed": sum(1 for o in outcomes if o.status == ValidationStatus.PASS),
        "warnings": sum(1 for o in outcomes if o.status == ValidationStatus.WARNING),
        "errors": sum(1 for o in outcomes if o.status == ValidationStatus.ERROR),
        "review_required": sum(1 for o in outcomes if o.status == ValidationStatus.REVIEW_REQUIRED),
        "results_created": created,
        "ran_at": extracted_at.isoformat(),
    }
    return summary


def get_document_validation(db: Session, document_id: int) -> dict[str, Any]:
    """Stored results + summary for one document (404 when document missing)."""
    try:
        document = db.get(Document, document_id)
        if document is None:
            raise AppError(status_code=404, code="document_not_found", message="Document not found.")
        rows = db.execute(
            select(ValidationResult)
            .where(ValidationResult.document_id == document_id)
            .order_by(ValidationResult.id)
        ).scalars().all()
        counts = db.execute(
            select(ValidationResult.status, func.count())
            .where(ValidationResult.document_id == document_id)
            .group_by(ValidationResult.status)
        ).all()
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not load validation results."
        ) from exc

    by_status = {status: int(count) for status, count in counts}
    return {
        "document": document,
        "rows": list(rows),
        "summary": {
            "total_checks": int(sum(by_status.values())),
            "passed": by_status.get(ValidationStatus.PASS, 0),
            "warnings": by_status.get(ValidationStatus.WARNING, 0),
            "errors": by_status.get(ValidationStatus.ERROR, 0),
            "review_required": by_status.get(ValidationStatus.REVIEW_REQUIRED, 0),
        },
    }


def list_review_queue(
    db: Session, review_status: str = ReviewStatus.OPEN, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    """Unresolved (or filtered) validation items needing human attention."""
    try:
        base = select(ValidationResult).where(ValidationResult.review_status == review_status)
        total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        rows = db.execute(
            base.order_by(ValidationResult.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).scalars().all()

        filenames: dict[int, str] = {}
        record_rows: dict[int, ExtractedRecord] = {}
        document_ids = {row.document_id for row in rows}
        record_ids = {row.extracted_record_id for row in rows if row.extracted_record_id}
        if document_ids:
            for doc_id, filename in db.execute(
                select(Document.id, Document.filename).where(Document.id.in_(document_ids))
            ).all():
                filenames[doc_id] = filename
        if record_ids:
            for record in db.execute(
                select(ExtractedRecord).where(ExtractedRecord.id.in_(record_ids))
            ).scalars().all():
                record_rows[record.id] = record
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not load the review queue."
        ) from exc

    return {"rows": list(rows), "total": int(total), "filenames": filenames, "records": record_rows}


def set_review_status(
    db: Session, validation_id: int, review_status: str, notes: str | None
) -> ValidationResult:
    """Reviewer decision on one validation item. Never touches source values."""
    if review_status not in ReviewStatus.values():
        raise AppError(
            status_code=422, code="invalid_review_status",
            message=f"review_status must be one of {sorted(ReviewStatus.values())}.",
        )
    try:
        result = db.get(ValidationResult, validation_id)
        if result is None:
            raise AppError(status_code=404, code="validation_not_found", message="Validation result not found.")
        result.review_status = review_status
        result.review_notes = notes
        result.reviewed_at = datetime.now(timezone.utc)
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppError(
            status_code=500, code="database_error", message="Could not update the review status."
        ) from exc
    return result

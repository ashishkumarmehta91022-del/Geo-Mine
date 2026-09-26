"""Validation service: bridges the DB-free engine to extracted/OCR data.

Guarantees:
- Original extracted values are NEVER modified — results only describe.
- Deterministic: same data + config ⇒ same results (fixed rule order).
- Idempotent per document: a run replaces that document's previous results.
- Composable (Step 7): load_validation_scope → compute_outcomes →
  write_outcomes lets document processing embed validation in its own
  transaction; run_document_validation remains the standalone entry point.
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
    DateRule,
    DuplicateRule,
    NumericRule,
    OCRConfidenceRule,
    RangeRule,
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


# ---------------------------------------------------------------------------
# Composable pipeline (Step 7): load → compute → write (caller commits)
# ---------------------------------------------------------------------------


def load_validation_scope(db: Session, document_id: int) -> dict:
    """Load candidates for validation (this document + cross-document scope).

    No writes, no commit. 404 for unknown documents; DB errors translated.
    """
    try:
        document = db.get(Document, document_id)
        if document is None:
            raise AppError(status_code=404, code="document_not_found", message="Document not found.")

        records = db.execute(
            select(ExtractedRecord)
            .where(ExtractedRecord.document_id == document_id)
            .order_by(ExtractedRecord.id)
        ).scalars().all()
        record_candidates = [_record_candidate(r, document.filename) for r in records]

        pages = db.execute(
            select(DocumentPage)
            .where(
                DocumentPage.document_id == document_id,
                DocumentPage.extraction_status.in_(["ocr_extracted", "no_text", "failed"]),
            )
            .order_by(DocumentPage.page_number)
        ).scalars().all()
        ocr_candidates = [c for c in (_ocr_candidate(p, document.filename) for p in pages) if c]

        all_rows = db.execute(
            select(ExtractedRecord, Document.filename)
            .join(Document, ExtractedRecord.document_id == Document.id)
            .order_by(ExtractedRecord.id)
        ).all()
        all_candidates = [_record_candidate(r, filename) for r, filename in all_rows]
    except AppError:
        raise
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not load data for validation."
        ) from exc

    return {
        "document": document,
        "record_candidates": record_candidates,
        "ocr_candidates": ocr_candidates,
        "all_candidates": all_candidates,
    }


def compute_outcomes(scope: dict, config: ValidationConfig | None = None) -> list:
    """Scope → RuleOutcomes in fixed rule order (deterministic, no DB access)."""
    config = config or demo_config()
    # Fixed order ⇒ deterministic outcome order. Cross-document rules see
    # every candidate; the others only this document's records.
    ordered = (
        RequiredFieldRule(),
        NumericRule(),
        RangeRule(),
        DateRule(),
        OCRConfidenceRule(),
        DuplicateRule(),
        CrossDocumentConsistencyRule(),
    )
    outcomes: list = []
    for rule in ordered:
        if isinstance(rule, _CROSS_DOCUMENT_RULES):
            outcomes.extend(rule.validate(scope["all_candidates"], config))
        else:
            outcomes.extend(rule.validate(scope["record_candidates"], config))
    # OCR-page candidates flow through the OCR rule only.
    outcomes.extend(OCRConfidenceRule().validate(scope["ocr_candidates"], config))
    return outcomes


def _worst_status(outcomes) -> str | None:
    """Document-level rollup: error > review_required > warning > pass."""
    statuses = {o.status for o in outcomes}
    if ValidationStatus.ERROR in statuses:
        return ValidationStatus.ERROR
    if ValidationStatus.REVIEW_REQUIRED in statuses:
        return ValidationStatus.REVIEW_REQUIRED
    if ValidationStatus.WARNING in statuses:
        return ValidationStatus.WARNING
    if statuses:
        return ValidationStatus.PASS
    return None


def write_outcomes(db: Session, document: Document, outcomes) -> int:
    """Replace the document's previous results and write the new ones.

    NO commit — the caller owns the transaction (Step 7: processing embeds
    validation in its own delete-replace transaction). Record-level rollup
    updates validation_status on records; values are never touched.
    """
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
                statuses = {o.status for o in outcome_by_record.get(record.id, [])}
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
    except OperationalError as exc:
        db.rollback()
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Validation persistence failed for document %s", document.id)
        raise AppError(
            status_code=500,
            code="validation_persistence_failed",
            message="Validation ran but results could not be saved.",
        ) from exc
    return len(outcomes)


# ---------------------------------------------------------------------------
# Standalone entry points (Step 6 API contract preserved)
# ---------------------------------------------------------------------------


def run_document_validation(
    db: Session, document_id: int, config: ValidationConfig | None = None
) -> dict[str, Any]:
    """Run the full rule set for one document. Returns a summary dict."""
    scope = load_validation_scope(db, document_id)
    outcomes = compute_outcomes(scope, config)
    created = write_outcomes(db, scope["document"], outcomes)
    db.commit()
    return {
        "document_id": scope["document"].id,
        "total_checks": len(outcomes),
        "passed": sum(1 for o in outcomes if o.status == ValidationStatus.PASS),
        "warnings": sum(1 for o in outcomes if o.status == ValidationStatus.WARNING),
        "errors": sum(1 for o in outcomes if o.status == ValidationStatus.ERROR),
        "review_required": sum(1 for o in outcomes if o.status == ValidationStatus.REVIEW_REQUIRED),
        "results_created": created,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


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
            status_code=422,
            code="invalid_review_status",
            message=f"review_status must be one of {sorted(ReviewStatus.values())}.",
        )
    try:
        result = db.get(ValidationResult, validation_id)
        if result is None:
            raise AppError(
                status_code=404, code="validation_not_found", message="Validation result not found."
            )
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

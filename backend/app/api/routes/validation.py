"""Validation routes — thin wrappers over validation_service.

NOTE: static paths (/review-queue) are registered BEFORE /{document_id} so
FastAPI does not try to parse "review-queue" as an integer id.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.constants import ReviewStatus
from app.db import get_db
from app.schemas.validation import (
    ReviewQueueResponse,
    ValidationDocumentResponse,
    ValidationItem,
    ValidationReviewResponse,
    ValidationReviewUpdate,
    ValidationRunResponse,
)
from app.services import validation_service

router = APIRouter(prefix="/api/validation", tags=["validation"])


def _to_item(row, filename: str | None, confidence: float | None) -> ValidationItem:
    return ValidationItem(
        id=row.id,
        document_id=row.document_id,
        document_filename=filename,
        extracted_record_id=row.extracted_record_id,
        page_id=row.page_id,
        source_reference=row.source_reference,
        rule_code=row.rule_code,
        status=row.status,
        severity=row.severity,
        message=row.message,
        original_value=row.original_value,
        expected_value=row.expected_value,
        details=row.details,
        review_status=row.review_status,
        review_notes=row.review_notes,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
        confidence=confidence,
    )


@router.post("/run/{document_id}", response_model=ValidationRunResponse, status_code=200)
def run_validation_route(document_id: int, db: Session = Depends(get_db)) -> ValidationRunResponse:
    """Run the deterministic rule set over one document's extracted/OCR data."""
    summary = validation_service.run_document_validation(db, document_id)
    return ValidationRunResponse(**summary)


@router.get("/review-queue", response_model=ReviewQueueResponse)
def review_queue_route(
    review_status: str = Query(default=ReviewStatus.OPEN),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    """Validation items needing (or having received) human review."""
    data = validation_service.list_review_queue(db, review_status, page, page_size)
    items = []
    for row in data["rows"]:
        record = data["records"].get(row.extracted_record_id) if row.extracted_record_id else None
        confidence = float(record.confidence) if record and record.confidence is not None else None
        if confidence is None:
            # Page-level OCR results have no linked record; their confidence
            # lives in the persisted outcome details (provenance-complete).
            details = row.details if isinstance(row.details, dict) else {}
            candidate_details = details.get("candidate") if isinstance(details.get("candidate"), dict) else {}
            raw_confidence = candidate_details.get("confidence")
            if raw_confidence is not None:
                confidence = float(raw_confidence)
        items.append(_to_item(row, data["filenames"].get(row.document_id), confidence))
    return ReviewQueueResponse(
        page=page,
        page_size=page_size,
        total=data["total"],
        items=items,
    )


@router.get("/{document_id}", response_model=ValidationDocumentResponse)
def get_validation_route(document_id: int, db: Session = Depends(get_db)) -> ValidationDocumentResponse:
    """Stored validation results + summary for one document."""
    data = validation_service.get_document_validation(db, document_id)
    return ValidationDocumentResponse(
        document_id=document_id,
        summary=data["summary"],
        items=[_to_item(row, data["document"].filename, None) for row in data["rows"]],
    )


@router.patch("/{validation_id}", response_model=ValidationReviewResponse)
def update_review_route(
    validation_id: int, update: ValidationReviewUpdate, db: Session = Depends(get_db)
) -> ValidationReviewResponse:
    """Reviewer decision (open / in_review / resolved / rejected) + notes.

    This NEVER modifies the original extracted value — only the review state.
    """
    result = validation_service.set_review_status(
        db, validation_id, update.review_status, update.review_notes
    )
    return ValidationReviewResponse(
        id=result.id,
        review_status=result.review_status,
        review_notes=result.review_notes,
        reviewed_at=result.reviewed_at,
    )

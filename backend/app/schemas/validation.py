"""Validation API request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ValidationReviewUpdate(BaseModel):
    review_status: str
    review_notes: str | None = None


class ValidationReviewResponse(BaseModel):
    id: int
    review_status: str
    review_notes: str | None
    reviewed_at: datetime | None


class ValidationItem(BaseModel):
    id: int
    document_id: int
    document_filename: str | None = None
    extracted_record_id: int | None
    page_id: int | None
    source_reference: str | None
    rule_code: str
    status: str
    severity: str
    message: str | None
    original_value: str | None
    expected_value: str | None
    details: dict[str, Any] | None
    review_status: str
    review_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime
    # Convenience mirror of the record's confidence for the review queue.
    confidence: float | None = None


class ValidationSummary(BaseModel):
    total_checks: int
    passed: int
    warnings: int
    errors: int
    review_required: int


class ValidationRunResponse(BaseModel):
    document_id: int
    total_checks: int
    passed: int
    warnings: int
    errors: int
    review_required: int
    results_created: int
    ran_at: str


class ValidationDocumentResponse(BaseModel):
    document_id: int
    summary: ValidationSummary
    items: list[ValidationItem]


class ReviewQueueResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ValidationItem]

"""Validation result model — rule outcomes with full provenance.

Extended in Step 6 (migration 0003): page/document-level checks, severity,
review workflow. Extracted values are NEVER modified by validation — a
result only describes and flags.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.extracted_record import ExtractedRecord


class ValidationResult(Base):
    """One deterministic validation outcome, traceable to its source."""

    __tablename__ = "validation_results"
    __table_args__ = (
        Index("ix_validation_results_document_id", "document_id"),
        Index("ix_validation_results_status", "status"),
        Index("ix_validation_results_severity", "severity"),
        Index("ix_validation_results_review_status", "review_status"),
        Index("ix_validation_results_rule_code", "rule_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- provenance (at least one source link always present) ---
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_pages.id", ondelete="SET NULL"), nullable=True
    )
    # Nullable since Step 6: OCR/page-level checks need no record.
    extracted_record_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("extracted_records.id", ondelete="CASCADE"), nullable=True
    )
    # Free-text source pointer, e.g. "page 2", "sheet Production, row 5".
    source_reference: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # --- the rule outcome ---
    # e.g. REQUIRED_FIELD_MISSING | NUMERIC_FORMAT | RANGE_BOUNDARY | OCR_LOW_CONFIDENCE.
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    # pass | warning | error | review_required (ValidationStatus).
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # info | warning | error | critical (ValidationSeverity — rule-configured).
    severity: Mapped[str] = mapped_column(String(16), nullable=False, server_default="warning")
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Original value preserved verbatim — never overwritten by validation.
    original_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    expected_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # Rule parameters + evidence (thresholds, both conflict sides, OCR boxes...).
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # --- human review workflow ---
    # open | in_review | resolved | rejected (ReviewStatus).
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    extracted_record: Mapped[Optional[ExtractedRecord]] = relationship(
        back_populates="validation_results"
    )

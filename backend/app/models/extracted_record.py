"""Extracted record model.

Structured geological/mining/production values extracted from documents
(extraction logic itself arrives in a later step).
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.document import Document, DocumentPage


class ExtractedRecord(TimestampMixin, Base):
    """A single structured value extracted from a document (or one of its pages)."""

    __tablename__ = "extracted_records"
    __table_args__ = (
        Index("ix_extracted_records_document_id", "document_id"),
        Index("ix_extracted_records_entity_name", "entity_name"),
        Index("ix_extracted_records_metric_name", "metric_name"),
        Index("ix_extracted_records_reporting_period", "reporting_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable: a record may span pages or come from document-level metadata.
    page_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_pages.id", ondelete="SET NULL"), nullable=True
    )
    # e.g. coal_production | borehole | grade | reserve | dispatch.
    record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(256), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # e.g. "2025-26" (financial year) or "2025-04" (month).
    reporting_period: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Where in the source this came from, e.g. "page 12, table 3".
    source_reference: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Extraction confidence in [0, 1].
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    # Lifecycle: pending -> valid | warning | failed.
    validation_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending", index=True
    )

    document: Mapped[Document] = relationship(back_populates="extracted_records")
    page: Mapped[Optional[DocumentPage]] = relationship()
    validation_results: Mapped[list["ValidationResult"]] = relationship(  # noqa: F821
        back_populates="extracted_record", cascade="all, delete-orphan"
    )
    # NOTE: Step 6 made this relationship Optional (record-level checks only).
    # Page/OCR-level validation results exist without an extracted record.

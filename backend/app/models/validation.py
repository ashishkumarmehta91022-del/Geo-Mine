"""Validation result model.

Outcomes of rule-based checks against extracted records (the validation
engine itself arrives in a later step).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.extracted_record import ExtractedRecord


class ValidationResult(Base):
    """A single validation check outcome for an extracted record."""

    __tablename__ = "validation_results"
    __table_args__ = (
        Index("ix_validation_results_extracted_record_id", "extracted_record_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    extracted_record_id: Mapped[int] = mapped_column(
        ForeignKey("extracted_records.id", ondelete="CASCADE"), nullable=False
    )
    # e.g. range_check | unit_check | cross_reference | completeness.
    validation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # passed | warning | failed.
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    actual_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    extracted_record: Mapped[ExtractedRecord] = relationship(back_populates="validation_results")

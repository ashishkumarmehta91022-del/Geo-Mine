"""Knowledge index model — the retrieval layer over authoritative sources.

NOT a source of truth: every row points back to documents / document_pages /
extracted_records / validation_results. Document deletion cascades here
(no orphaned search entries).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeIndex(Base):
    """One searchable retrieval unit (page, structured record, or validation)."""

    __tablename__ = "knowledge_index"
    __table_args__ = (
        Index("ix_knowledge_index_document_id", "document_id"),
        Index("ix_knowledge_index_unit_type", "unit_type"),
        Index("ix_knowledge_index_entity", "entity"),
        Index("ix_knowledge_index_metric", "metric"),
        Index("ix_knowledge_index_validation_status", "validation_status"),
        Index("ix_knowledge_index_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    record_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    validation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # page | record | validation (constants.RetrievalUnitType).
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    entity: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    metric: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reporting_period: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    extraction_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    validation_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    ocr_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    # PostgreSQL-native full-text vector, maintained by the knowledge service.
    search_vector = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

"""Document and document page models.

documents       — an uploaded geological/mining/production report
document_pages  — per-page extracted text (OCR/text layers come in later steps)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Document(TimestampMixin, Base):
    """A report document ingested into the platform."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False, server_default="upload")
    # Storage reference: local file path or future object-store URI.
    storage_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Lifecycle: uploaded -> processing -> processed | failed.
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="uploaded")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number"
    )
    extracted_records: Mapped[list["ExtractedRecord"]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentPage(Base):
    """One page of a document, with the text extracted from it."""

    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
        Index("ix_document_pages_document_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(nullable=False)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Lifecycle: pending -> processing -> extracted | failed.
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="pages")

"""Document and document page models.

documents       — an uploaded geological/mining/production report
document_pages  — one extraction unit each: PDF page, DOCX section,
                  spreadsheet sheet, or image (Step 4; formerly PDF-only)
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
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
    # Lifecycle: uploaded -> processing -> processed | failed (constants.DocumentStatus).
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="uploaded")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Step 4: extraction provenance (null until processed) ---
    # Aggregate text outcome across pages, e.g. "extracted" | "no_text" | "mixed" | "ocr_required".
    extraction_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    extractor_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    extractor_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Preserved failure information from the last processing attempt (null when OK).
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentPage.page_number",
    )
    extracted_records: Mapped[list["ExtractedRecord"]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentPage(Base):
    """One extraction unit of a document.

    For PDFs this is a page; for spreadsheets a sheet (one row per sheet,
    rows/cells preserved in structured_metadata); for DOCX a section
    (paragraph/table reference); for images the image itself.
    """

    __tablename__ = "document_pages"
    __table_args__ = (
        # Idempotent re-processing: one row per (document, unit index).
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
        Index("ix_document_pages_document_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    # 1-based index within the document (PDF page, sheet index, section index).
    page_number: Mapped[int] = mapped_column(nullable=False)
    # Unit kind: page | sheet | image (constants.PageContentType).
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="page")
    # Human-readable source reference, e.g. "sheet Production", "section 3, table 1".
    section_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Per-unit text outcome (constants.TextExtractionStatus).
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    # Legacy Step 2 column, kept in sync for existing queries.
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    # --- extraction provenance (Step 4) ---
    extractor_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    extractor_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Type-preserving structured data (sheet rows, table structures, image metadata).
    structured_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="pages")

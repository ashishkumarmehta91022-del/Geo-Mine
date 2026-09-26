"""Processing status and extracted-content response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ExtractionStats(BaseModel):
    extracted: int = 0
    no_text: int = 0
    ocr_required: int = 0
    failed: int = 0
    total_units: int = 0


class ProcessingStatusResponse(BaseModel):
    document_id: int
    status: str
    processed_at: datetime | None
    extraction_status: str | None
    extractor: dict[str, str | None]
    statistics: ExtractionStats
    error_message: str | None


class ContentSection(BaseModel):
    type: str  # page | sheet | image
    number: int
    reference: str | None
    text: str | None
    extraction_status: str
    structured: dict[str, Any] | None


class DocumentContentResponse(BaseModel):
    document_id: int
    status: str
    extraction_status: str | None
    sections: list[ContentSection]

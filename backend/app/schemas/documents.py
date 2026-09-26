"""Document API request/response schemas."""

from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    filename: str
    document_type: str
    source: str
    status: str
    storage_reference: str
    uploaded_at: datetime
    # Preserved processing error (null unless status == "failed").
    error_message: str | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    page: int
    page_size: int
    total: int

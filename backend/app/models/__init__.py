"""ORM models. Importing this package registers every model on Base.metadata."""

from app.models.base import Base, TimestampMixin
from app.models.document import Document, DocumentPage
from app.models.extracted_record import ExtractedRecord
from app.models.validation import ValidationResult
from app.models.audit import AuditLog
from app.models.knowledge import KnowledgeIndex

__all__ = [
    "Base",
    "TimestampMixin",
    "Document",
    "DocumentPage",
    "ExtractedRecord",
    "ValidationResult",
    "AuditLog",
    "KnowledgeIndex",
]

"""Audit log model.

Append-only traceability of platform actions. References other entities
through (entity_type, entity_id) columns — deliberately simple, no
polymorphic ORM machinery.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """One auditable action performed on the platform."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # e.g. document.uploaded | record.extracted | record.validated.
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    # e.g. "document", "extracted_record".
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Free-form structured context for the action.
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

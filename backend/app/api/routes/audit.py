"""Audit log routes — read-only traceability view (metadata only).

GET /api/audit   paginated audit trail (newest first, bounded page size)

Honest behavior: the audit trail stores metadata only (action, entity,
counts) — never question text, answers, or document contents. When the
database is unreachable the standard 503 DatabaseUnavailableError is
raised; no fabricated entries are returned.
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session
from typing import Any

from app.db import get_db
from app.exceptions import AppError, DatabaseUnavailableError
from app.models import AuditLog

router = APIRouter(prefix="/api/audit", tags=["audit"])
logger = logging.getLogger(__name__)

MAX_PAGE_SIZE = 100


class AuditLogItem(BaseModel):
    id: int
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    details: dict[str, Any] | None = None
    created_at: str


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    page: int
    page_size: int
    total: int


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs_route(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    action: str | None = Query(default=None, description="exact action match"),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Paginated audit trail, newest first (metadata only)."""
    try:
        base = select(AuditLog)
        if action:
            base = base.where(AuditLog.action == action)
        total = db.scalar(select(func.count()).select_from(AuditLog)) or 0
        rows = db.execute(
            base.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        logger.exception("Audit log query failed")
        raise AppError(status_code=500, code="database_error", message="Could not query the audit trail.") from exc

    return AuditLogListResponse(
        items=[
            AuditLogItem(
                id=row.id,
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                details=row.details,
                created_at=row.created_at.isoformat(),
            )
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total=int(total),
    )

"""Dashboard routes (Step 14) — read-only operational aggregation.

GET /api/dashboard/summary   full payload (statuses + metrics + recents)
GET /api/dashboard/statuses  lightweight status-only polling payload

Honest offline behavior: when PostgreSQL is unreachable the summary is
still 200 with `data_available=false` and metric sections absent — the UI
shows "Database unavailable", never fabricated zeroes. Audit rows carry
counts only.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.dashboard.service import audit_metadata, build_dashboard_summary
from app.db import get_db, probe_database
from app.exceptions import DatabaseUnavailableError
from app.models import AuditLog
from app.schemas.dashboard import DashboardStatus, DashboardStatuses, DashboardSummary
from app.llm.config import default_config
from app.llm.service import llm_available

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)


def _statuses_only(db_connected: bool, detail: str | None) -> dict:
    from app.dashboard.service import compute_statuses

    statuses = compute_statuses(
        db_connected=db_connected, db_detail=detail, index_stats=None,
        llm_configured=llm_available(default_config()),
    )
    return {
        "data_available": db_connected,
        "api": DashboardStatus(component="api", status="OPERATIONAL"),
        **statuses,
    }


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary_route(db: Session = Depends(get_db)) -> DashboardSummary:
    """Operational dashboard aggregation (read-only, offline-safe)."""
    try:
        payload = build_dashboard_summary(db)
    except DatabaseUnavailableError:
        # Mid-query outage after a successful probe: honest offline payload.
        payload = _offline_payload()
    except SQLAlchemyError as exc:
        logger.exception("Dashboard aggregation failed at the database level")
        payload = _offline_payload()
        payload["message"] = (
            "Database query failed while composing the dashboard; "
            "no partial values are shown."
        )
    try:
        db.add(AuditLog(action="dashboard.summary", entity_type="dashboard",
                        entity_id=None, details=audit_metadata(payload)))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning("Dashboard audit write failed (response unaffected)")
    return DashboardSummary(**payload)


def _offline_payload() -> dict:
    """Honest offline payload (no fabricated values)."""
    from app.dashboard.service import compute_statuses

    statuses = compute_statuses(
        db_connected=False, db_detail="unavailable", index_stats=None,
        llm_configured=llm_available(default_config()),
    )
    return {
        "data_available": False,
        "message": (
            "Database unavailable — live operational metrics cannot be "
            "queried. No demo values are shown."
        ),
        "database": statuses["database"],
        "api": DashboardStatus(component="api", status="OPERATIONAL",
                               detail="API is up; database is not reachable."),
        "retrieval": statuses["retrieval"],
        "embeddings": statuses["embeddings"],
        "llm": statuses["llm"],
        "documents": None, "records": None, "validation": None,
        "knowledge": None, "intelligence": None,
        "recent_documents": [], "recent_activity": [],
        "limitations": [
            "Dashboard is read-only aggregation over source-of-truth tables.",
        ],
    }


@router.get("/statuses", response_model=DashboardStatuses)
def dashboard_statuses_route(db: Session = Depends(get_db)) -> DashboardStatuses:
    """Lightweight status-only summary (bounded probe + availability checks)."""
    connected, detail = probe_database()
    payload = _statuses_only(connected, detail)
    return DashboardStatuses(**payload)

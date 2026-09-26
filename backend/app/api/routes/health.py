"""Health check endpoints."""

from fastapi import APIRouter

from app.db import probe_database
from app.schemas.health import DatabaseHealth, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Liveness probe. Always returns 200 once the API itself is up.

    The `database` field reports an actual `SELECT 1` round-trip:
      - connected: true only when PostgreSQL answered
      - detail: "connected" | "unavailable" | "timeout"
    A missing database must never fail the API liveness probe.
    """
    connected, detail = probe_database()
    return HealthResponse(
        status="ok",
        service="cmpdi-ai-reporting-platform",
        database=DatabaseHealth(connected=connected, detail=detail),
    )

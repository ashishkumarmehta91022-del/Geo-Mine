"""Health check endpoints."""

from fastapi import APIRouter

from app.db import check_database_connection
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Liveness probe. Always returns 200 once the app is up.

    Reports `database: "up" | "down"` as extra diagnostic info without
    failing the request — a missing PostgreSQL must not crash the probe.
    """
    database = "up" if check_database_connection() else "down"
    return HealthResponse(
        status="ok",
        service="cmpdi-ai-reporting-platform",
        database=database,
    )


"""Health endpoint response schema."""

from pydantic import BaseModel


class DatabaseHealth(BaseModel):
    """Honest database connectivity report."""

    connected: bool
    # "connected" | "unavailable" | "timeout" — why the probe returned what it did.
    detail: str


class HealthResponse(BaseModel):
    status: str
    service: str
    database: DatabaseHealth

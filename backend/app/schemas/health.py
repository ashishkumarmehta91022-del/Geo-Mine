"""Health endpoint response schema."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str = "unknown"

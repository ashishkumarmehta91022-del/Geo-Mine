"""Report analysis API schemas (Step 12)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.reports import ReportFiltersIn


class ReportAnalyzeRequest(BaseModel):
    """Raw analysis request — validated/bounded by app/reports/spec.py.

    The analytical sections follow the report specification model: same
    selections, filters and bounds. `include_narrative` opts into the
    optional AI narrative layer (honest fallback when unavailable).
    """

    title: str = Field(..., min_length=1, max_length=200)
    report_type: str | None = Field(default=None, max_length=64)
    reporting_period: str | None = Field(default=None, max_length=64)
    document_ids: list[int] | None = None
    entities: list[str] | None = None
    metrics: list[str] | None = None
    output_format: str = Field(default="json", max_length=16)
    filters: ReportFiltersIn | None = None
    requester: str | None = Field(default=None, max_length=128)
    include_narrative: bool = False


class ReportAnalyzeResponse(BaseModel):
    """Deterministic analytical result (LLM narrative optional, labeled)."""

    status: str
    report_id: str
    fingerprint: str
    specification: dict[str, Any]
    generated_at: datetime
    record_count: int
    document_count: int
    conflict_count: int
    validation_warning_error_count: int
    excluded_value_count: int
    kpis: list[dict[str, Any]] = []
    trends: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    distributions: list[dict[str, Any]] = []
    insights: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []
    excluded_values: list[dict[str, Any]] = []
    narrative: dict[str, Any] | None = None
    limitations: list[str] = []

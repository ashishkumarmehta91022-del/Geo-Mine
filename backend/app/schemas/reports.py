"""Report generation API schemas (Step 11)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportFiltersIn(BaseModel):
    """Optional narrowing filters (all equality-based, all optional)."""

    validation_status: str | None = Field(default=None, max_length=32)
    extraction_method: str | None = Field(default=None, max_length=32)
    record_type: str | None = Field(default=None, max_length=64)


class ReportGenerateRequest(BaseModel):
    """Raw report request — validated/bounded by app/reports/spec.py."""

    title: str = Field(..., min_length=1, max_length=200)
    report_type: str | None = Field(default=None, max_length=64)
    reporting_period: str | None = Field(default=None, max_length=64)
    document_ids: list[int] | None = None
    entities: list[str] | None = None
    metrics: list[str] | None = None
    sections: list[str] | None = None
    output_format: str = Field(default="docx", max_length=16)
    filters: ReportFiltersIn | None = None
    requester: str | None = Field(default=None, max_length=128)


class ReportConflictSide(BaseModel):
    value_raw: str
    normalized_values: list[str | None] = []
    sources: list[dict[str, Any]] = []


class ReportConflictItem(BaseModel):
    entity: str | None = None
    metric: str | None = None
    reporting_period: str | None = None
    unit: str | None = None
    status: str
    values: list[ReportConflictSide] = []


class ReportArtifactInfo(BaseModel):
    format: str
    filename: str
    size_bytes: int
    download_available: bool
    note: str | None = None


class ReportGenerateResponse(BaseModel):
    """Generation result — DOCX bytes ride outside this model as the HTTP
    attachment; everything here is JSON-safe metadata."""

    status: str
    report_id: str
    fingerprint: str
    specification: dict[str, Any]
    reporting_period: str | None = None
    generated_at: datetime
    artifact: ReportArtifactInfo
    summary: dict[str, Any]
    conflict_count: int
    conflicts: list[ReportConflictItem] = []
    evidence_count: int
    validation_warning_error_count: int
    missing_value_count: int
    sections_built: list[str] = []
    limitations: list[str] = []


class ReportGenerateOK(BaseModel):
    """Response body for the JSON variant of the endpoint (format=json)."""

    report: ReportGenerateResponse

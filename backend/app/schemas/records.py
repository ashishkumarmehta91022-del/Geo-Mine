"""Structured record API schemas (Step 7)."""

from datetime import datetime
from typing import Any
from decimal import Decimal

from pydantic import BaseModel


class RecordResponse(BaseModel):
    id: int
    document_id: int
    document_filename: str | None = None
    page_id: int | None
    page_number: int | None = None
    entity_name: str
    metric_name: str
    # raw ≠ derived: both are always exposed.
    value_raw: str | None
    metric_value: Decimal | None
    normalized_value: str | None
    unit: str | None
    reporting_period: str | None
    source_reference: str | None
    extraction_method: str | None
    confidence: float | None
    validation_status: str
    record_metadata: dict[str, Any] | None


class RecordListResponse(BaseModel):
    items: list[RecordResponse]
    page: int
    page_size: int
    total: int

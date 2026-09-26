"""Validation data models — decoupled from the ORM so the engine is DB-free.

`ValueCandidate` wraps one extracted value (verbatim) with its provenance;
`RuleOutcome` is one rule's verdict. Neither ever rewrites the source value.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

# Field names rules may reference (map to ExtractedRecord columns).
FIELD_ENTITY = "entity_name"
FIELD_METRIC = "metric_name"
FIELD_VALUE = "metric_value"
FIELD_UNIT = "unit"
FIELD_PERIOD = "reporting_period"

_KNOWN_FIELDS = {FIELD_ENTITY, FIELD_METRIC, FIELD_VALUE, FIELD_UNIT, FIELD_PERIOD}


@dataclass(frozen=True)
class ValueCandidate:
    """One extracted value under validation, with full provenance."""

    document_id: int
    metric_name: str
    raw_value: str | None  # verbatim source text — never modified
    numeric_value: Decimal | None = None  # parsed when cleanly parseable
    record_id: int | None = None
    page_id: int | None = None
    entity_name: str | None = None
    unit: str | None = None
    reporting_period: str | None = None
    source_reference: str | None = None
    confidence: float | None = None  # extraction/OCR confidence in [0,1]
    review_required: bool = False  # carried from OCR metadata (Step 5)
    ocr_metadata: dict[str, Any] | None = None
    document_filename: str | None = None

    def field_value(self, field_name: str) -> str | None:
        """Raw text of a named field (verbatim)."""
        if field_name not in _KNOWN_FIELDS:
            raise KeyError(f"Unknown validation field: {field_name}")
        return {
            FIELD_ENTITY: self.entity_name,
            FIELD_METRIC: self.metric_name,
            FIELD_VALUE: self.raw_value,
            FIELD_UNIT: self.unit,
            FIELD_PERIOD: self.reporting_period,
        }[field_name]


@dataclass(frozen=True)
class RuleOutcome:
    """One rule applied to one candidate. Provenance always preserved."""

    rule_code: str
    status: str  # ValidationStatus value
    severity: str  # ValidationSeverity value
    message: str
    candidate: ValueCandidate
    expected: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

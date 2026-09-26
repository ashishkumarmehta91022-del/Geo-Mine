"""Field-extraction configuration.

*** DEMONSTRATION SCHEMA ***
The metric patterns below are generic development examples for exercising the
pipeline (e.g. DEMO_COAL_PRODUCTION). They are NOT official CMPDI/CIL field
definitions. Authoritative fields/mappings can replace them via configuration
without touching the extraction engine: each entry maps a metric pattern to
the validation expectation consumed by the Step 6 engine.
"""

import re
from dataclasses import dataclass, field

from app.validation.config import NumericSpec, RangeSpec


@dataclass(frozen=True)
class FieldSpec:
    """One structured field definition (demo values — replace with authoritative ones)."""

    metric_pattern: str  # regex over the metric name (exact-match friendly)
    label: str  # human-readable demo label
    required: bool = False
    numeric: NumericSpec | None = None
    range: RangeSpec | None = None
    allow_future_date: bool = False


@dataclass(frozen=True)
class StructuringConfig:
    """All field definitions + builder switches in one deterministic object."""

    # metric_name (lowercased) -> spec; matched with re.fullmatch.
    field_specs: dict[str, FieldSpec] = field(default_factory=dict)
    # Candidate labels recognized inside sheet/table cells (demo).
    entity_column_aliases: tuple[str, ...] = ("mine", "entity", "mine name", "entity_name")
    value_column_aliases: tuple[str, ...] = ("value", "quantity", "production", "amount")
    unit_column_aliases: tuple[str, ...] = ("unit", "units", "uom")
    period_column_aliases: tuple[str, ...] = ("period", "reporting period", "date", "year", "month")
    metric_column_aliases: tuple[str, ...] = ("metric", "field", "parameter")
    # Longest text block from a page kept as a record (guardrail).
    max_text_records_per_page: int = 3


def demo_config() -> StructuringConfig:
    """DEMO field schema — clearly labeled, deterministic, swappable."""
    return StructuringConfig(
        field_specs={
            "demo_coal_production": FieldSpec(
                metric_pattern=r"demo_coal_production",
                label="DEMO coal production",
                required=True,
                numeric=NumericSpec(allow_negative=False),
                range=RangeSpec(minimum=0, maximum=10_000_000),
            ),
            "demo_overburden_removed": FieldSpec(
                metric_pattern=r"demo_overburden_removed",
                label="DEMO overburden removed (m³)",
                numeric=NumericSpec(allow_negative=False),
                range=RangeSpec(minimum=0, maximum=50_000_000),
            ),
        },
        entity_column_aliases=("mine", "entity", "mine name", "entity_name"),
        value_column_aliases=("value", "quantity", "production", "amount"),
        unit_column_aliases=("unit", "units", "uom"),
        period_column_aliases=("period", "reporting period", "date", "year", "month"),
        metric_column_aliases=("metric", "field", "parameter"),
    )

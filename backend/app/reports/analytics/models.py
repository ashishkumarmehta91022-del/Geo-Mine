"""Typed analytical models (Step 12) — every result keeps provenance.

Analytical objects (KPI/Trend/Comparison/Distribution/Insight/ChartSpec) are
DERIVED VIEWS over the Step 7 source-of-truth records — they never replace
or duplicate it. Every model carries source record/document ids, validation
status and conflict status so no analytical output can become untraceable.
All payloads are JSON-safe (frontend-friendly chart specifications).
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class InsightKind(StrEnum):
    """Deterministic insight kinds (extensible)."""

    TREND = "TREND"
    CHANGE = "CHANGE"
    COMPARISON = "COMPARISON"
    DATA_GAP = "DATA_GAP"
    VALIDATION_WARNING = "VALIDATION_WARNING"
    CONFLICT = "CONFLICT"


class AnalyticalStatus(StrEnum):
    """Status of an analytical result regarding data trustworthiness."""

    OK = "ok"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class ExcludedValue:
    """A record excluded from arithmetic — raw value preserved, reason given."""

    record_id: int
    document_id: int
    value_raw: str | None
    normalized_value: str | None
    reason: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "document_id": self.document_id,
            "value_raw": self.value_raw,
            "normalized_value": self.normalized_value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class KPI:
    """One deterministic key performance indicator."""

    name: str                       # e.g. "total", "average", "count_records"
    label: str                      # human-readable, e.g. "Total production"
    entity: str | None = None
    metric: str | None = None
    reporting_period: str | None = None
    unit: str | None = None
    value: Decimal | None = None    # None for count-style KPIs' numeric absence
    count: int | None = None        # for count-style KPIs
    # Provenance / trust.
    source_record_ids: list[int] = field(default_factory=list)
    source_document_ids: list[int] = field(default_factory=list)
    validation_status: str | None = None
    conflict_status: str = AnalyticalStatus.OK.value
    excluded: list[ExcludedValue] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "entity": self.entity,
            "metric": self.metric,
            "reporting_period": self.reporting_period,
            "unit": self.unit,
            "value": str(self.value) if self.value is not None else None,
            "count": self.count,
            "source_record_ids": list(self.source_record_ids),
            "source_document_ids": list(self.source_document_ids),
            "validation_status": self.validation_status,
            "conflict_status": self.conflict_status,
            "excluded": [item.to_payload() for item in self.excluded],
        }


@dataclass(frozen=True)
class TrendPoint:
    period: str
    value: Decimal
    value_raw: str | None
    record_ids: list[int]
    document_ids: list[int]
    validation_status: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "value": str(self.value),
            "value_raw": self.value_raw,
            "record_ids": list(self.record_ids),
            "document_ids": list(self.document_ids),
            "validation_status": self.validation_status,
        }


@dataclass(frozen=True)
class Trend:
    """Deterministic time-series analysis for one (entity, metric, unit)."""

    entity: str | None
    metric: str | None
    unit: str | None
    points: list[TrendPoint] = field(default_factory=list)
    missing_periods: list[str] = field(default_factory=list)  # explicitly reported gaps
    first_value: Decimal | None = None
    last_value: Decimal | None = None
    absolute_change: Decimal | None = None
    percent_change: Decimal | None = None      # None when first == 0 or unsafe
    percent_change_valid: bool = False
    direction: str = "unchanged"               # increasing | decreasing | unchanged
    status: str = AnalyticalStatus.OK.value    # review_required when conflicts inside
    source_record_ids: list[int] = field(default_factory=list)
    source_document_ids: list[int] = field(default_factory=list)
    excluded: list[ExcludedValue] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "metric": self.metric,
            "unit": self.unit,
            "points": [p.to_payload() for p in self.points],
            "missing_periods": list(self.missing_periods),
            "first_value": str(self.first_value) if self.first_value is not None else None,
            "last_value": str(self.last_value) if self.last_value is not None else None,
            "absolute_change": str(self.absolute_change) if self.absolute_change is not None else None,
            "percent_change": str(self.percent_change) if self.percent_change is not None else None,
            "percent_change_valid": self.percent_change_valid,
            "direction": self.direction,
            "status": self.status,
            "source_record_ids": list(self.source_record_ids),
            "source_document_ids": list(self.source_document_ids),
            "excluded": [item.to_payload() for item in self.excluded],
        }


@dataclass(frozen=True)
class ComparisonSide:
    label: str                      # entity, metric or period name
    value: Decimal | None
    value_raw: str | None
    unit: str | None
    record_ids: list[int]
    document_ids: list[int]
    validation_status: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "value": str(self.value) if self.value is not None else None,
            "value_raw": self.value_raw,
            "unit": self.unit,
            "record_ids": list(self.record_ids),
            "document_ids": list(self.document_ids),
            "validation_status": self.validation_status,
        }


@dataclass(frozen=True)
class Comparison:
    """Deterministic comparison across entities, metrics or periods.

    Differences are computed only within one unit; sides with no safe
    numeric value are kept (raw preserved) and make the difference None.
    """

    kind: str                       # entities | metrics | periods
    metric: str | None              # the metric compared (entities/periods kinds)
    unit: str | None
    period: str | None              # the period compared (entities/metrics kinds)
    sides: list[ComparisonSide] = field(default_factory=list)
    absolute_difference: Decimal | None = None
    difference_unit: str | None = None
    difference_valid: bool = False
    status: str = AnalyticalStatus.OK.value
    source_record_ids: list[int] = field(default_factory=list)
    source_document_ids: list[int] = field(default_factory=list)
    excluded: list[ExcludedValue] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "metric": self.metric,
            "unit": self.unit,
            "period": self.period,
            "sides": [s.to_payload() for s in self.sides],
            "absolute_difference": (
                str(self.absolute_difference) if self.absolute_difference is not None else None
            ),
            "difference_unit": self.difference_unit,
            "difference_valid": self.difference_valid,
            "status": self.status,
            "source_record_ids": list(self.source_record_ids),
            "source_document_ids": list(self.source_document_ids),
            "excluded": [item.to_payload() for item in self.excluded],
        }


@dataclass(frozen=True)
class Distribution:
    """Value distribution for one metric (histogram of safe numeric values)."""

    metric: str | None
    unit: str | None
    bins: list[dict[str, Any]] = field(default_factory=list)  # {range, count}
    total_counted: int = 0
    excluded: list[ExcludedValue] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "unit": self.unit,
            "bins": [dict(b) for b in self.bins],
            "total_counted": self.total_counted,
            "excluded": [item.to_payload() for item in self.excluded],
        }


@dataclass(frozen=True)
class Insight:
    """One deterministic, descriptive (never causal/speculative) insight."""

    kind: InsightKind
    message: str                    # descriptive language only
    entity: str | None = None
    metric: str | None = None
    reporting_period: str | None = None
    status: str = AnalyticalStatus.OK.value
    source_record_ids: list[int] = field(default_factory=list)
    source_document_ids: list[int] = field(default_factory=list)
    related_chart: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "message": self.message,
            "entity": self.entity,
            "metric": self.metric,
            "reporting_period": self.reporting_period,
            "status": self.status,
            "source_record_ids": list(self.source_record_ids),
            "source_document_ids": list(self.source_document_ids),
            "related_chart": self.related_chart,
        }


@dataclass(frozen=True)
class ChartSeries:
    name: str
    unit: str | None
    # Frontend-friendly points: {"x": <period/category>, "y": <number|null>}
    points: list[dict[str, Any]] = field(default_factory=list)
    point_record_ids: list[list[int]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "points": [dict(p) for p in self.points],
            "point_record_ids": [list(ids) for ids in self.point_record_ids],
        }


@dataclass(frozen=True)
class ChartSpec:
    """Frontend-friendly chart DATA specification (no backend rendering)."""

    chart_type: str                 # line | bar | comparison
    title: str
    x_axis: str
    y_axis: str
    unit: str | None
    series: list[ChartSeries] = field(default_factory=list)
    source_record_ids: list[int] = field(default_factory=list)
    source_document_ids: list[int] = field(default_factory=list)
    conflict_status: str = AnalyticalStatus.OK.value
    validation_statuses: list[str] = field(default_factory=list)
    note: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "chart_type": self.chart_type,
            "title": self.title,
            "x_axis": self.x_axis,
            "y_axis": self.y_axis,
            "unit": self.unit,
            "series": [s.to_payload() for s in self.series],
            "source_record_ids": list(self.source_record_ids),
            "source_document_ids": list(self.source_document_ids),
            "conflict_status": self.conflict_status,
            "validation_statuses": list(self.validation_statuses),
            "note": self.note,
        }


@dataclass
class AnalyticsResult:
    """Complete analytical output for one report selection (deterministic)."""

    kpis: list[KPI] = field(default_factory=list)
    trends: list[Trend] = field(default_factory=list)
    comparisons: list[Comparison] = field(default_factory=list)
    distributions: list[Distribution] = field(default_factory=list)
    insights: list[Insight] = field(default_factory=list)
    charts: list[ChartSpec] = field(default_factory=list)
    excluded_values: list[ExcludedValue] = field(default_factory=list)
    conflict_count: int = 0
    validation_warning_error_count: int = 0
    record_count: int = 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "kpis": [k.to_payload() for k in self.kpis],
            "trends": [t.to_payload() for t in self.trends],
            "comparisons": [c.to_payload() for c in self.comparisons],
            "distributions": [d.to_payload() for d in self.distributions],
            "insights": [i.to_payload() for i in self.insights],
            "charts": [c.to_payload() for c in self.charts],
            "excluded_values": [e.to_payload() for e in self.excluded_values],
            "conflict_count": self.conflict_count,
            "validation_warning_error_count": self.validation_warning_error_count,
            "record_count": self.record_count,
        }

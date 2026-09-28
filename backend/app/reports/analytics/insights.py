"""Deterministic insight generation (Step 12, Phase 9).

Insights are DESCRIPTIVE ONLY: they state what the validated data shows
(directions, differences, gaps, conflicts) and never claim causation,
never speculate, never recommend. Conflicted and flagged data produce
explicit review-required insights instead of silent omission.
"""

from typing import Any

from app.reports.analytics.engine import REVIEW_STATUSES
from app.reports.analytics.models import (
    AnalyticalStatus,
    Comparison,
    Insight,
    InsightKind,
    Trend,
)
from app.reports.engine import REPORT_DATA_MISSING, ReportData

MAX_INSIGHTS = 60
MAX_GAP_INSIGHTS = 12

_KIND_ORDER = {
    InsightKind.CONFLICT: 0,
    InsightKind.VALIDATION_WARNING: 1,
    InsightKind.DATA_GAP: 2,
    InsightKind.TREND: 3,
    InsightKind.CHANGE: 4,
    InsightKind.COMPARISON: 5,
}


def _flat(value: Any) -> str:
    """Single-line deterministic text for any dynamic fragment."""
    return " ".join(str(value).split()) if value is not None else ""


def _fmt(value) -> str:
    """Deterministic human number format (no trailing zeros)."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _conflict_insights(data: ReportData) -> list[Insight]:
    insights: list[Insight] = []
    for conflict in data.conflicts:
        scope = " — ".join(
            part for part in (conflict.entity, conflict.metric,
                              conflict.reporting_period, conflict.unit) if part
        ) or "unspecified selection"
        values = ", ".join(_flat(v["value_raw"]) for v in conflict.values)
        insights.append(Insight(
            kind=InsightKind.CONFLICT,
            message=(
                f"Different {_flat(conflict.metric) or 'value'} values were "
                f"found for {scope} ({values}). Human review is required."
            ),
            entity=conflict.entity, metric=conflict.metric,
            reporting_period=conflict.reporting_period,
            status=AnalyticalStatus.REVIEW_REQUIRED.value,
            source_record_ids=sorted({
                entry["record_id"] for v in conflict.values for entry in v["sources"]
            }),
            source_document_ids=sorted({
                entry["document_id"] for v in conflict.values for entry in v["sources"]
            }),
        ))
    return insights


def _validation_insights(data: ReportData) -> list[Insight]:
    insights: list[Insight] = []
    flagged = [r for r in data.records if (r.validation_status or "") in REVIEW_STATUSES]
    for record in flagged:
        insights.append(Insight(
            kind=InsightKind.VALIDATION_WARNING,
            message=(
                f"{_flat(record.metric) or 'Record'} value "
                f"'{_flat(record.value_raw) or REPORT_DATA_MISSING}' for "
                f"{_flat(record.entity) or '?'} "
                f"({_flat(record.reporting_period) or 'no period'}) has "
                f"validation status {record.validation_status}. Verify "
                f"against the source document."
            ),
            entity=record.entity, metric=record.metric,
            reporting_period=record.reporting_period,
            status=AnalyticalStatus.REVIEW_REQUIRED.value,
            source_record_ids=[record.record_id],
            source_document_ids=[record.document_id],
        ))
    return insights


def _gap_insights(data: ReportData, trends: list[Trend]) -> list[Insight]:
    insights: list[Insight] = []
    # Records with no stored value at all — explicit missing information.
    valueless = [r for r in data.records if not r.has_value()]
    for record in valueless[:MAX_GAP_INSIGHTS]:
        insights.append(Insight(
            kind=InsightKind.DATA_GAP,
            message=(
                f"No {_flat(record.metric) or 'metric'} value is available "
                f"for {_flat(record.entity) or '?'} "
                f"({_flat(record.reporting_period) or 'no period'})."
            ),
            entity=record.entity, metric=record.metric,
            reporting_period=record.reporting_period,
            source_record_ids=[record.record_id],
            source_document_ids=[record.document_id],
        ))
    # Calendar-like gaps between trend points — explicitly represented.
    for trend in trends:
        for period in trend.missing_periods[:MAX_GAP_INSIGHTS]:
            insights.append(Insight(
                kind=InsightKind.DATA_GAP,
                message=(
                    f"No {_flat(trend.metric) or 'metric'} record is "
                    f"available for {period}"
                    + (f" ({_flat(trend.entity)})" if trend.entity else "") + "."
                ),
                entity=trend.entity, metric=trend.metric,
                reporting_period=period,
                source_record_ids=[],  # a gap has no records by definition
                source_document_ids=sorted(trend.source_document_ids),
            ))
    return insights


def _trend_insights(trends: list[Trend]) -> list[Insight]:
    insights: list[Insight] = []
    past_tense = {"increasing": "increased", "decreasing": "decreased"}
    for trend in trends:
        # A definitive trend sentence is stated only for clean series —
        # series with exclusions/conflicts already carry review insights.
        if trend.status != AnalyticalStatus.OK.value:
            continue
        if len(trend.points) < 2 or trend.absolute_change is None:
            continue
        first_period = trend.points[0].period
        last_period = trend.points[-1].period
        unit = f" {_flat(trend.unit)}" if trend.unit else ""
        if trend.direction in past_tense:
            message = (
                f"{_flat(trend.metric) or 'Value'} {past_tense[trend.direction]} "
                f"from {_fmt(trend.first_value)}{unit} to "
                f"{_fmt(trend.last_value)}{unit} between {first_period} "
                f"and {last_period}."
            )
        else:  # unchanged
            message = (
                f"{_flat(trend.metric) or 'Value'} remained unchanged at "
                f"{_fmt(trend.first_value)}{unit} between {first_period} "
                f"and {last_period}."
            )
        insights.append(Insight(
            kind=InsightKind.TREND,
            message=message,
            entity=trend.entity, metric=trend.metric,
            source_record_ids=list(trend.source_record_ids),
            source_document_ids=list(trend.source_document_ids),
        ))
    return insights


def _comparison_insights(comparisons: list[Comparison]) -> list[Insight]:
    insights: list[Insight] = []
    for comparison in comparisons:
        if comparison.status != AnalyticalStatus.OK.value:
            continue
        valued = [s for s in comparison.sides if s.value is not None]
        if len(valued) < 2:
            continue
        unit = f" {_flat(comparison.unit)}" if comparison.unit else ""
        sides_text = ", ".join(
            f"{_flat(s.label)} = {_fmt(s.value)}{unit}" for s in valued
        )
        insights.append(Insight(
            kind=InsightKind.COMPARISON,
            message=(
                f"{_flat(comparison.metric) or 'Value'} differs across "
                f"entities for {_flat(comparison.period) or 'the selection'}: "
                f"{sides_text} (difference {_fmt(comparison.absolute_difference)}{unit})."
            ),
            metric=comparison.metric,
            reporting_period=comparison.period,
            source_record_ids=list(comparison.source_record_ids),
            source_document_ids=list(comparison.source_document_ids),
        ))
    return insights


def generate_insights(
    data: ReportData,
    trends: list[Trend],
    comparisons: list[Comparison],
) -> list[Insight]:
    """Deterministic insight set in fixed kind order, bounded (never causal)."""
    insights: list[Insight] = []
    insights.extend(_conflict_insights(data))
    insights.extend(_validation_insights(data))
    insights.extend(_gap_insights(data, trends))
    insights.extend(_trend_insights(trends))
    insights.extend(_comparison_insights(comparisons))
    insights.sort(key=lambda i: (_KIND_ORDER[i.kind], i.message))
    return insights[:MAX_INSIGHTS]

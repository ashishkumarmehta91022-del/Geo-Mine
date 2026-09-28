"""Chart specification generation (Step 12, Phase 7).

Produces frontend-friendly chart DATA (no backend rendering, no new
visualization dependency). Every chart keeps source record ids and
validation/conflict status; conflicted or excluded data is never plotted as
if it were certain — gaps render as null points, review-required series are
labeled in the spec.
"""

from app.reports.analytics.models import (
    AnalyticalStatus,
    ChartSeries,
    ChartSpec,
    Comparison,
    Distribution,
    Trend,
)
from app.reports.engine import ReportData

MAX_CHARTS = 30


def _trend_charts(trends: list[Trend]) -> list[ChartSpec]:
    charts: list[ChartSpec] = []
    for trend in trends:
        series_name = trend.entity or trend.metric or "value"
        # Missing calendar periods are explicitly represented as null points
        # (a gap in the chart, never a fabricated interpolation).
        present = {p.period: p for p in trend.points}
        ordered_periods = sorted(
            set(list(present) + list(trend.missing_periods)),
            key=lambda p: (p is None, p or ""),
        )
        points: list[dict] = []
        point_record_ids: list[list[int]] = []
        for period in ordered_periods:
            point = present.get(period)
            if point is not None:
                points.append({"x": period, "y": float(point.value)})
                point_record_ids.append(list(point.record_ids))
            else:
                points.append({"x": period, "y": None})
                point_record_ids.append([])
        title = f"{trend.metric or 'Value'} by Period"
        if trend.entity:
            title = f"{title} — {trend.entity}"
        review = trend.status != AnalyticalStatus.OK.value
        charts.append(ChartSpec(
            chart_type="line",
            title=title,
            x_axis="Reporting Period",
            y_axis=trend.metric or "Value",
            unit=trend.unit,
            series=[ChartSeries(name=series_name, unit=trend.unit,
                                points=points, point_record_ids=point_record_ids)],
            source_record_ids=list(trend.source_record_ids),
            source_document_ids=list(trend.source_document_ids),
            conflict_status=trend.status,
            validation_statuses=sorted({p.validation_status or "unknown" for p in trend.points}),
            note=("Contains excluded or conflicting values; conflicted values "
                  "are not plotted — see validation/conflict notes."
                  if review else None),
        ))
    return charts


def _distribution_charts(distributions: list[Distribution]) -> list[ChartSpec]:
    charts: list[ChartSpec] = []
    for distribution in distributions:
        charts.append(ChartSpec(
            chart_type="bar",
            title=f"Distribution of {distribution.metric or 'values'}"
                  + (f" ({distribution.unit})" if distribution.unit else ""),
            x_axis="Value range",
            y_axis="Record count",
            unit="count",
            series=[ChartSeries(
                name="records",
                unit="count",
                points=[{"x": b["range"], "y": b["count"]} for b in distribution.bins],
                point_record_ids=[],
            )],
            source_record_ids=[],  # bins aggregate; exclusions listed on the distribution
            source_document_ids=[],
            conflict_status=(
                AnalyticalStatus.REVIEW_REQUIRED.value if distribution.excluded
                else AnalyticalStatus.OK.value
            ),
            validation_statuses=["pass"] if distribution.total_counted else [],
            note=(f"{len(distribution.excluded)} value(s) excluded from the "
                  f"distribution (conflicts/validation/non-numeric)."
                  if distribution.excluded else None),
        ))
    return charts


def _comparison_charts(comparisons: list[Comparison]) -> list[ChartSpec]:
    charts: list[ChartSpec] = []
    for comparison in comparisons:
        title = f"{comparison.metric or 'Value'} by Entity"
        if comparison.period:
            title = f"{title} ({comparison.period})"
        review = comparison.status != AnalyticalStatus.OK.value
        charts.append(ChartSpec(
            chart_type="comparison",
            title=title,
            x_axis="Entity",
            y_axis=comparison.metric or "Value",
            unit=comparison.unit,
            series=[ChartSeries(
                name=comparison.metric or "value",
                unit=comparison.unit,
                points=[
                    # Entities without a safe value appear with y=null —
                    # visible, never silently dropped, never given a number.
                    {"x": side.label, "y": float(side.value) if side.value is not None else None}
                    for side in comparison.sides
                ],
                point_record_ids=[list(side.record_ids) for side in comparison.sides],
            )],
            source_record_ids=list(comparison.source_record_ids),
            source_document_ids=list(comparison.source_document_ids),
            conflict_status=comparison.status,
            validation_statuses=sorted({s.validation_status or "unknown" for s in comparison.sides}),
            note=("Contains excluded or conflicting values; entities without "
                  "a verified value are shown as gaps — no winner implied."
                  if review else None),
        ))
    return charts


def generate_charts(
    data: ReportData,
    trends: list[Trend],
    comparisons: list[Comparison],
    distributions: list[Distribution],
) -> list[ChartSpec]:
    """Deterministic chart DATA specifications (line → bar → comparison)."""
    charts: list[ChartSpec] = []
    charts.extend(_trend_charts(trends))
    charts.extend(_distribution_charts(distributions))
    charts.extend(_comparison_charts(comparisons))
    return charts[:MAX_CHARTS]

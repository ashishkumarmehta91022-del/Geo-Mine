"""Analytical report sections (Step 12, Phase 10).

Deterministic section builders that extend the Step 11 report with the
Step 12 analytical layer. Same rules as app/reports/sections.py: builders
consume only collected/analytical data — every number originates from stored
structured records. No LLM anywhere in this module.

`charts` renders the frontend-friendly chart DATA specifications as a
structured appendix (values only; the actual visualization is the
frontend's job — no chart-rendering dependency was added).
"""

from typing import Any

from app.reports.analytics.models import AnalyticalStatus
from app.reports.engine import ReportData

MAX_CHART_ROWS = 40


def _fmt(value) -> str:
    """Deterministic human number format (no trailing zeros)."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _status_suffix(status: str) -> str:
    return "  [REVIEW REQUIRED]" if status == AnalyticalStatus.REVIEW_REQUIRED.value else ""


def _kpi_summary(data: ReportData, analytics) -> dict[str, Any]:
    rows = []
    for kpi in analytics.kpis:
        if kpi.name.startswith("count_"):
            rows.append([kpi.label, str(kpi.count), "—", "—"])
        else:
            value = _fmt(kpi.value) if kpi.value is not None else "—"
            rows.append([
                kpi.label,
                value,
                kpi.unit or "—",
                _status_suffix(kpi.conflict_status).strip() or "OK",
            ])
    return {
        "title": "KPI Summary",
        "headers": ["Indicator", "Value", "Unit", "Status"],
        "rows": rows,
        "empty_note": "No KPIs were computable for this selection." if not rows else None,
        "excluded_note": (
            f"{len(analytics.excluded_values)} value(s) were excluded from "
            "arithmetic (conflicts, validation states, non-numeric normalized "
            "values); raw values are preserved in the detailed data section."
            if analytics.excluded_values else None
        ),
    }


def _analytical_insights(data: ReportData, analytics) -> dict[str, Any]:
    items = [
        {
            "kind": insight.kind.value,
            "headline": insight.kind.value,
            "lines": [insight.message],
            "status": ("REVIEW REQUIRED"
                       if insight.status == AnalyticalStatus.REVIEW_REQUIRED.value
                       else "OK"),
        }
        for insight in analytics.insights
    ]
    return {
        "title": "Analytical Insights",
        "items": items,
        "empty_note": ("No insights were derivable from the selection — "
                       "nothing was assumed.") if not items else None,
    }


def _trends_section(data: ReportData, analytics) -> dict[str, Any]:
    items = []
    for trend in analytics.trends:
        lines = []
        for point in trend.points:
            lines.append(
                f"{point.period}: {_fmt(point.value)}"
                + (f" {trend.unit}" if trend.unit else "")
                + (f" (raw: {point.value_raw})" if point.value_raw != str(point.value) else "")
                + f" — records {point.record_ids}"
            )
        for gap in trend.missing_periods:
            lines.append(f"{gap}: no record available (gap)")
        change = "n/a"
        if trend.absolute_change is not None:
            change = _fmt(trend.absolute_change)
            if trend.percent_change is not None:
                change += f" ({_fmt(trend.percent_change)}%)"
        elif len(trend.points) >= 2 and trend.first_value == 0:
            change = "percentage change not defined for a zero base"
        lines.append(f"Change (first→last): {change}")
        if trend.status == AnalyticalStatus.REVIEW_REQUIRED.value:
            lines.append(
                "REVIEW REQUIRED: contains excluded or conflicting values; "
                "conflicted values are not charted or aggregated."
            )
        scope = " — ".join(part for part in (trend.entity, trend.metric, trend.unit) if part)
        items.append({"headline": scope or "trend", "lines": lines,
                      "status": "REVIEW REQUIRED" if trend.status == AnalyticalStatus.REVIEW_REQUIRED.value else "OK"})
    return {
        "title": "Trends",
        "items": items,
        "empty_note": ("No time-series with at least one validated numeric "
                       "value was available.") if not items else None,
    }


def _comparisons_section(data: ReportData, analytics) -> dict[str, Any]:
    headers = ["Metric", "Period", "Entity", "Value", "Unit", "Validation", "Status"]
    rows = []
    for comparison in analytics.comparisons:
        for side in comparison.sides:
            rows.append([
                comparison.metric or "—",
                comparison.period or "—",
                side.label,
                _fmt(side.value) if side.value is not None else "no verified value",
                comparison.unit or "—",
                side.validation_status or "—",
                "REVIEW REQUIRED" if comparison.status == AnalyticalStatus.REVIEW_REQUIRED.value else "OK",
            ])
        if comparison.sides and comparison.absolute_difference is not None:
            rows.append([
                comparison.metric or "—", comparison.period or "—",
                "difference (max−min, verified values only)",
                _fmt(comparison.absolute_difference),
                comparison.difference_unit or "—", "—",
                "REVIEW REQUIRED" if comparison.status == AnalyticalStatus.REVIEW_REQUIRED.value else "OK",
            ])
    return {
        "title": "Comparisons",
        "headers": headers,
        "rows": rows,
        "empty_note": ("No entity comparisons were computable (needs ≥ 2 "
                       "entities with validated numeric values for the same "
                       "metric/unit/period).") if not rows else None,
    }


def _charts_appendix(data: ReportData, analytics) -> dict[str, Any]:
    items = []
    for chart in analytics.charts:
        lines = [f"Type: {chart.chart_type} · X: {chart.x_axis} · Y: {chart.y_axis}"
                 + (f" · Unit: {chart.unit}" if chart.unit else "")]
        for series in chart.series:
            rendered = 0
            for point in series.points:
                if rendered >= MAX_CHART_ROWS:
                    lines.append(f"  … {len(series.points) - rendered} more point(s)")
                    break
                y = "gap (no verified value)" if point.get("y") is None else _fmt(point["y"])
                lines.append(f"  {series.name} @ {point.get('x')}: {y}")
                rendered += 1
        lines.append(f"Source records: {chart.source_record_ids}")
        if chart.conflict_status == AnalyticalStatus.REVIEW_REQUIRED.value:
            lines.append("Status: REVIEW REQUIRED — conflicted values are not plotted.")
        items.append({"headline": chart.title, "lines": lines,
                      "status": "REVIEW REQUIRED" if chart.conflict_status == AnalyticalStatus.REVIEW_REQUIRED.value else "OK"})
    return {
        "title": "Charts (Data Specifications)",
        "items": items,
        "note": ("Chart DATA specifications for frontend visualization — "
                 "values only, no images. Interactive rendering is the "
                 "frontend's responsibility."),
        "empty_note": "No chart specifications were derivable.",
    }


# Registration point — new analytical sections plug in here.
ANALYTICAL_BUILDERS = {
    "kpi_summary": _kpi_summary,
    "analytical_insights": _analytical_insights,
    "trends": _trends_section,
    "comparisons": _comparisons_section,
    "charts": _charts_appendix,
}


def build_analytical_sections(
    data: ReportData,
    analytics,
    *,
    requested=None,
    include_charts: bool = True,
) -> list[dict[str, Any]]:
    """Build analytical sections in canonical order.

    `requested=None` ⇒ all analytical sections (include_analytics=True with
    no explicit section curation). Otherwise only the named analytical
    sections render — respecting an explicitly curated section list.
    """
    order = ["kpi_summary", "analytical_insights", "trends", "comparisons", "charts"]
    requested = set(requested) if requested is not None else set(ANALYTICAL_BUILDERS)
    sections: list[dict[str, Any]] = []
    for name in order:
        if name == "charts" and not include_charts:
            continue
        if name not in requested or name not in ANALYTICAL_BUILDERS:
            continue
        builder = ANALYTICAL_BUILDERS.get(name)
        if builder is not None:
            sections.append(builder(data, analytics))
    return sections

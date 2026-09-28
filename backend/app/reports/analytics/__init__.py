"""Report analytics (Step 12): deterministic KPIs, trends, comparisons,
distributions, insights and frontend-friendly chart specifications over the
Step 7 structured records — plus an optional, strictly-grounded LLM
narrative layer (Step 10 provider abstraction).

The deterministic engine is authoritative; conflicts propagate as
REVIEW_REQUIRED and are never silently resolved.
"""

from app.reports.analytics.charts import generate_charts
from app.reports.analytics.engine import (
    generate_comparisons,
    generate_distributions,
    generate_kpis,
    generate_trends,
)
from app.reports.analytics.insights import generate_insights
from app.reports.analytics.models import (
    AnalyticsResult,
    ChartSeries,
    ChartSpec,
    Comparison,
    ComparisonSide,
    Distribution,
    ExcludedValue,
    Insight,
    InsightKind,
    KPI,
    Trend,
    TrendPoint,
)
from app.reports.analytics.numerics import parse_numeric
from app.reports.analytics.service import (
    audit_metadata,
    build_analytics,
    build_narrative,
    deterministic_narrative,
    validate_narrative_response,
)

__all__ = [
    "AnalyticsResult",
    "ChartSeries",
    "ChartSpec",
    "Comparison",
    "ComparisonSide",
    "Distribution",
    "ExcludedValue",
    "Insight",
    "InsightKind",
    "KPI",
    "Trend",
    "TrendPoint",
    "audit_metadata",
    "build_analytics",
    "build_narrative",
    "deterministic_narrative",
    "generate_charts",
    "generate_comparisons",
    "generate_distributions",
    "generate_insights",
    "generate_kpis",
    "generate_trends",
    "parse_numeric",
    "validate_narrative_response",
]

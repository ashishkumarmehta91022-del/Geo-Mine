"""Step 12 report analytics tests — DB-free.

Covers: KPI calculation, unsafe/non-numeric value handling, trend analysis,
missing periods, percentage-change validity, entity comparison, incompatible
units, conflict propagation, chart specifications, insight generation,
provenance preservation, deterministic output, AI-narrative unavailable/
failed/ok behavior and no-fabrication guarantees.

PostgreSQL-dependent API behavior lives in test_report_analytics_api.py and
skips honestly when the database is unavailable.
"""

import json
from decimal import Decimal

import pytest

from app.reports import RecordItem, ReportData, build_specification
from app.reports.analytics import (
    build_analytics,
    build_narrative,
    deterministic_narrative,
    generate_charts,
    generate_comparisons,
    generate_kpis,
    generate_trends,
    parse_numeric,
    validate_narrative_response,
)
from app.reports.engine import _detect_conflicts
from app.reports.service import analyze_report, generate_report


def _record(record_id, **overrides) -> RecordItem:
    defaults = dict(
        document_id=1,
        document_name="A.pdf",
        entity="Mine A",
        metric="production",
        value_raw="1000",
        normalized_value="1000",
        unit="tonnes",
        reporting_period="2024",
        extraction_method="native_text",
        validation_status="pass",
    )
    defaults.update(overrides)
    return RecordItem(record_id=record_id, **defaults)


def _data(records, spec=None, conflicts=None) -> ReportData:
    spec = spec or build_specification(title="Analytics Test")
    return ReportData(
        specification=spec,
        records=list(records),
        conflicts=_detect_conflicts(list(records)) if conflicts is None else conflicts,
        document_ids=sorted({r.document_id for r in records}),
    )


def _analytics(records, spec=None):
    return build_analytics(_data(records, spec))


def _kpi(result, name, metric=None):
    return next(
        k for k in result.kpis
        if k.name == name and (metric is None or k.metric == metric)
    )


# --- KPI engine (Phase 3) ---------------------------------------------------


def test_kpi_counts_cover_full_population():
    records = [
        _record(1),
        _record(2, entity="Mine B", validation_status="warning", value_raw="5", normalized_value="5"),
        _record(3, entity="Mine C", value_raw=None, normalized_value=None, validation_status="pending"),
    ]
    result = _analytics(records)
    assert _kpi(result, "count_records").count == 3
    assert _kpi(result, "count_validated").count == 1
    assert _kpi(result, "count_requires_review").count == 1
    assert _kpi(result, "count_missing_values").count == 1
    assert _kpi(result, "count_conflicts").count == 0


def test_kpi_aggregates_use_only_valid_numeric_values():
    records = [
        _record(1, value_raw="100", normalized_value="100"),
        _record(2, document_id=2, entity="Mine B", value_raw="300", normalized_value="300"),
        _record(3, document_id=3, entity="Mine C", value_raw="200", normalized_value="200"),
    ]
    result = _analytics(records)
    # Entities within ONE period aggregate (never summed ACROSS periods).
    assert _kpi(result, "total", "production").value == Decimal(600)
    assert _kpi(result, "average", "production").value == Decimal(200)
    assert _kpi(result, "minimum", "production").value == Decimal(100)
    assert _kpi(result, "maximum", "production").value == Decimal(300)


def test_kpi_provenance_carries_source_ids():
    records = [_record(1), _record(2, document_id=2)]
    result = _analytics(records)
    total = _kpi(result, "total", "production")
    assert sorted(total.source_record_ids) == [1, 2]
    assert sorted(total.source_document_ids) == [1, 2]


# --- unsafe / non-numeric values (Phase 3 rules) ------------------------------


def test_non_numeric_normalized_value_excluded_with_reason_raw_preserved():
    records = [
        _record(1, entity="Mine B", value_raw="1O5", normalized_value=None),
        _record(2, value_raw="100", normalized_value="100"),
    ]
    result = _analytics(records)
    total = _kpi(result, "total", "production")
    assert total.value == Decimal(100)  # only the safe value contributed
    excluded = [(e.record_id, e.reason) for e in result.excluded_values]
    assert (1, "normalized_value_not_numeric") in excluded
    assert total.excluded[0].value_raw == "1O5"  # raw preserved verbatim


def test_comma_thousands_and_units_are_not_guessed():
    assert parse_numeric("1,200") is None
    assert parse_numeric("1200 tonnes") is None
    assert parse_numeric("1e3") is None or parse_numeric("1e3") == Decimal("1e3").normalize()
    assert parse_numeric("abc") is None
    assert parse_numeric("  42 ") == Decimal(42)


def test_validation_flagged_values_never_enter_arithmetic():
    records = [
        _record(1, entity="Mine B", validation_status="error", value_raw="999", normalized_value="999"),
        _record(2, entity="Mine C", validation_status="review_required", value_raw="888", normalized_value="888"),
        _record(3, value_raw="100", normalized_value="100"),
    ]
    result = _analytics(records)
    total = _kpi(result, "total", "production")
    assert total.value == Decimal(100)
    reasons = {e.record_id: e.reason for e in result.excluded_values}
    assert reasons[1] == "validation_status_error_or_review"
    assert reasons[2] == "validation_status_error_or_review"


def test_duplicate_agreeing_records_do_not_inflate_totals():
    records = [
        _record(1, value_raw="1200", normalized_value="1200"),
        _record(2, document_id=2, value_raw="1200", normalized_value="1200"),
    ]
    result = _analytics(records)
    assert _kpi(result, "total", "production").value == Decimal(1200)  # same fact twice


def test_disagreeing_unflagged_records_are_excluded_not_averaged():
    records = [
        _record(1, value_raw="1200", normalized_value="1200"),
        _record(2, document_id=2, value_raw="1300", normalized_value="1300"),
    ]
    # conflicts=[] isolates the defensive per-cell check (normally these
    # records would already be a detected conflict at the ReportData level).
    result = build_analytics(_data(records, conflicts=[]))
    totals = [k for k in result.kpis if k.name == "total"]
    assert totals == []
    assert any(
        e.reason == "inconsistent_values_within_period" for e in result.excluded_values
    )


# --- trend analysis (Phase 4) -------------------------------------------------


def test_trend_direction_and_changes():
    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
        _record(3, document_id=3, reporting_period="2026", value_raw="150", normalized_value="150"),
    ]
    result = _analytics(records)
    trend = result.trends[0]
    assert trend.direction == "increasing"
    assert trend.absolute_change == Decimal(50)
    assert trend.percent_change == Decimal(50)
    assert trend.percent_change_valid is True
    assert [p.period for p in trend.points] == ["2024", "2025", "2026"]
    assert trend.missing_periods == []


def test_trend_decreasing_and_unchanged():
    down = _analytics([
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="80", normalized_value="80"),
    ]).trends[0]
    assert down.direction == "decreasing"
    same = _analytics([
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="100", normalized_value="100"),
    ]).trends[0]
    assert same.direction == "unchanged"
    assert same.absolute_change == Decimal(0)
    assert same.percent_change == Decimal(0)


def test_trend_missing_periods_explicitly_represented():
    records = [
        _record(1, reporting_period="2024-01", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2024-03", value_raw="120", normalized_value="120"),
    ]
    result = _analytics(records)
    trend = result.trends[0]
    assert trend.missing_periods == ["2024-02"]  # explicit gap, never interpolated


def test_percent_change_omitted_for_zero_base():
    records = [
        _record(1, reporting_period="2024", value_raw="0", normalized_value="0"),
        _record(2, document_id=2, reporting_period="2025", value_raw="100", normalized_value="100"),
    ]
    trend = _analytics(records).trends[0]
    assert trend.percent_change is None
    assert trend.percent_change_valid is False
    assert trend.absolute_change == Decimal(100)  # absolute change still valid


def test_trend_insight_language_is_descriptive_not_causal():
    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
    ]
    result = _analytics(records)
    trend_insight = next(i for i in result.insights if i.kind.value == "TREND")
    assert "increased from 100 tonnes to 120 tonnes" in trend_insight.message
    assert " because " not in trend_insight.message
    assert "efficiency" not in trend_insight.message.lower()


# --- comparison analysis (Phase 5) ---------------------------------------------


def test_entity_comparison_reports_difference_without_labels():
    records = [
        _record(1, entity="Mine A", value_raw="1200", normalized_value="1200"),
        _record(2, document_id=2, entity="Mine B", value_raw="1350", normalized_value="1350"),
    ]
    result = _analytics(records)
    comparison = result.comparisons[0]
    labels = {s.label: s.value for s in comparison.sides}
    assert labels == {"Mine A": Decimal(1200), "Mine B": Decimal(1350)}
    assert comparison.absolute_difference == Decimal(150)
    assert comparison.difference_valid is True
    messages = " ".join(i.message.lower() for i in result.insights)
    for banned in ("better", "best", "worst", "outperform", "superior"):
        assert banned not in messages


def test_incompatible_units_never_compared():
    records = [
        _record(1, unit="tonnes", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, unit="kilotonnes", value_raw="200", normalized_value="200"),
    ]
    result = _analytics(records)
    # Two separate metric/unit groups — no cross-unit difference anywhere.
    assert len(result.comparisons) == 0  # single entity per cell ⇒ no comparison
    units = {k.unit for k in result.kpis if k.name == "total"}
    assert units == {"tonnes", "kilotonnes"}


# --- conflict-aware analytics (Phase 6) ------------------------------------------


def test_conflicting_values_excluded_from_all_arithmetic():
    records = [
        _record(1, value_raw="1200", normalized_value="1200"),
        _record(2, document_id=2, value_raw="1350", normalized_value="1350"),
    ]
    result = _analytics(records)
    # Conflicting values ⇒ no aggregate KPI exists for that period at all:
    # no fake average, no winner. Both raw values are preserved on the
    # exclusions with their explicit reason.
    totals = [k for k in result.kpis if k.name == "total"]
    assert totals == []
    conflict_excluded = [
        e for e in result.excluded_values if e.reason == "conflicting_values_not_averaged"
    ]
    assert {e.value_raw for e in conflict_excluded} == {"1200", "1350"}


def test_conflict_propagates_to_trend_and_chart_status():
    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
        _record(3, document_id=3, reporting_period="2025", value_raw="125", normalized_value="125"),
    ]
    result = _analytics(records)
    trend = result.trends[0]
    assert trend.status == "review_required"
    assert [p.period for p in trend.points] == ["2024"]  # 2025 unusable
    line_chart = next(c for c in result.charts if c.chart_type == "line")
    assert line_chart.conflict_status == "review_required"
    assert "not plotted" in line_chart.note


def test_conflicted_entity_shown_as_gap_in_comparison_and_chart():
    records = [
        _record(1, entity="Mine A", value_raw="1200", normalized_value="1200"),
        _record(2, document_id=2, entity="Mine B", value_raw="1350", normalized_value="1350"),
        _record(3, document_id=3, entity="Mine C", value_raw="1400", normalized_value="1400"),
        _record(4, document_id=4, entity="Mine C", value_raw="999", normalized_value="999"),
    ]
    result = _analytics(records)
    comparison = result.comparisons[0]
    sides = {s.label: s.value for s in comparison.sides}
    assert sides["Mine C"] is None            # visible gap
    assert sides["Mine A"] == Decimal(1200)   # verified sides still compared
    chart = next(c for c in result.charts if c.chart_type == "comparison")
    points = {p["x"]: p["y"] for p in chart.series[0].points}
    assert points == {"Mine A": 1200.0, "Mine B": 1350.0, "Mine C": None}


# --- chart specifications (Phase 7) -----------------------------------------------


def test_chart_specifications_are_frontend_friendly_and_provenanced():
    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
    ]
    result = _analytics(records)
    line = next(c for c in result.charts if c.chart_type == "line")
    payload = line.to_payload()
    assert payload["chart_type"] == "line"
    assert payload["x_axis"] == "Reporting Period"
    assert payload["unit"] == "tonnes"
    assert payload["series"][0]["points"] == [
        {"x": "2024", "y": 100.0}, {"x": "2025", "y": 120.0}
    ]
    assert payload["source_record_ids"] == [1, 2]
    assert payload["conflict_status"] == "ok"
    bar = next(c for c in result.charts if c.chart_type == "bar")
    assert len(bar.series[0].points) == 5


def test_gap_periods_render_as_null_points_not_inventions():
    records = [
        _record(1, reporting_period="2024-01", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2024-03", value_raw="120", normalized_value="120"),
    ]
    result = _analytics(records)
    line = next(c for c in result.charts if c.chart_type == "line")
    points = line.series[0].points
    assert {"x": "2024-02", "y": None} in points  # explicit gap


# --- insights (Phase 9) --------------------------------------------------------------


def test_insight_types_are_deterministic_and_descriptive():
    records = [
        _record(1, value_raw="1200", normalized_value="1200"),
        _record(2, document_id=2, value_raw="1350", normalized_value="1350"),
        _record(3, document_id=3, validation_status="warning", value_raw="7", normalized_value="7"),
        _record(4, document_id=4, value_raw=None, normalized_value=None),
    ]
    result = _analytics(records)
    kinds = {i.kind.value for i in result.insights}
    assert {"CONFLICT", "VALIDATION_WARNING", "DATA_GAP"} <= kinds
    conflict = next(i for i in result.insights if i.kind.value == "CONFLICT")
    assert "Human review is required" in conflict.message
    assert "1200" in conflict.message and "1350" in conflict.message
    gap = next(i for i in result.insights if i.kind.value == "DATA_GAP")
    assert "No" in gap.message and "available" in gap.message


# --- provenance & determinism --------------------------------------------------------


def test_every_analytical_object_keeps_provenance():
    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
    ]
    result = _analytics(records)
    assert result.trends[0].source_record_ids == [1, 2]
    assert result.record_count == 2
    for kpi in result.kpis:
        assert hasattr(kpi, "source_record_ids")


def test_analytics_output_is_deterministic():
    records = [
        _record(1, reporting_period="2024"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
    ]
    first = build_analytics(_data(records)).to_payload()
    second = build_analytics(_data(records)).to_payload()
    assert first == second


# --- AI narrative (Phase 8) ------------------------------------------------------------


class _NarrativeProvider:
    """Fake provider returning a contract-valid narrative response."""

    name = "fake"
    model = "fake-narrative-v1"

    def __init__(self, text=None):
        self.text = text or json.dumps({
            "narrative": "Production increased from 100 to 120 tonnes between 2024 and 2025.",
            "summary_points": ["Production rose across the period."],
            "limitations": "Review-required items are excluded from arithmetic.",
        })
        self.calls = []

    def is_available(self):
        return True

    def generate(self, messages, *, timeout_seconds, max_output_chars):
        self.calls.append([dict(m) for m in messages])
        from app.llm.base import LLMCompletion

        return LLMCompletion(text=self.text, provider=self.name, model=self.model,
                             prompt_chars=1, completion_chars=len(self.text))


@pytest.fixture(autouse=True)
def _restore_provider():
    from app.llm.service import set_llm_provider

    set_llm_provider(None)
    yield
    set_llm_provider(None)


def test_narrative_unavailable_is_honest_and_non_fatal():
    records = [_record(1)]
    result = _analytics(records)
    outcome = build_narrative(result)
    assert outcome["state"] == "unavailable"
    assert outcome["reason"].startswith("unavailable")


def test_narrative_input_contains_only_analytical_results():
    from app.reports.analytics.service import build_narrative_messages, _compact_payload

    records = [_record(1), _record(2, value_raw="sensitive", normalized_value="120")]
    result = _analytics(records)
    context = _compact_payload(result)
    provider = _NarrativeProvider()
    from app.llm.service import set_llm_provider

    set_llm_provider(provider)
    build_narrative(result)
    user_content = provider.calls[0][1]["content"]
    # Grounded data present…
    assert "kpis" in user_content and "trends" in user_content
    # …nothing else: no document names, no question mechanism, no system text.
    assert "A.pdf" not in user_content
    system_content = provider.calls[0][0]["content"]
    assert "Never invent numbers" in system_content
    assert build_narrative_messages(context)[0]["role"] == "system"


def test_narrative_contract_validation():
    valid = json.dumps({"narrative": "n", "summary_points": ["a"], "limitations": ""})
    assert validate_narrative_response(valid)["narrative"] == "n"
    for bad in (
        "not json",
        '{"narrative": "n"}',
        '{"narrative": "n", "summary_points": ["a"], "limitations": "", "extra": 1}',
        '{"narrative": "", "summary_points": ["a"], "limitations": ""}',
        '{"narrative": "n", "summary_points": "a", "limitations": ""}',
    ):
        with pytest.raises(ValueError):
            validate_narrative_response(bad)


def test_narrative_ok_state_labels_ai_output():
    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
    ]
    result = _analytics(records)
    from app.llm.service import set_llm_provider

    provider = _NarrativeProvider()
    set_llm_provider(provider)
    outcome = build_narrative(result)
    assert outcome["state"] == "ok"
    assert outcome["provider"] == "fake"
    assert "increased from 100 to 120" in outcome["narrative"]
    assert "AI model" in outcome["notice"]


def test_narrative_contract_break_is_contained():
    records = [_record(1)]
    result = _analytics(records)
    from app.llm.service import set_llm_provider

    # MockLLMProvider speaks the Step 10 ai.query contract, NOT the narrative
    # contract — the narrative layer must degrade honestly, never crash.
    from app.llm.mock_provider import MockLLMProvider

    set_llm_provider(MockLLMProvider())
    outcome = build_narrative(result)
    assert outcome["state"] == "failed"
    assert "malformed" in outcome["reason"]


def test_deterministic_narrative_never_invents_values():
    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
    ]
    result = _analytics(records)
    narrative = deterministic_narrative(result)
    assert narrative["state"] == "deterministic"
    assert "120" in narrative["narrative"]          # real values only
    assert "999" not in narrative["narrative"]      # nothing invented
    assert "no ai involved" in narrative["limitations"].lower()


# --- report integration (Phase 10) ------------------------------------------------------


def test_generate_report_opt_in_analytics_sections_and_docx():
    import io

    from docx import Document as DocxDocument

    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
    ]
    spec = build_specification(title="Full", include_analytics=True, include_narrative=True)
    payload = generate_report(spec, data=_data(records, spec))
    assert "KPI Summary" in payload["sections_built"]
    assert "Narrative (deterministic)" in payload["sections_built"]
    assert payload["narrative_state"] == "deterministic"
    assert payload["analytics_counts"]["kpi_count"] > 0
    document = DocxDocument(io.BytesIO(payload["docx_bytes"]))
    headings = [p.text for p in document.paragraphs if p.style.name.startswith("Heading")]
    assert "KPI Summary" in headings and "Trends" in headings


def test_generate_report_without_analytics_is_unchanged_step11_behavior():
    records = [_record(1)]
    spec = build_specification(title="Plain")
    payload = generate_report(spec, data=_data(records, spec))
    assert payload["analytics"] is None
    assert payload["narrative_state"] is None
    assert "KPI Summary" not in payload["sections_built"]
    assert payload["sections_built"] == [
        "Executive Summary", "Key Figures", "Detailed Data",
        "Validation / Review Notes", "Sources / Evidence",
    ]


def test_analyze_report_returns_full_analytical_payload():
    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
        _record(3, document_id=3, entity="Mine B", value_raw="bad", normalized_value=None),
    ]
    spec = build_specification(title="Analysis", include_narrative=True)
    result = analyze_report(spec, data=_data(records, spec))
    assert result["status"] == "ok"
    assert result["record_count"] == 3
    assert result["excluded_value_count"] == 1
    assert result["kpis"] and result["trends"] and result["charts"]
    # Narrative fell back deterministically; the AI attempt is preserved honestly.
    assert result["narrative"]["state"] == "deterministic"
    assert result["narrative"]["ai_attempt"]["state"] == "unavailable"


def test_analyze_audit_payload_never_contains_values():
    from app.reports.service import analyze_audit_metadata

    records = [
        _record(1, entity="SECRET_MINE", value_raw="1,200"),
        _record(2, document_id=2, value_raw="1350"),
    ]
    spec = build_specification(title="T")
    payload = analyze_report(spec, data=_data(records, spec))
    flat = str(analyze_audit_metadata(payload))
    for secret in ("SECRET_MINE", "1,200", "1350", "A.pdf"):
        assert secret not in flat


def test_no_fabricated_numbers_anywhere_in_analytics_payload():
    records = [
        _record(1, reporting_period="2024", value_raw="100", normalized_value="100"),
        _record(2, document_id=2, reporting_period="2025", value_raw="120", normalized_value="120"),
    ]
    payload = str(build_analytics(_data(records)).to_payload())
    for fabricated in ("999", "424242", "1234567890"):
        assert fabricated not in payload

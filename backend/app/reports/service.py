"""Report generation service (Step 11) — orchestration + audit metadata.

Pipeline (fixed order, deterministic):
  1. specification built and validated (app/reports/spec.py)
  2. data collection (app/reports/engine.py — read-only over structured records)
  3. deterministic conflict detection (engine; no winner, ever)
  4. deterministic sections (app/reports/sections.py — no LLM)
  5. DOCX rendering (app/reports/docx.py)
  6. metadata-only audit row (never document contents, never values)

The generator NEVER fabricates values, NEVER silently resolves conflicts,
NEVER modifies source documents or structured records, handles missing data
explicitly, and enforces report-size limits.

Persistence: this foundation intentionally has NO report artifact model.
The DOCX bytes are returned in-memory to the API layer (single request
lifecycle) and the limitation is documented + audited — source-of-truth
data and the report artifact lifecycle stay clearly separated.
"""

import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.reports.analytics.service import (
    build_analytics,
    build_narrative,
    deterministic_narrative,
)
from app.reports.analytics_sections import (
    ANALYTICAL_BUILDERS as ANALYTICAL_SECTION_NAMES,
    build_analytical_sections,
)
from app.reports.spec import DEFAULT_SECTIONS as DEFAULT_SECTIONS_ALL
from app.reports.docx import report_filename, render_report_docx
from app.reports.engine import (
    REPORT_DATA_MISSING,
    ReportData,
    collect_report_data,
    compute_summary,
)
from app.reports.sections import build_sections
from app.reports.spec import ReportSpecification

logger = logging.getLogger(__name__)

REPORTS_ARE_NOT_PERSISTED_NOTICE = (
    "Report artifacts are generated in-memory and not persisted in this "
    "foundation step; re-generate with the same specification + data to "
    "reproduce the document (fingerprint in the filename)."
)


def generate_report(
    specification: ReportSpecification,
    *,
    data: ReportData | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Run the deterministic report pipeline and return the response payload.

    Exactly one of `data` (pre-collected, for DB-free tests) or `db` must be
    provided. The response echoes the specification, summary, conflicts,
    evidence counts, download metadata and the DOCX bytes under `docx_bytes`
    (never serialized into audit logs or JSON responses).
    """
    if (data is None) == (db is None):
        raise ValueError("generate_report requires exactly one of data= or db=.")

    if data is None:
        data = collect_report_data(db, specification)  # type: ignore[arg-type]
    else:
        # Pre-collected data (DB-free tests): summarize deterministically.
        # DB path already carries its summary; recompute is idempotent.
        data.summary = compute_summary(data)

    sections = build_sections(data)  # Step 11 deterministic sections (unchanged)
    composed: list[dict[str, Any]] | None = None  # Step 12 composed list

    # --- Step 12: optional analytical sections (opt-in, non-breaking) ----
    analytics = None
    narrative: dict[str, Any] | None = None
    if specification.include_analytics:
        analytics = build_analytics(data)
        # Default: all analytical sections. If the caller curated an explicit
        # section list, only the analytical names within it render.
        curated = (
            [s for s in specification.requested_sections if s in ANALYTICAL_SECTION_NAMES]
            if set(specification.requested_sections) != set(DEFAULT_SECTIONS_ALL)
            else None
        )
        analytical = build_analytical_sections(data, analytics, requested=curated)
        # Analytical sections follow the Executive Summary when present.
        insert_at = (
            1 if sections and sections[0].get("title") == "Executive Summary" else 0
        )
        sections = sections[:insert_at] + analytical + sections[insert_at:]

    if specification.include_narrative:
        if analytics is None:
            analytics = build_analytics(data)
        narrative = build_narrative(analytics)
        if narrative.get("state") != "ok":
            # LLM unavailable/failed ⇒ deterministic narrative remains; the
            # attempt reason is preserved honestly. Generation NEVER fails.
            fallback = deterministic_narrative(analytics)
            narrative = {**fallback, "ai_attempt": narrative}
        sections = sections + [{
            "title": (
                "Narrative (AI-generated)"
                if narrative.get("state") == "ok"
                else "Narrative (deterministic)"
            ),
            "paragraphs": [narrative.get("narrative", "")],
            "notes": [
                narrative.get("notice", ""),
                f"Limitations: {narrative.get('limitations', '')}",
            ],
            "items": ([
                {"headline": "Summary point", "lines": [point]}
                for point in narrative.get("summary_points", [])
            ] if narrative.get("state") == "ok" else []),
        }]
    if sections != build_sections(data):
        composed = sections  # analytical/narrative sections were appended
    docx_bytes = render_report_docx(data, sections=composed)
    summary = dict(data.summary)

    return {
        "status": "ok",
        "report_id": specification.report_id(),
        "fingerprint": specification.fingerprint(),
        "specification": specification.to_payload(),
        "reporting_period": specification.reporting_period,
        "generated_at": specification.generated_at,
        "artifact": {
            "format": specification.output_format,
            "filename": report_filename(specification),
            "size_bytes": len(docx_bytes),
            "download_available": False,
            "note": REPORTS_ARE_NOT_PERSISTED_NOTICE,
        },
        "summary": summary,
        "conflict_count": data.conflict_count,
        "conflicts": [conflict.to_payload() for conflict in data.conflicts],
        "evidence_count": len(data.records),
        "validation_warning_error_count": data.validation_warning_error_count,
        "missing_value_count": data.missing_value_count,
        "sections_built": [section.get("title") for section in sections],
        "narrative_state": (
            narrative.get("state") if narrative is not None else None
        ),
        "analytics_counts": (
            {
                "kpi_count": len(analytics.kpis),
                "trend_count": len(analytics.trends),
                "comparison_count": len(analytics.comparisons),
                "insight_count": len(analytics.insights),
                "chart_count": len(analytics.charts),
                "excluded_value_count": len(analytics.excluded_values),
            }
            if analytics is not None
            else None
        ),
        "analytics": analytics.to_payload() if analytics is not None else None,
        "limitations": [
            REPORTS_ARE_NOT_PERSISTED_NOTICE,
            "No LLM is used in this foundation; all values are deterministic "
            "extractions from stored structured records.",
            (
                f"Report covers at most {summary.get('record_limit')} records "
                "(deterministic order); larger selections are truncated and "
                "marked partial."
            ) if summary.get("truncated") else
            "No data was estimated or fabricated; missing values are explicit.",
        ],
        "docx_bytes": docx_bytes,
        "missing_marker": REPORT_DATA_MISSING,
    }


def analyze_report(
    specification: ReportSpecification,
    *,
    data: ReportData | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Deterministic analytics over a report selection (no DOCX artifact).

    Same data engine and conflict rules as generate_report; returns KPIs,
    trends, comparisons, distributions, insights, chart DATA specifications,
    validation/conflict summaries and provenance references. The LLM
    narrative is attempted only when the specification asks for it — and its
    unavailability never fails the deterministic result.
    """
    if (data is None) == (db is None):
        raise ValueError("analyze_report requires exactly one of data= or db=.")

    if data is None:
        data = collect_report_data(db, specification)  # type: ignore[arg-type]
    else:
        data.summary = compute_summary(data)

    analytics = build_analytics(data)
    narrative: dict[str, Any] | None = None
    if specification.include_narrative:
        narrative = build_narrative(analytics)
        if narrative.get("state") != "ok":
            narrative = {
                **deterministic_narrative(analytics),
                "ai_attempt": narrative,
            }

    return {
        "status": "ok",
        "report_id": specification.report_id(),
        "fingerprint": specification.fingerprint(),
        "specification": specification.to_payload(),
        "generated_at": specification.generated_at,
        "record_count": len(data.records),
        "document_count": len(data.document_ids),
        "conflict_count": len(data.conflicts),
        "validation_warning_error_count": analytics.validation_warning_error_count,
        "excluded_value_count": len(analytics.excluded_values),
        "kpis": [k.to_payload() for k in analytics.kpis],
        "trends": [t.to_payload() for t in analytics.trends],
        "comparisons": [c.to_payload() for c in analytics.comparisons],
        "distributions": [d.to_payload() for d in analytics.distributions],
        "insights": [i.to_payload() for i in analytics.insights],
        "charts": [c.to_payload() for c in analytics.charts],
        "excluded_values": [e.to_payload() for e in analytics.excluded_values],
        "narrative": narrative,
        "limitations": [
            "KPIs, trends, comparisons and distributions use ONLY validated, "
            "non-conflicting numeric values; excluded values are listed with "
            "their reasons and raw values are preserved.",
            "Insights are descriptive only — no causal claims are made.",
            "Percentage change is omitted when the base value is zero.",
        ],
    }


def audit_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Safe audit payload — metadata only (never values, never contents)."""
    spec_payload = payload.get("specification", {})
    summary = payload.get("summary", {})
    return {
        "status": payload.get("status"),
        "report_type": spec_payload.get("report_type"),
        "output_format": payload.get("artifact", {}).get("format"),
        "reporting_period": payload.get("reporting_period"),
        "selected_document_count": len(spec_payload.get("document_ids", []) or []),
        "selected_entity_count": len(spec_payload.get("entities", []) or []),
        "selected_metric_count": len(spec_payload.get("metrics", []) or []),
        "record_count": summary.get("record_count"),
        "conflict_count": payload.get("conflict_count"),
        "validation_warning_error_count": payload.get("validation_warning_error_count"),
        "missing_value_count": payload.get("missing_value_count"),
        "artifact_size_bytes": payload.get("artifact", {}).get("size_bytes"),
        "report_fingerprint": payload.get("fingerprint"),
    }


def analyze_audit_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Safe audit payload for the analyze endpoint — metadata only."""
    spec_payload = payload.get("specification", {})
    return {
        "status": payload.get("status"),
        "report_type": spec_payload.get("report_type"),
        "reporting_period": spec_payload.get("reporting_period"),
        "selected_document_count": len(spec_payload.get("document_ids", []) or []),
        "record_count": payload.get("record_count"),
        "document_count": payload.get("document_count"),
        "conflict_count": payload.get("conflict_count"),
        "validation_warning_error_count": payload.get("validation_warning_error_count"),
        "excluded_value_count": payload.get("excluded_value_count"),
        "kpi_count": len(payload.get("kpis", [])),
        "trend_count": len(payload.get("trends", [])),
        "comparison_count": len(payload.get("comparisons", [])),
        "insight_count": len(payload.get("insights", [])),
        "chart_count": len(payload.get("charts", [])),
        "narrative_state": (payload.get("narrative") or {}).get("state"),
        "report_fingerprint": payload.get("fingerprint"),
    }


def log_report_analysis(db: Session, payload: dict[str, Any]) -> None:
    """Append one audit row for an analysis (metadata only; never fails the call)."""
    try:
        db.add(
            AuditLog(
                action="report.analyze",
                entity_type="report",
                entity_id=None,
                details=analyze_audit_metadata(payload),
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning("Report analysis audit write failed (result unaffected)")


def log_report_generation(db: Session, payload: dict[str, Any]) -> None:
    """Append one audit row with safe metadata only.

    Never stores document contents, record values or the generated artifact;
    a failed audit write never fails the report itself (logged, rolled back).
    """
    try:
        db.add(
            AuditLog(
                action="report.generate",
                entity_type="report",
                entity_id=None,
                details=audit_metadata(payload),
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning("Report generation audit write failed (report unaffected)")

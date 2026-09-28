"""Deterministic report sections (Step 11).

Every builder consumes ONLY the collected ReportData (structured records
already stored by the system) and the specification. There is no LLM in this
layer and there is no code path that can invent a value: every string is
either fixed template text or derived from record fields (verbatim
`value_raw`, stored `normalized_value`, provenance columns).

Section model is extensible: a future builder registers a new section name
in `ReportSection` and a function in BUILDERS — existing sections and the
DOCX writer stay untouched.
"""

from typing import Any

from app.reports.engine import REPORT_DATA_MISSING, ReportData, RecordItem
from app.reports.spec import ReportSection

# Template notice attached to every generated report (prototype honesty).
PROTOTYPE_NOTICE = (
    "Prototype/demo output generated from structured records already stored "
    "by this platform. It is NOT an official CMPDI/CIL report and carries no "
    "certification. Verify every figure against its cited source document."
)


def _source_label(record: RecordItem) -> str:
    """Deterministic human-readable source trail for one record."""
    bits: list[str] = []
    if record.document_name:
        bits.append(f"{record.document_name} (doc {record.document_id})")
    else:
        bits.append(f"document {record.document_id}")
    if record.page_number is not None:
        bits.append(f"page {record.page_number}")
    elif record.page_id is not None:
        bits.append(f"page-id {record.page_id}")
    if record.source_reference:
        bits.append(str(record.source_reference))
    return " · ".join(bits)


def _value_text(record: RecordItem) -> str:
    """Raw value verbatim; unit and normalization only when stored."""
    if not record.has_value():
        return REPORT_DATA_MISSING
    text = record.value_raw if record.value_raw else record.normalized_value
    if record.unit:
        text = f"{text} {record.unit}"
    return text


def _executive_summary(data: ReportData) -> dict[str, Any]:
    """Template-only summary — every number comes from the deterministic summary."""
    s = data.summary
    spec = data.specification
    period = spec.reporting_period or "all available periods"
    scope = f"{s['document_count']} selected document(s)" if s["document_count"] else "the full structured record store"
    lines: list[str] = [
        f"This {spec.report_type} report covers {period} and was compiled "
        f"from {scope}. {s['record_count']} structured record(s) were "
        f"selected; {s['record_count'] - s['missing_value_count']} carry a "
        f"source value.",
    ]
    if s["entities"]:
        lines.append(f"Entities covered: {', '.join(s['entities'][:20])}.")
    if s["metrics"]:
        lines.append(f"Metrics covered: {', '.join(s['metrics'][:20])}.")
    if s["conflict_count"]:
        lines.append(
            f"REVIEW REQUIRED: {s['conflict_count']} conflicting value group(s) "
            f"were detected. All conflicting values are reported with their "
            f"sources; none was selected automatically."
        )
    if s["validation_warning_error_count"]:
        lines.append(
            f"{s['validation_warning_error_count']} record(s) carry a "
            f"validation warning/error/review status and must not be treated "
            f"as verified figures."
        )
    if s["pending_validation_count"]:
        lines.append(
            f"{s['pending_validation_count']} record(s) have not been "
            f"validated yet (status pending)."
        )
    if s["missing_value_count"]:
        lines.append(
            f"{s['missing_value_count']} record(s) have no stored value; they "
            f"are listed as missing information — nothing was estimated."
        )
    if s["truncated"]:
        lines.append(
            f"NOTE: the record count exceeded the report limit "
            f"({s['record_limit']}); the report covers the first "
            f"{s['record_limit']} records in deterministic order and is "
            f"therefore PARTIAL."
        )
    return {
        "title": "Executive Summary",
        "paragraphs": lines,
        "notes": [PROTOTYPE_NOTICE],
    }


def _key_figures(data: ReportData) -> dict[str, Any]:
    """Deterministic table: one row per valued record — raw value verbatim."""
    headers = ["Entity", "Metric", "Value (raw)", "Normalized", "Unit",
               "Period", "Validation", "Source"]
    rows: list[list[str]] = []
    for record in data.records:
        if not record.has_value():
            continue
        rows.append([
            record.entity or "—",
            record.metric or "—",
            record.value_raw or "—",
            record.normalized_value or "—",
            record.unit or "—",
            record.reporting_period or "—",
            record.validation_status or "—",
            _source_label(record),
        ])
    return {
        "title": "Key Figures",
        "headers": headers,
        "rows": rows,
        "empty_note": (
            "No records with stored values matched the report filters. "
            "Nothing was estimated or fabricated."
        ) if not rows else None,
    }


def _detailed_data(data: ReportData) -> dict[str, Any]:
    """Records grouped by (entity, metric, period) — deterministic order."""
    groups = data.grouped_records()
    tables: list[dict[str, Any]] = []
    for entity, metric, period, records in groups:
        headers = ["Record", "Value (raw)", "Normalized", "Unit", "Validation",
                   "Source", "Extraction"]
        rows = [
            [
                str(r.record_id),
                r.value_raw if r.value_raw else REPORT_DATA_MISSING,
                r.normalized_value or "—",
                r.unit or "—",
                r.validation_status or "—",
                _source_label(r),
                r.extraction_method or "—",
            ]
            for r in records
        ]
        label = " — ".join(part for part in (entity, metric, period) if part) or "ungrouped"
        tables.append({"caption": label, "headers": headers, "rows": rows})
    return {
        "title": "Detailed Data",
        "tables": tables,
        "empty_note": "No structured records matched the report filters." if not tables else None,
    }


def _validation_notes(data: ReportData) -> dict[str, Any]:
    """Conflict groups (REVIEW REQUIRED) + warning/error/pending records."""
    items: list[dict[str, Any]] = []
    for conflict in data.conflicts:
        lines = [
            f"{v['value_raw']}"
            + (f" (normalized: {'; '.join(n for n in v['normalized_values'] if n)})"
               if any(v["normalized_values"]) else "")
            + f" — {s['document_name'] or 'document ' + str(s['document_id'])}"
            + (f", page {s['page_number']}" if s["page_number"] is not None else "")
            + (f", {s['source_reference']}" if s["source_reference"] else "")
            + f" [record {s['record_id']}, validation: {s['validation_status'] or 'unknown'}]"
            for v in conflict.values
            for s in v["sources"]
        ]
        scope = " — ".join(
            part for part in (conflict.entity, conflict.metric,
                              conflict.reporting_period, conflict.unit) if part
        )
        items.append({
            "kind": "conflict",
            "headline": f"CONFLICT — {scope}",
            "lines": lines,
            "status": "REVIEW REQUIRED",
        })
    flagged = [r for r in data.records if r.validation_status in
               ("warning", "error", "review_required")]
    for record in flagged:
        items.append({
            "kind": "validation",
            "headline": (
                f"Validation {record.validation_status} — record "
                f"{record.record_id} ({record.entity or '?'} · "
                f"{record.metric or '?'} · value {record.value_raw or REPORT_DATA_MISSING})"
            ),
            "lines": [f"Source: {_source_label(record)}"],
            "status": record.validation_status.upper(),
        })
    if not items and not data.conflicts:
        items = [] if data.records else [{
            "kind": "info",
            "headline": "No structured records matched the report filters.",
            "lines": ["The validation section therefore has nothing to report; "
                      "no data was assumed."],
            "status": "INFO",
        }]
    return {
        "title": "Validation / Review Notes",
        "items": items,
        "review_required": bool(data.conflicts) or bool(flagged),
    }


def _sources_evidence(data: ReportData) -> dict[str, Any]:
    """Every selected record traced to document/page/record/source — no gaps."""
    headers = ["Record", "Document", "Page", "Source reference", "Extraction",
               "OCR conf.", "Validation"]
    rows = [
        [
            str(r.record_id),
            f"{r.document_name} (doc {r.document_id})" if r.document_name else f"doc {r.document_id}",
            str(r.page_number) if r.page_number is not None else ("page-id " + str(r.page_id) if r.page_id is not None else "—"),
            r.source_reference or "—",
            r.extraction_method or "—",
            f"{r.ocr_confidence:.2f}" if r.ocr_confidence is not None else "—",
            r.validation_status or "—",
        ]
        for r in data.records
    ]
    return {
        "title": "Sources / Evidence",
        "headers": headers,
        "rows": rows,
        "empty_note": (
            "No records matched; no sources can be cited. Nothing was "
            "referenced beyond the actual selection." if not rows else None
        ),
    }


# Single registration point — section name → builder (deterministic output).
BUILDERS = {
    ReportSection.EXECUTIVE_SUMMARY.value: _executive_summary,
    ReportSection.KEY_FIGURES.value: _key_figures,
    ReportSection.DETAILED_DATA.value: _detailed_data,
    ReportSection.VALIDATION_NOTES.value: _validation_notes,
    ReportSection.SOURCES_EVIDENCE.value: _sources_evidence,
}


def build_sections(data: ReportData) -> list[dict[str, Any]]:
    """Build the requested sections in canonical order (deterministic)."""
    order = [member.value for member in ReportSection]
    sections: list[dict[str, Any]] = []
    for name in order:
        if name not in data.specification.requested_sections:
            continue
        builder = BUILDERS.get(name)
        if builder is None:  # future sections registered without a builder
            sections.append({"title": name.replace("_", " ").title(),
                             "paragraphs": ["Section reserved for a future step."]})
            continue
        sections.append(builder(data))
    return sections

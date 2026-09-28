"""Automated report generation foundation (Step 11).

Deterministic, provenance-grounded DOCX reports over validated structured
records. The pipeline never fabricates values, never silently resolves
conflicts and never modifies source data.
"""

from app.reports.docx import report_filename, render_report_docx
from app.reports.engine import (
    ConflictItem,
    RecordItem,
    ReportData,
    collect_report_data,
)
from app.reports.sections import build_sections
from app.reports.service import (
    audit_metadata,
    generate_report,
    log_report_generation,
)
from app.reports.spec import (
    DEFAULT_SECTIONS,
    ReportFilters,
    ReportFormat,
    ReportSection,
    ReportSpecification,
    build_specification,
)

__all__ = [
    "ConflictItem",
    "DEFAULT_SECTIONS",
    "RecordItem",
    "ReportData",
    "ReportFilters",
    "ReportFormat",
    "ReportSection",
    "ReportSpecification",
    "audit_metadata",
    "build_sections",
    "build_specification",
    "collect_report_data",
    "generate_report",
    "log_report_generation",
    "report_filename",
    "render_report_docx",
]

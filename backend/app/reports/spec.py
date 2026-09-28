"""Typed report specification (Step 11) — deterministic, extensible.

The specification is the ONLY input the report generator accepts. Every
field is validated and bounded here so downstream stages (data engine,
sections, DOCX) can rely on a normalized, frozen contract. Nothing in this
module touches the database and nothing modifies source data.

Extensibility: new report types/templates add new section builders and (if
needed) new specification fields — the existing fields keep their meaning.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from app.exceptions import AppError

# --- bounds (report-size/context limits; env-independent by design) --------
MAX_TITLE_LENGTH = 200
MAX_REPORT_TYPE_LENGTH = 64
MAX_PERIOD_LENGTH = 64
MAX_DOCUMENT_IDS = 100
MAX_ENTITIES = 50
MAX_METRICS = 50
MAX_PERIOD_FILTERS = 24
MAX_ENTITY_LENGTH = 256
MAX_METRIC_LENGTH = 128
MAX_REPORT_RECORDS = 500  # hard cap on records pulled into one report
MAX_REQUESTER_LENGTH = 128


class ReportSection(StrEnum):
    """Initial deterministic section model (extensible)."""

    EXECUTIVE_SUMMARY = "executive_summary"
    KEY_FIGURES = "key_figures"
    DETAILED_DATA = "detailed_data"
    VALIDATION_NOTES = "validation_notes"
    SOURCES_EVIDENCE = "sources_evidence"

    @classmethod
    def values(cls) -> set[str]:
        return {member.value for member in cls}


class ReportFormat(StrEnum):
    """Output formats. DOCX first (python-docx already in the stack); PDF is
    deliberately NOT offered — no verified PDF mechanism exists yet."""

    DOCX = "docx"

    @classmethod
    def values(cls) -> set[str]:
        return {member.value for member in cls}


DEFAULT_SECTIONS: tuple[str, ...] = tuple(ReportSection.values())


@dataclass(frozen=True)
class ReportFilters:
    """Optional narrowing filters (all optional, all equality-based)."""

    validation_status: str | None = None   # pass | warning | error | review_required | pending
    extraction_method: str | None = None   # native_text | ocr | table | spreadsheet | docx
    record_type: str | None = None         # e.g. coal_production | borehole | grade

    def to_payload(self) -> dict[str, str | None]:
        return {
            "validation_status": self.validation_status,
            "extraction_method": self.extraction_method,
            "record_type": self.record_type,
        }


@dataclass(frozen=True)
class ReportSpecification:
    """Fully normalized report request (immutable once built)."""

    title: str
    report_type: str
    reporting_period: str | None
    document_ids: tuple[int, ...]
    entities: tuple[str, ...]
    metrics: tuple[str, ...]
    requested_sections: tuple[str, ...]
    output_format: str
    filters: ReportFilters = field(default_factory=ReportFilters)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    requester: str | None = None
    # Step 12: optional analytical extensions (deterministic engine is
    # authoritative; the AI narrative is an additional labeled layer).
    include_analytics: bool = False
    include_narrative: bool = False

    def to_payload(self) -> dict:
        """Canonical dict used for the fingerprint and response echo."""
        return {
            "title": self.title,
            "report_type": self.report_type,
            "reporting_period": self.reporting_period,
            "document_ids": list(self.document_ids),
            "entities": list(self.entities),
            "metrics": list(self.metrics),
            "requested_sections": list(self.requested_sections),
            "output_format": self.output_format,
            "filters": self.filters.to_payload(),
            "requester": self.requester,
            "include_analytics": self.include_analytics,
            "include_narrative": self.include_narrative,
        }

    def fingerprint(self) -> str:
        """Deterministic short fingerprint of the specification content.

        Note: `generated_at` is deliberately excluded — the fingerprint
        identifies WHAT was requested, not WHEN.
        """
        canonical = json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

    def report_id(self) -> str:
        return f"rpt-{self.fingerprint()}"


def _clean_str(value, limit: int, code: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(status_code=422, code=code, message=f"{label} must be a non-empty string.")
    cleaned = " ".join(value.split())
    if len(cleaned) > limit:
        raise AppError(
            status_code=422,
            code=code,
            message=f"{label} exceeds the {limit}-character limit.",
        )
    return cleaned


def _clean_str_list(values, limit_count: int, limit_len: int, code: str, label: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise AppError(status_code=422, code=code, message=f"{label} must be a list.")
    if len(values) > limit_count:
        raise AppError(
            status_code=422,
            code=code,
            message=f"{label} exceeds the maximum of {limit_count} entries.",
        )
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean_str(value, limit_len, code, label)
        if item not in seen:
            seen.add(item)
            cleaned.append(item)
    return tuple(cleaned)


def _clean_document_ids(values) -> tuple[int, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise AppError(status_code=422, code="invalid_document_ids", message="document_ids must be a list of ids.")
    if len(values) > MAX_DOCUMENT_IDS:
        raise AppError(
            status_code=422,
            code="too_many_document_ids",
            message=f"document_ids exceeds the maximum of {MAX_DOCUMENT_IDS}.",
        )
    ids: list[int] = []
    seen: set[int] = set()
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise AppError(
                status_code=422,
                code="invalid_document_ids",
                message="document_ids must contain positive integers.",
            )
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return tuple(ids)


def _clean_sections(values) -> tuple[str, ...]:
    if values is None or (isinstance(values, (list, tuple)) and len(values) == 0):
        return DEFAULT_SECTIONS
    if not isinstance(values, (list, tuple)):
        raise AppError(status_code=422, code="invalid_sections", message="sections must be a list of section names.")
    allowed = ReportSection.values()
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str) or value.strip() not in allowed:
            raise AppError(
                status_code=422,
                code="invalid_sections",
                message=f"Unknown section {value!r}; valid sections: {sorted(allowed)}.",
            )
        section = value.strip()
        if section not in cleaned:
            cleaned.append(section)
    return tuple(cleaned)


def _clean_filters(values) -> ReportFilters:
    if values is None:
        return ReportFilters()
    if not isinstance(values, dict):
        raise AppError(status_code=422, code="invalid_filters", message="filters must be an object.")

    def _optional(key: str, limit: int) -> str | None:
        raw = values.get(key)
        if raw is None:
            return None
        cleaned = _clean_str(raw, limit, "invalid_filters", f"filters.{key}")
        return cleaned

    return ReportFilters(
        validation_status=_optional("validation_status", 32),
        extraction_method=_optional("extraction_method", 32),
        record_type=_optional("record_type", 64),
    )


def build_specification(
    *,
    title,
    report_type=None,
    reporting_period=None,
    document_ids=None,
    entities=None,
    metrics=None,
    sections=None,
    output_format=None,
    filters=None,
    requester=None,
    generated_at=None,
    include_analytics=False,
    include_narrative=False,
) -> ReportSpecification:
    """Validate raw request fields into a frozen ReportSpecification.

    Raises AppError(422) with a specific code for every violation — the API
    layer never has to guess what went wrong.
    """
    clean_title = _clean_str(title, MAX_TITLE_LENGTH, "empty_title", "title")
    clean_type = (
        _clean_str(report_type, MAX_REPORT_TYPE_LENGTH, "invalid_report_type", "report_type")
        if report_type not in (None, "")
        else "summary"
    )
    clean_period = (
        _clean_str(reporting_period, MAX_PERIOD_LENGTH, "invalid_reporting_period", "reporting_period")
        if reporting_period not in (None, "")
        else None
    )
    clean_requester = (
        _clean_str(requester, MAX_REQUESTER_LENGTH, "invalid_requester", "requester")
        if requester not in (None, "")
        else None
    )

    fmt = output_format or ReportFormat.DOCX
    if not isinstance(fmt, str) or fmt.strip() not in ReportFormat.values():
        raise AppError(
            status_code=422,
            code="unsupported_report_format",
            message=f"output_format must be one of {sorted(ReportFormat.values())}.",
        )

    when = generated_at or datetime.now(timezone.utc)
    return ReportSpecification(
        title=clean_title,
        report_type=clean_type,
        reporting_period=clean_period,
        document_ids=_clean_document_ids(document_ids),
        entities=_clean_str_list(entities, MAX_ENTITIES, MAX_ENTITY_LENGTH, "too_many_entities", "entities"),
        metrics=_clean_str_list(metrics, MAX_METRICS, MAX_METRIC_LENGTH, "too_many_metrics", "metrics"),
        requested_sections=_clean_sections(sections),
        output_format=fmt.strip(),
        filters=_clean_filters(filters),
        generated_at=when,
        requester=clean_requester,
        include_analytics=bool(include_analytics),
        include_narrative=bool(include_narrative),
    )

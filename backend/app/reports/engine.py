"""Report data engine (Step 11) — deterministic selection over structured records.

Reads ONLY from the Step 7 source-of-truth tables (`extracted_records` +
provenance context from `documents` / `document_pages`). No new
source-of-truth table is introduced; nothing here ever writes to or modifies
source data — the engine issues SELECT statements only.

Data integrity rules (enforced by construction):
- `value_raw` passes through VERBATIM — never reformatted, never "fixed".
- `normalized_value` is the safe stored normalization (NULL when none exists).
- Every record keeps document/page/record ids, source reference, extraction
  method, validation status and OCR confidence — full provenance.
- Conflicting values are REPORTED, never resolved: both sides stay visible
  with their sources; no winner is ever selected.
- Missing data is explicit: records without values are kept and marked, and
  the summary counts them honestly.

Determinism: ordering is fully specified (entity → metric → period → record
id; conflicts ordered by first-seen raw value then record id), so identical
database content always produces byte-identical report data.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.constants import ValidationStatus
from app.exceptions import AppError, DatabaseUnavailableError
from app.models import Document, DocumentPage, ExtractedRecord
from app.reports.spec import MAX_REPORT_RECORDS, ReportSpecification

# Validation states that always surface in the review section.
REVIEW_STATUSES = (ValidationStatus.WARNING.value, ValidationStatus.ERROR.value,
                   ValidationStatus.REVIEW_REQUIRED.value)

# Explicit missing-data marker — rendered verbatim wherever a value would
# have been. It is NEVER replaced with an estimate or a default.
REPORT_DATA_MISSING = "DATA MISSING"


@dataclass(frozen=True)
class RecordItem:
    """One structured record with complete provenance (immutable)."""

    record_id: int
    document_id: int
    document_name: str | None = None
    page_id: int | None = None
    page_number: int | None = None
    source_reference: str | None = None
    record_type: str | None = None
    entity: str | None = None
    metric: str | None = None
    value_raw: str | None = None        # verbatim — never modified by the engine
    normalized_value: str | None = None
    unit: str | None = None
    reporting_period: str | None = None
    extraction_method: str | None = None
    validation_status: str | None = None
    ocr_confidence: float | None = None
    confidence: float | None = None

    def has_value(self) -> bool:
        """A record carries a reportable value when raw or normalized exists."""
        return bool(self.value_raw) or bool(self.normalized_value)

    def to_payload(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page_id": self.page_id,
            "page_number": self.page_number,
            "source_reference": self.source_reference,
            "record_type": self.record_type,
            "entity": self.entity,
            "metric": self.metric,
            "value_raw": self.value_raw,
            "normalized_value": self.normalized_value,
            "unit": self.unit,
            "reporting_period": self.reporting_period,
            "extraction_method": self.extraction_method,
            "validation_status": self.validation_status,
            "ocr_confidence": self.ocr_confidence,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ConflictItem:
    """One (entity, metric, period, unit) group with disagreeing raw values.

    No winner is ever selected: every distinct value stays listed with the
    full source trail of each side. The section is always marked REVIEW
    REQUIRED.
    """

    entity: str | None
    metric: str | None
    reporting_period: str | None
    unit: str | None
    # Ordered by first-seen raw value, then record id (deterministic).
    values: tuple[dict[str, Any], ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "metric": self.metric,
            "reporting_period": self.reporting_period,
            "unit": self.unit,
            "status": "REVIEW REQUIRED",
            "values": [dict(value) for value in self.values],
        }


@dataclass
class ReportData:
    """Everything the section builders / DOCX writer need — deterministic."""

    specification: ReportSpecification
    records: list[RecordItem] = field(default_factory=list)
    conflicts: list[ConflictItem] = field(default_factory=list)
    document_ids: list[int] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def validation_warning_error_count(self) -> int:
        return sum(
            1 for r in self.records if r.validation_status in REVIEW_STATUSES
        )

    @property
    def missing_value_count(self) -> int:
        return sum(1 for r in self.records if not r.has_value())

    def grouped_records(self) -> list[tuple[str | None, str | None, str | None, list[RecordItem]]]:
        """Deterministic grouping by (entity, metric, period).

        Group order: entity → metric → period (string sort, NULLs last);
        record order within a group follows the engine's record order.
        """
        groups: dict[tuple[str | None, str | None, str | None], list[RecordItem]] = {}
        for record in self.records:
            key = (record.entity, record.metric, record.reporting_period)
            groups.setdefault(key, []).append(record)
        return [
            (entity, metric, period, groups[key])
            for key, (entity, metric, period, *_) in (
                (key, (*key, groups[key])) for key in sorted(
                    groups,
                    key=lambda k: ((k[0] or "~"), (k[1] or "~"), (k[2] or "~")),
                )
            )
        ]

    def to_payload(self) -> dict[str, Any]:
        return {
            "records": [record.to_payload() for record in self.records],
            "conflicts": [conflict.to_payload() for conflict in self.conflicts],
            "summary": dict(self.summary),
        }


def _detect_conflicts(records: list[RecordItem]) -> list[ConflictItem]:
    """Deterministic conflict detection over valued records.

    Grouping key: (entity, metric, reporting_period, unit). Units are part of
    the key deliberately — cross-unit reconciliation would require conversion
    rules this foundation does not have, and guessing one could fabricate
    values. Distinct raw values within a group ⇒ one conflict covering every
    member. No winner, no merging, no correction.
    """
    groups: dict[tuple[str | None, str | None, str | None, str | None],
                 dict[str, list[dict[str, Any]]]] = {}
    for record in records:
        if not record.value_raw:
            continue
        key = (record.entity, record.metric, record.reporting_period, record.unit)
        entry = {
            "record_id": record.record_id,
            "document_id": record.document_id,
            "document_name": record.document_name,
            "page_number": record.page_number,
            "source_reference": record.source_reference,
            "validation_status": record.validation_status,
        }
        groups.setdefault(key, {}).setdefault(record.value_raw, []).append(entry)

    conflicts: list[ConflictItem] = []
    for key in sorted(groups, key=lambda k: tuple(part or "~" for part in k)):
        entity, metric, period, unit = key
        by_value = groups[key]
        if len(by_value) < 2:
            continue
        ordered_values = sorted(by_value, key=lambda v: by_value[v][0]["record_id"])
        values = tuple(
            {
                "value_raw": value,
                "normalized_values": _normalized_for(by_value[value]),
                "sources": by_value[value],
            }
            for value in ordered_values
        )
        conflicts.append(
            ConflictItem(
                entity=entity, metric=metric, reporting_period=period, unit=unit,
                values=values,
            )
        )
    return conflicts


def _normalized_for(entries: list[dict[str, Any]]) -> list[str | None]:
    return [entry.get("normalized_value") for entry in entries]


def collect_report_data(db: Session, specification: ReportSpecification) -> ReportData:
    """Select, order, bound and summarize the report's structured records.

    Read-only; raises DatabaseUnavailableError when PostgreSQL cannot be
    reached (honest failure — never an empty-but-successful report).
    """
    try:
        stmt = (
            select(ExtractedRecord)
            .order_by(
                ExtractedRecord.entity_name,
                ExtractedRecord.metric_name,
                ExtractedRecord.reporting_period,
                ExtractedRecord.id,
            )
            .limit(MAX_REPORT_RECORDS + 1)  # fetch one extra to detect truncation
        )
        if specification.document_ids:
            stmt = stmt.where(ExtractedRecord.document_id.in_(specification.document_ids))
        if specification.entities:
            stmt = stmt.where(ExtractedRecord.entity_name.in_(specification.entities))
        if specification.metrics:
            stmt = stmt.where(ExtractedRecord.metric_name.in_(specification.metrics))
        if specification.reporting_period:
            stmt = stmt.where(ExtractedRecord.reporting_period == specification.reporting_period)

        filters = specification.filters
        if filters.validation_status:
            stmt = stmt.where(ExtractedRecord.validation_status == filters.validation_status)
        if filters.extraction_method:
            stmt = stmt.where(ExtractedRecord.extraction_method == filters.extraction_method)
        if filters.record_type:
            stmt = stmt.where(ExtractedRecord.record_type == filters.record_type)

        rows = list(db.scalars(stmt))
        truncated = len(rows) > MAX_REPORT_RECORDS
        rows = rows[:MAX_REPORT_RECORDS]

        # --- provenance context (batched, read-only) ------------------------
        document_ids = {row.document_id for row in rows}
        filenames: dict[int, str] = {}
        if document_ids:
            filenames = dict(
                db.execute(
                    select(Document.id, Document.filename).where(Document.id.in_(document_ids))
                ).all()
            )
        page_ids = {row.page_id for row in rows if row.page_id is not None}
        page_numbers: dict[int, int] = {}
        if page_ids:
            page_numbers = dict(
                db.execute(
                    select(DocumentPage.id, DocumentPage.page_number)
                    .where(DocumentPage.id.in_(page_ids))
                ).all()
            )

        records = [
            RecordItem(
                record_id=row.id,
                document_id=row.document_id,
                document_name=filenames.get(row.document_id),
                page_id=row.page_id,
                page_number=page_numbers.get(row.page_id) if row.page_id is not None else None,
                source_reference=row.source_reference,
                record_type=row.record_type,
                entity=row.entity_name,
                metric=row.metric_name,
                value_raw=row.value_raw,
                normalized_value=row.normalized_value,
                unit=row.unit,
                reporting_period=row.reporting_period,
                extraction_method=row.extraction_method,
                validation_status=row.validation_status,
                # ExtractedRecord carries a single extraction confidence
                # (Numeric 5,4); OCR-derived confidence lives on
                # document_pages.ocr metadata, not on records.
                ocr_confidence=None,
                confidence=float(row.confidence) if row.confidence is not None else None,
            )
            for row in rows
        ]
    except DatabaseUnavailableError:
        raise
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500,
            code="database_error",
            message="Could not collect report data from the structured records.",
        ) from exc

    conflicts = _detect_conflicts(records)

    data = ReportData(
        specification=specification,
        records=records,
        conflicts=conflicts,
        document_ids=sorted(document_ids),
        summary={},
    )
    data.summary = compute_summary(data, truncated=truncated)
    return data


def compute_summary(data: ReportData, *, truncated: bool = False) -> dict[str, Any]:
    """Deterministic summary over the collected records (shared by the DB
    path and the pre-collected/DB-free path)."""
    records = data.records
    return {
        "record_count": len(records),
        "document_count": len({r.document_id for r in records}),
        "conflict_count": len(data.conflicts),
        "validation_warning_error_count": data.validation_warning_error_count,
        "pending_validation_count": sum(
            1 for r in records if r.validation_status == "pending"
        ),
        "missing_value_count": data.missing_value_count,
        "entities": sorted({r.entity for r in records if r.entity}),
        "metrics": sorted({r.metric for r in records if r.metric}),
        "reporting_periods": sorted(
            {r.reporting_period for r in records if r.reporting_period}
        ),
        "record_limit": MAX_REPORT_RECORDS,
        "truncated": truncated,
    }

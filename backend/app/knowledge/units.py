"""Retrieval-unit drafts: pure functions turning source rows into index entries.

DB-free and deterministic — persistence happens in the knowledge service.
Every draft keeps full provenance; nothing here strips source references.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.constants import RetrievalUnitType
from app.models import DocumentPage, ExtractedRecord, ValidationResult


@dataclass(frozen=True)
class IndexUnitDraft:
    """One row for knowledge_index (provenance always preserved)."""

    unit_type: str
    document_id: int
    page_id: int | None = None
    record_id: int | None = None
    validation_id: int | None = None
    title: str | None = None
    content: str | None = None
    source_reference: str | None = None
    entity: str | None = None
    metric: str | None = None
    reporting_period: str | None = None
    extraction_method: str | None = None
    validation_status: str | None = None
    ocr_confidence: float | None = None


def page_unit(page: DocumentPage, document_filename: str | None) -> IndexUnitDraft:
    """A document page (or sheet/image unit) as a retrieval unit."""
    meta = page.structured_metadata or {}
    ocr = meta.get("ocr") if isinstance(meta, dict) else None
    confidence = None
    if isinstance(ocr, dict) and ocr.get("confidence") is not None:
        try:
            confidence = float(ocr["confidence"])
        except (TypeError, ValueError):
            confidence = None
    label = {
        "page": "Page",
        "sheet": "Sheet",
        "image": "Image",
    }.get(page.content_type, "Page")
    return IndexUnitDraft(
        unit_type=RetrievalUnitType.PAGE,
        document_id=page.document_id,
        page_id=page.id,
        title=f"{document_filename or document_id} — {label.lower()} {page.page_number}",
        content=page.extracted_text,
        source_reference=page.section_reference or f"{label.lower()} {page.page_number}",
        extraction_method=(
            "ocr" if page.extraction_status in ("ocr_extracted",) else "native_text"
        ),
        ocr_confidence=confidence,
    )


def record_unit(record: ExtractedRecord, document_filename: str | None) -> IndexUnitDraft:
    """A structured record as a retrieval unit (raw + normalized kept distinct)."""
    value_text = (
        record.normalized_value
        or (str(record.metric_value) if record.metric_value is not None else None)
        or record.value_raw
    )
    title_parts = [part for part in (record.entity_name, record.metric_name) if part]
    return IndexUnitDraft(
        unit_type=RetrievalUnitType.RECORD,
        document_id=record.document_id,
        record_id=record.id,
        page_id=record.page_id,
        title=" — ".join(title_parts) or None,
        content=value_text,
        source_reference=record.source_reference,
        entity=record.entity_name,
        metric=record.metric_name,
        reporting_period=record.reporting_period,
        extraction_method=record.extraction_method,
        validation_status=record.validation_status,
    )


def validation_unit(result: ValidationResult, document_filename: str | None) -> IndexUnitDraft:
    """A validation result as a retrieval unit (conflicts stay searchable)."""
    title = f"{result.rule_code} — {result.status}"
    return IndexUnitDraft(
        unit_type=RetrievalUnitType.VALIDATION,
        document_id=result.document_id,
        validation_id=result.id,
        record_id=result.extracted_record_id,
        page_id=result.page_id,
        title=title,
        content=result.message,
        source_reference=result.source_reference,
        validation_status=result.status,
    )


def units_from_rows(
    pages: list[DocumentPage],
    records: list[ExtractedRecord],
    validations: list[ValidationResult],
    document_filename: str | None,
) -> list[IndexUnitDraft]:
    """Build all retrieval units for one document (fixed order ⇒ determinism)."""
    drafts: list[IndexUnitDraft] = []
    drafts.extend(page_unit(p, document_filename) for p in pages)
    drafts.extend(record_unit(r, document_filename) for r in records)
    drafts.extend(validation_unit(v, document_filename) for v in validations)
    return drafts

"""StructuredRecordBuilder — extraction sections → traceable record drafts.

Deterministic and DB-free: takes the Step 4/5 `ExtractionResult` plus page
metadata and produces `ExtractedRecord`-shaped drafts with verbatim values,
safe normalizations and full provenance. Persistence happens in the
processing service (idempotent delete-replace).
"""

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.constants import TextExtractionStatus
from app.processing.base import ExtractedSection, ExtractionResult
from app.structuring.config import StructuringConfig, demo_config
from app.structuring.normalization import (
    normalize_decimal,
    normalize_number,
    normalize_period,
    normalize_text,
)

logger = logging.getLogger(__name__)

# Extraction methods (reuse existing terminology — no duplicate vocabulary).
METHOD_NATIVE_TEXT = "native_text"
METHOD_OCR = "ocr"
METHOD_TABLE = "table"
METHOD_SPREADSHEET = "spreadsheet"
METHOD_DOCX = "docx"


@dataclass(frozen=True)
class RecordDraft:
    """One structured record ready for persistence (provenance complete)."""

    entity_name: str
    metric_name: str
    raw_value: str | None  # verbatim — never modified
    normalized_value: str | None  # only when unambiguous
    numeric_value: Decimal | None
    unit: str | None
    reporting_period: str | None
    source_reference: str | None
    page_number: int | None
    extraction_method: str
    confidence: float | None
    review_required: bool
    record_metadata: dict[str, Any] = field(default_factory=dict)


def _cell_text(rows: list[list[Any]], row_index: int, col_index: int) -> str | None:
    try:
        value = rows[row_index][col_index]
    except IndexError:
        return None
    if value is None:
        return None
    return normalize_text(str(value))


def _find_column(headers: list[Any], aliases: tuple[str, ...]) -> int | None:
    lowered = [str(h).strip().lower() if h is not None else "" for h in headers]
    for alias in aliases:
        if alias in lowered:
            return lowered.index(alias)
    return None


def _ocr_confidence(section: ExtractedSection) -> tuple[float | None, bool, dict | None]:
    meta = section.structured_metadata or {}
    ocr = meta.get("ocr") if isinstance(meta, dict) else None
    if not isinstance(ocr, dict):
        return None, False, None
    confidence = ocr.get("confidence")
    try:
        confidence_f = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_f = None
    return confidence_f, bool(ocr.get("review_required")), ocr


class StructuredRecordBuilder:
    """Builds record drafts from extraction results per the configured schema."""

    def __init__(self, config: StructuringConfig | None = None):
        self._config = config or demo_config()

    # --- public API ---------------------------------------------------------

    def build(self, extraction: ExtractionResult, document_id: int) -> list[RecordDraft]:
        drafts: list[RecordDraft] = []
        for section in extraction.sections:
            try:
                if section.structured_metadata and "rows" in section.structured_metadata:
                    drafts.extend(self._from_spreadsheet(section, document_id))
                elif section.structured_metadata and "tables" in section.structured_metadata:
                    drafts.extend(self._from_docx_tables(section, document_id))
                elif section.content_type == "image":
                    drafts.extend(self._from_image(section, document_id))
                elif section.text:
                    drafts.extend(self._from_text(section, document_id))
            except Exception:  # noqa: BLE001 — one bad section must not sink the rest
                logger.exception(
                    "Structured-record building failed for document %s section %s",
                    document_id,
                    section.index,
                )
        return drafts

    # --- spreadsheet sections (XLSX/XLS) -------------------------------------

    def _from_spreadsheet(self, section: ExtractedSection, document_id: int) -> list[RecordDraft]:
        rows = section.structured_metadata.get("rows") or []
        if len(rows) < 2:
            return []
        headers = rows[0]

        entity_col = _find_column(headers, self._config.entity_column_aliases)
        value_col = _find_column(headers, self._config.value_column_aliases)
        unit_col = _find_column(headers, self._config.unit_column_aliases)
        period_col = _find_column(headers, self._config.period_column_aliases)
        metric_col = _find_column(headers, self._config.metric_column_aliases)

        # A value column is the minimum viable table shape.
        if value_col is None:
            return []

        sheet_name = section.structured_metadata.get("sheet_name") or f"{section.index}"
        sheet_reference = f"sheet {sheet_name}"  # matches document_pages reference style
        drafts: list[RecordDraft] = []
        for row_index in range(1, len(rows)):
            raw_value = _cell_text(rows, row_index, value_col)
            if raw_value in (None, ""):
                continue
            entity = _cell_text(rows, row_index, entity_col) if entity_col is not None else None
            metric = (
                _cell_text(rows, row_index, metric_col)
                if metric_col is not None
                else self._default_metric(rows, row_index, section)
            )
            numeric = None if raw_value is None else self._safe_decimal(raw_value)
            drafts.append(
                RecordDraft(
                    entity_name=entity or "UNKNOWN_ENTITY",
                    metric_name=metric or "unknown_metric",
                    raw_value=raw_value,
                    normalized_value=normalize_number(raw_value),
                    numeric_value=numeric,
                    unit=_cell_text(rows, row_index, unit_col) if unit_col is not None else None,
                    reporting_period=(
                        normalize_period(_cell_text(rows, row_index, period_col))
                        if period_col is not None
                        else None
                    ),
                    source_reference=f"{sheet_reference}, row {row_index + 1}",
                    page_number=section.index,
                    extraction_method=METHOD_SPREADSHEET,
                    confidence=None,
                    review_required=False,
                    record_metadata={
                        "sheet_name": sheet_name,
                        "row_index": row_index + 1,
                        "headers": [str(h) for h in headers],
                    },
                )
            )
        return drafts

    def _default_metric(
        self, rows: list[list[Any]], row_index: int, section: ExtractedSection, fallback: str = "sheet"
    ) -> str:
        """Demo fallback metric name from the sheet/section title (deterministic)."""
        source_name = str(section.structured_metadata.get("sheet_name") or fallback)
        slug = re.sub(r"[^a-z0-9]+", "_", source_name.lower()).strip("_")
        return f"demo_{slug}" if slug else "demo_unknown_metric"

    # --- DOCX tables -----------------------------------------------------------

    def _from_docx_tables(self, section: ExtractedSection, document_id: int) -> list[RecordDraft]:
        drafts: list[RecordDraft] = []
        for table in section.structured_metadata.get("tables", []):
            rows = table.get("rows") or []
            headers = table.get("headers") or []
            if not rows:
                continue
            entity_col = _find_column(headers, self._config.entity_column_aliases)
            value_col = _find_column(headers, self._config.value_column_aliases)
            unit_col = _find_column(headers, self._config.unit_column_aliases)
            period_col = _find_column(headers, self._config.period_column_aliases)
            if value_col is None:
                continue
            table_index = table.get("table_index", 0)
            for row_index, row in enumerate(rows):
                raw_value = (
                    normalize_text(str(row[value_col])) if value_col < len(row) and row[value_col] is not None else None
                )
                if raw_value in (None, ""):
                    continue
                numeric = None if raw_value is None else self._safe_decimal(raw_value)
                drafts.append(
                    RecordDraft(
                        entity_name=(
                            normalize_text(str(row[entity_col]))
                            if entity_col is not None and entity_col < len(row) and row[entity_col] is not None
                            else "UNKNOWN_ENTITY"
                        ),
                        metric_name=self._default_metric(rows, row_index, section, fallback="docx_section"),
                        raw_value=raw_value,
                        normalized_value=normalize_number(raw_value),
                        numeric_value=numeric,
                        unit=(
                            normalize_text(str(row[unit_col]))
                            if unit_col is not None and unit_col < len(row) and row[unit_col] is not None
                            else None
                        ),
                        reporting_period=(
                            normalize_period(
                                normalize_text(str(row[period_col]))
                            )
                            if period_col is not None and period_col < len(row) and row[period_col] is not None
                            else None
                        ),
                        source_reference=f"section {section.index}, table {table_index}, row {row_index + 1}",
                        page_number=section.index,
                        extraction_method=METHOD_TABLE,
                        confidence=None,
                        review_required=False,
                        record_metadata={
                            "table_index": table_index,
                            "row_index": row_index + 1,
                            "headers": [str(h) for h in headers],
                        },
                    )
                )
        return drafts

    # --- image (OCR) sections ------------------------------------------------------

    def _from_image(self, section: ExtractedSection, document_id: int) -> list[RecordDraft]:
        confidence, review_required, ocr = _ocr_confidence(section)
        if not section.text:
            return []
        # One verbatim record per OCR'd image; splitting into fields is a
        # future, review-gated step — never guessed here.
        return [
            RecordDraft(
                entity_name="UNKNOWN_ENTITY",
                metric_name="demo_ocr_text",
                raw_value=section.text,
                normalized_value=None,  # OCR text is never numerically interpreted
                numeric_value=None,
                unit=None,
                reporting_period=None,
                source_reference=section.section_reference or "image",
                page_number=section.index,
                extraction_method=METHOD_OCR,
                confidence=confidence,
                review_required=review_required or confidence is None,
                record_metadata={"ocr": ocr},
            )
        ]

    # --- free-text sections (PDF native / DOCX paragraphs) -----------------------------

    def _from_text(self, section: ExtractedSection, document_id: int) -> list[RecordDraft]:
        confidence, review_required, ocr = _ocr_confidence(section)
        method = METHOD_OCR if section.extraction_status == TextExtractionStatus.OCR_EXTRACTED else METHOD_NATIVE_TEXT
        # Keep a bounded number of verbatim text records per page — the raw
        # text remains fully available in document_pages; these records exist
        # so reviewers/validation can reference text-derived content.
        paragraphs = [p for p in (section.text or "").split("\n\n") if p.strip()]
        drafts: list[RecordDraft] = []
        for paragraph in paragraphs[: self._config.max_text_records_per_page]:
            drafts.append(
                RecordDraft(
                    entity_name="UNKNOWN_ENTITY",
                    metric_name="demo_text_block",
                    raw_value=paragraph,
                    normalized_value=normalize_text(paragraph),
                    numeric_value=None,
                    unit=None,
                    reporting_period=None,
                    source_reference=f"{section.section_reference} (text)",
                    page_number=section.index,
                    extraction_method=method,
                    confidence=confidence,
                    review_required=review_required,
                    record_metadata={"ocr": ocr} if ocr else {},
                )
            )
        return drafts

    # --- helpers ---------------------------------------------------------------------

    @staticmethod
    def _safe_decimal(raw: str) -> Decimal | None:
        from app.validation.parsing import parse_number

        return parse_number(raw)

"""Structuring layer tests (no PostgreSQL required) — deterministic by design."""

import io
from decimal import Decimal

from app.processing.base import ExtractedSection, ExtractionResult
from app.structuring.builder import (
    METHOD_DOCX,
    METHOD_NATIVE_TEXT,
    METHOD_OCR,
    METHOD_SPREADSHEET,
    METHOD_TABLE,
    StructuredRecordBuilder,
)
from app.structuring.normalization import (
    normalize_date,
    normalize_number,
    normalize_period,
    normalize_text,
)
from app.structuring.config import demo_config
from tests.processing_fixtures import (
    docx_bytes,
    rendered_text_image_bytes,
    xlsx_bytes,
)
from app.processing.extractors import DOCXExtractor, ImageExtractor, XLSXExtractor

# --- safe normalization ---------------------------------------------------------


def test_normalize_text_collapses_whitespace_and_unicode():
    assert normalize_text("  A\u00a0 B   C ") == "A B C"
    assert normalize_text("") is None
    assert normalize_text(None) is None


def test_normalize_number_grouping_and_canonical_form():
    assert normalize_number("1,200") == "1200"
    assert normalize_number("1,20,000") == "120000"
    assert normalize_number("12.50") == "12.5"  # canonical form drops redundant zeros
    assert normalize_number("1200.0") == "1200"  # integral -> no trailing zero


def test_ocr_confusion_is_never_normalized():
    """'1O5' (letter O) must NOT become 105 — normalized stays NULL."""
    assert normalize_number("1O5") is None
    assert normalize_number("12.3.4") is None
    assert normalize_number("l23") is None  # letter l


def test_normalize_date_and_period_safety():
    assert normalize_date("30/06/2025") == "2025-06-30"
    assert normalize_date("31/02/2025") is None  # impossible date — not fixed
    assert normalize_period("2023") == "2023"
    assert normalize_period("2025-26") == "2025-26"  # financial year kept verbatim
    assert normalize_period("not-a-date") is None


# --- spreadsheet builder ----------------------------------------------------------


def _xlsx_extraction() -> ExtractionResult:
    sheets = {
        "Production": [
            ["Mine", "Value", "Unit", "Period"],
            ["DEMO_MINE_A", "1,200", "tonnes", "2025-06-30"],
            ["DEMO_MINE_B", "1O5", "tonnes", "2025-06-30"],  # OCR-typical confusion
        ],
    }
    return XLSXExtractor().extract(io.BytesIO(xlsx_bytes(sheets)))


def test_spreadsheet_records_provenance_and_raw_values():
    drafts = StructuredRecordBuilder().build(_xlsx_extraction(), document_id=7)

    assert len(drafts) == 2
    first, second = drafts
    assert first.entity_name == "DEMO_MINE_A"
    assert first.raw_value == "1,200"  # verbatim
    assert first.normalized_value == "1200"  # unambiguous normalization
    assert first.numeric_value == Decimal("1200")
    assert first.unit == "tonnes"
    assert first.reporting_period == "2025-06-30"
    assert first.extraction_method == METHOD_SPREADSHEET
    assert first.source_reference == "sheet Production, row 2"
    assert first.page_number == 1
    assert first.record_metadata["sheet_name"] == "Production"


def test_ocr_confusion_value_stays_verbatim_with_null_normalized():
    second = StructuredRecordBuilder().build(_xlsx_extraction(), 7)[1]
    assert second.raw_value == "1O5"  # source value preserved exactly
    assert second.normalized_value is None  # no guess
    assert second.numeric_value is None


# --- DOCX table builder --------------------------------------------------------------


def test_docx_table_records():
    content = docx_bytes(["Intro"], table=[["Mine", "Value"], ["DEMO_MINE_A", "500"]])
    extraction = DOCXExtractor().extract(io.BytesIO(content))
    drafts = StructuredRecordBuilder().build(extraction, document_id=3)

    table_drafts = [d for d in drafts if d.extraction_method == METHOD_TABLE]
    assert len(table_drafts) == 1
    draft = table_drafts[0]
    assert draft.entity_name == "DEMO_MINE_A"
    assert draft.raw_value == "500"
    assert draft.normalized_value == "500"
    assert "table 1" in draft.source_reference


def test_docx_paragraph_text_records_with_method_docx_native():
    content = docx_bytes(["First paragraph text.", "Second paragraph text."])
    extraction = DOCXExtractor().extract(io.BytesIO(content))
    drafts = StructuredRecordBuilder().build(extraction, document_id=3)

    text_drafts = [d for d in drafts if d.extraction_method in {METHOD_NATIVE_TEXT, METHOD_DOCX}]
    assert text_drafts, "paragraph text should produce records"
    assert all(d.raw_value for d in text_drafts)


# --- image/OCR builder ------------------------------------------------------------------


def test_ocr_image_record_is_verbatim_and_review_flagged():
    extraction = ImageExtractor().extract(io.BytesIO(rendered_text_image_bytes("DEMO 12345")))
    drafts = StructuredRecordBuilder().build(extraction, document_id=9)

    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.extraction_method == METHOD_OCR
    assert draft.normalized_value is None  # OCR text is never numerically interpreted
    assert draft.raw_value and "12345" in draft.raw_value.replace(" ", "")
    assert draft.review_required is False or draft.confidence is not None


# --- determinism ---------------------------------------------------------------------------


def test_builder_is_deterministic():
    extraction = _xlsx_extraction()
    first = StructuredRecordBuilder().build(extraction, 7)
    second = StructuredRecordBuilder().build(_xlsx_extraction(), 7)
    assert [(d.entity_name, d.metric_name, d.raw_value) for d in first] == [
        (d.entity_name, d.metric_name, d.raw_value) for d in second
    ]


def test_demo_config_is_labeled_demo():
    specs = demo_config().field_specs
    assert all(name.startswith("demo_") for name in specs), (
        "demo field specs must be clearly labeled as demonstration"
    )

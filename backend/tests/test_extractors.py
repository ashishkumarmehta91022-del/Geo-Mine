"""Extractor unit tests (no PostgreSQL required) — deterministic extraction."""

import io
from datetime import datetime

import pytest

from app.constants import PageContentType, TextExtractionStatus
from app.processing.base import package_version
from app.processing.extractors import (
    DOCXExtractor,
    ImageExtractor,
    PDFExtractor,
    XLSExtractor,
    XLSXExtractor,
)
from app.processing.normalization import normalize_text
from app.processing.registry import get_extractor
from tests.processing_fixtures import (
    corrupted_docx_bytes,
    corrupted_pdf_bytes,
    corrupted_xlsx_bytes,
    docx_bytes,
    jpeg_bytes,
    pdf_bytes,
    png_bytes,
    xls_bytes,
    xlsx_bytes,
)


def _buf(data: bytes) -> io.BytesIO:
    return io.BytesIO(data)


# --- registry ------------------------------------------------------------------

def test_registry_maps_extensions_to_extractors():
    assert isinstance(get_extractor(extension=".pdf", document_type=None), PDFExtractor)
    assert isinstance(get_extractor(extension=".docx", document_type=None), DOCXExtractor)
    assert isinstance(get_extractor(extension=".xlsx", document_type=None), XLSXExtractor)
    assert isinstance(get_extractor(extension=".xls", document_type=None), XLSExtractor)
    assert isinstance(get_extractor(extension=".png", document_type=None), ImageExtractor)
    assert isinstance(get_extractor(extension=".jpg", document_type=None), ImageExtractor)
    assert isinstance(get_extractor(extension=None, document_type="pdf"), PDFExtractor)


def test_registry_rejects_unknown():
    with pytest.raises(LookupError):
        get_extractor(extension=".rtf", document_type=None)


def test_extractor_versions_are_recorded():
    assert PDFExtractor().version == package_version("pymupdf")
    assert DOCXExtractor().version == package_version("python-docx")
    assert XLSXExtractor().version == package_version("openpyxl")
    assert XLSExtractor().version == package_version("xlrd")
    assert ImageExtractor().version == package_version("pillow")


# --- normalization ----------------------------------------------------------------


def test_normalization_preserves_meaning_and_structure():
    raw = "Line one\r\nLine  two   spaced\r\r\n\n\n\nLast \x00line"
    normalized = normalize_text(raw)
    lines = normalized.split("\n")
    assert lines[0] == "Line one"
    assert lines[1] == "Line two spaced"  # space runs collapsed
    assert lines[-1] == "Last line"  # null removed
    assert lines.count("") == 1  # 4 blank lines collapsed to exactly one


def test_normalization_keeps_tabs_in_sheet_text():
    assert normalize_text("A\tB\tC") == "A\tB\tC"


# --- PDF extractor --------------------------------------------------------------------


def test_pdf_multipage_extraction_in_order():
    pages = ["Page one content", "Page two content", "Page three content"]
    result = PDFExtractor().extract(_buf(pdf_bytes(pages)))

    assert [s.index for s in result.sections] == [1, 2, 3]
    assert all(s.content_type == PageContentType.PAGE for s in result.sections)
    assert "Page one" in result.sections[0].text
    assert "Page three" in result.sections[2].text
    assert all(s.extraction_status == TextExtractionStatus.EXTRACTED for s in result.sections)
    assert result.aggregate_text_status == TextExtractionStatus.EXTRACTED
    assert result.extractor_name == "pymupdf+ocr"  # Step 5: native path unchanged, OCR for scanned pages
    assert result.extractor_version == package_version("pymupdf")


def test_pdf_without_text_layer_reports_no_text():
    result = PDFExtractor().extract(_buf(pdf_bytes(["", ""])))  # two empty pages
    assert len(result.sections) == 2
    assert all(s.extraction_status == TextExtractionStatus.NO_TEXT for s in result.sections)
    assert all(s.text is None for s in result.sections)  # nothing invented
    assert result.aggregate_text_status == TextExtractionStatus.NO_TEXT


def test_pdf_mixed_pages_report_mixed():
    result = PDFExtractor().extract(_buf(pdf_bytes(["real text", ""])))
    assert result.sections[0].extraction_status == TextExtractionStatus.EXTRACTED
    assert result.sections[1].extraction_status == TextExtractionStatus.NO_TEXT
    assert result.aggregate_text_status == "mixed"


def test_corrupted_pdf_fails_loudly():
    with pytest.raises(Exception):
        PDFExtractor().extract(_buf(corrupted_pdf_bytes()))


# --- DOCX extractor ---------------------------------------------------------------------


def test_docx_paragraphs_in_order():
    result = DOCXExtractor().extract(_buf(docx_bytes(["First paragraph", "Second paragraph"])))
    assert len(result.sections) == 1
    text = result.sections[0].text
    assert "First paragraph" in text and "Second paragraph" in text
    assert result.sections[0].extraction_status == TextExtractionStatus.EXTRACTED


def test_docx_table_structure_preserved():
    table = [["Mine", "Year"], ["DEMO_MINE_A", "2025"], ["DEMO_MINE_B", "2026"]]
    result = DOCXExtractor().extract(_buf(docx_bytes(["Intro paragraph"], table=table)))

    table_sections = [s for s in result.sections if s.structured_metadata]
    assert len(table_sections) == 1
    structured = table_sections[0].structured_metadata["tables"][0]
    assert structured["headers"] == ["Mine", "Year"]
    assert structured["rows"] == [["DEMO_MINE_A", "2025"], ["DEMO_MINE_B", "2026"]]
    assert "table 1" in table_sections[0].section_reference


def test_docx_reading_order_paragraphs_then_table():
    table = [["A", "B"], ["1", "2"]]
    result = DOCXExtractor().extract(_buf(docx_bytes(["Before the table"], table=table)))
    refs = [s.section_reference for s in result.sections]
    assert refs.index("section 1") < refs.index("section 2, table 1")


def test_corrupted_docx_fails_loudly():
    with pytest.raises(Exception):
        DOCXExtractor().extract(_buf(corrupted_docx_bytes()))


# --- XLSX extractor -----------------------------------------------------------------------


def test_xlsx_multi_sheet_extraction():
    sheets = {
        "Production": [["Mine", "Year", "Tonnes"], ["DEMO_MINE_A", 2025, 120000]],
        "Summary": [["Total", 120000]],
    }
    result = XLSXExtractor().extract(_buf(xlsx_bytes(sheets)))

    assert [s.index for s in result.sections] == [1, 2]
    assert [s.section_reference for s in result.sections] == ["sheet Production", "sheet Summary"]
    assert all(s.content_type == PageContentType.SHEET for s in result.sections)
    assert result.aggregate_text_status == TextExtractionStatus.EXTRACTED


def test_xlsx_preserves_cell_types():
    rows = [
        ["text", 42, 3.14, True, None],
        ["date", datetime(2026, 3, 15, 10, 30, 0)],
    ]
    result = XLSXExtractor().extract(_buf(xlsx_bytes({"Data": rows})))
    extracted_rows = result.sections[0].structured_metadata["rows"]

    assert extracted_rows[0][0] == "text"  # str stays str
    assert extracted_rows[0][1] == 42 and isinstance(extracted_rows[0][1], int)  # int stays int
    assert extracted_rows[0][2] == 3.14  # float stays float
    assert extracted_rows[0][3] is True  # bool stays bool
    assert extracted_rows[0][4] is None  # empty stays None
    assert extracted_rows[1][1] == "2026-03-15T10:30:00"  # date → ISO 8601


def test_xlsx_empty_sheet_reports_no_text():
    result = XLSXExtractor().extract(_buf(xlsx_bytes({"Empty": [[]]})))
    assert result.sections[0].extraction_status == TextExtractionStatus.NO_TEXT
    assert result.sections[0].structured_metadata["rows"] == []


def test_corrupted_xlsx_fails_loudly():
    with pytest.raises(Exception):
        XLSXExtractor().extract(_buf(corrupted_xlsx_bytes()))


# --- XLS extractor ------------------------------------------------------------------------


def test_xls_multi_sheet_extraction():
    sheets = {"Prod": [["Mine", "Tonnes"], ["DEMO_MINE_A", 120000]]}
    result = XLSExtractor().extract(_buf(xls_bytes(sheets)))
    assert result.sections[0].section_reference == "sheet Prod"
    assert result.sections[0].structured_metadata["rows"][1][1] == 120000.0
    assert result.aggregate_text_status == TextExtractionStatus.EXTRACTED


# --- image extractor -------------------------------------------------------------------------


def test_image_ocr_path_reports_honestly():
    """Blank image: engine runs, finds no text, and reports that honestly
    (ocr_required only when the engine is unavailable in the environment)."""
    result = ImageExtractor().extract(_buf(png_bytes(120, 80)))
    assert len(result.sections) == 1
    section = result.sections[0]
    assert section.extraction_status in {
        TextExtractionStatus.NO_TEXT,  # engine ran, nothing detected
        TextExtractionStatus.OCR_REQUIRED,  # engine unavailable in this environment
    }
    assert section.text is None  # no invented text
    ocr_meta = section.structured_metadata.get("ocr") or {}
    if section.extraction_status == TextExtractionStatus.NO_TEXT:
        assert ocr_meta.get("engine") == "rapidocr-onnxruntime"  # provenance recorded
        assert ocr_meta.get("engine_version")
    assert result.aggregate_text_status == section.extraction_status


def test_jpeg_also_handled():
    result = ImageExtractor().extract(_buf(jpeg_bytes()))
    assert result.sections[0].structured_metadata["format"] == "JPEG"

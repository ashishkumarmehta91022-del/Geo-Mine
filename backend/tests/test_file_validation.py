"""Validation and storage tests that do NOT require PostgreSQL."""

import pytest

from app.exceptions import FileTooLargeError, InvalidFileError
from app.utils.file_validation import (
    ALL_ALLOWED_EXTENSIONS,
    sanitize_filename,
    validate_upload,
)

# --- filename sanitization -------------------------------------------------

def test_sanitize_strips_path_traversal():
    assert sanitize_filename("../../etc/report.pdf") == "report.pdf"
    assert sanitize_filename("..\\..\\windows\\report.pdf") == "report.pdf"


def test_sanitize_strips_absolute_paths_and_drives():
    assert sanitize_filename("C:\\Users\\evil\\report.pdf") == "report.pdf"
    assert sanitize_filename("/var/tmp/report.pdf") == "report.pdf"


def test_sanitize_rejects_null_bytes_and_empty():
    with pytest.raises(InvalidFileError):
        sanitize_filename("evil\x00.pdf")
    with pytest.raises(InvalidFileError):
        sanitize_filename("")
    with pytest.raises(InvalidFileError):
        sanitize_filename(None)


def test_sanitize_rejects_dot_names():
    with pytest.raises(InvalidFileError):
        sanitize_filename("..")


# --- extension / MIME policy -------------------------------------------------

def test_allowlist_contains_exactly_the_supported_types():
    assert ALL_ALLOWED_EXTENSIONS == {".pdf", ".docx", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"}


def test_unsupported_extension_rejected():
    with pytest.raises(InvalidFileError, match="Unsupported file type"):
        validate_upload(
            raw_filename="malware.txt",
            declared_content_type="text/plain",
            size_bytes=10,
            max_size_bytes=1024,
            head=b"hello",
        )


def test_misdeclared_mime_rejected():
    with pytest.raises(InvalidFileError, match="content type"):
        validate_upload(
            raw_filename="report.pdf",
            declared_content_type="text/html",  # not acceptable for any category
            size_bytes=10,
            max_size_bytes=1024,
            head=b"%PDF-1.7 rest",
        )


# --- content signatures --------------------------------------------------------

VALID_PDF = b"%PDF-1.7\n" + b"1" * 64
VALID_PNG = b"\x89PNG\r\n\x1a\n" + b"2" * 64
VALID_JPEG = b"\xff\xd8\xff\xe0" + b"3" * 64
# Minimal ZIP header followed by a mandatory OOXML part name.
VALID_DOCX = b"PK\x03\x04" + b"[Content_Types].xml...word/document.xml" + b"4" * 64
VALID_XLSX = b"PK\x03\x04" + b"[Content_Types].xml...xl/workbook.xml" + b"5" * 64


def _validate(name, mime, head, size=1024, max_size=1024 * 1024):
    return validate_upload(
        raw_filename=name,
        declared_content_type=mime,
        size_bytes=size,
        max_size_bytes=max_size,
        head=head,
    )


def test_valid_signatures_accepted():
    assert _validate("r.pdf", "application/pdf", VALID_PDF).document_type == "pdf"
    assert _validate("r.png", "image/png", VALID_PNG).document_type == "image"
    assert _validate("r.jpg", "image/jpeg", VALID_JPEG).document_type == "image"
    assert _validate("r.docx", None, VALID_DOCX).document_type == "docx"
    assert _validate("r.xlsx", None, VALID_XLSX).document_type == "xlsx"


def test_pdf_with_wrong_signature_rejected():
    with pytest.raises(InvalidFileError, match="PDF"):
        _validate("fake.pdf", "application/pdf", b"not a pdf at all")


def test_png_with_jpeg_signature_rejected():
    with pytest.raises(InvalidFileError, match="PNG"):
        _validate("fake.png", "image/png", VALID_JPEG)


def test_docx_without_office_entry_rejected():
    renamed_zip = b"PK\x03\x04" + b"random/stuff.txt" + b"6" * 64
    with pytest.raises(InvalidFileError, match="Office"):
        _validate("fake.docx", None, renamed_zip)


def test_xlsx_missing_spreadsheet_entry_rejected():
    docx_as_xlsx = b"PK\x03\x04" + b"word/document.xml" + b"7" * 64
    with pytest.raises(InvalidFileError, match="xl/"):
        _validate("fake.xlsx", None, docx_as_xlsx)


# --- size limits -------------------------------------------------------------

def test_oversized_file_rejected():
    with pytest.raises(FileTooLargeError):
        validate_upload(
            raw_filename="big.pdf",
            declared_content_type="application/pdf",
            size_bytes=26 * 1024 * 1024,
            max_size_bytes=25 * 1024 * 1024,
            head=VALID_PDF,
        )


def test_exact_limit_accepted():
    result = _validate("r.pdf", "application/pdf", VALID_PDF, size=1024, max_size=1024)
    assert result.original_filename == "r.pdf"

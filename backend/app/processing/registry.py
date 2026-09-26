"""Extractor registry: extension/type -> extractor (no if/elif pipelines).

New formats are added by registering an extractor here — the processing
service never changes.
"""

from app.processing.base import DocumentExtractor
from app.processing.extractors import (
    DOCXExtractor,
    ImageExtractor,
    PDFExtractor,
    XLSExtractor,
    XLSXExtractor,
)

# Lowercased extension (with dot) -> extractor instance.
_BY_EXTENSION: dict[str, DocumentExtractor] = {}
# Canonical document_type -> extractor instance (fallback when no extension exists).
_BY_TYPE: dict[str, DocumentExtractor] = {}


def register_extractor(extractor: DocumentExtractor, *, extensions: set[str], document_types: set[str]) -> None:
    for extension in extensions:
        _BY_EXTENSION[extension.lower()] = extractor
    for document_type in document_types:
        _BY_TYPE[document_type] = extractor


register_extractor(PDFExtractor(), extensions={".pdf"}, document_types={"pdf"})
register_extractor(DOCXExtractor(), extensions={".docx"}, document_types={"docx"})
register_extractor(XLSXExtractor(), extensions={".xlsx"}, document_types=set())
register_extractor(XLSExtractor(), extensions={".xls"}, document_types=set())
register_extractor(ImageExtractor(), extensions={".png", ".jpg", ".jpeg"}, document_types={"image"})
# The "xlsx" category covers both spreadsheet extensions; the exact extractor
# is chosen by extension when available.
_BY_TYPE["xlsx"] = XLSXExtractor()


def get_extractor(*, extension: str | None, document_type: str | None) -> DocumentExtractor:
    """Pick the extractor for a document. Raises LookupError when unsupported."""
    if extension:
        extractor = _BY_EXTENSION.get(extension.lower())
        if extractor is not None:
            return extractor
    if document_type:
        extractor = _BY_TYPE.get(document_type)
        if extractor is not None:
            return extractor
    raise LookupError(f"No extractor registered for extension={extension!r}, type={document_type!r}")

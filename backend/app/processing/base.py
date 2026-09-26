"""Extractor abstraction.

`DocumentExtractor.extract(file) -> ExtractionResult` — every section carries
its source reference and honest extraction status so downstream layers
(validation, AI, reports) can trace any piece back to its origin.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from typing import Any, BinaryIO

from app.constants import TextExtractionStatus


def package_version(package_name: str) -> str:
    """Actual installed package version — recorded for reproducibility."""
    try:
        return version(package_name)
    except PackageNotFoundError:  # pragma: no cover — only when packaging breaks
        return "unknown"


@dataclass
class ExtractedSection:
    """One extraction unit: PDF page, DOCX section, spreadsheet sheet, or image."""

    index: int  # 1-based position within the document
    content_type: str  # constants.PageContentType: page | sheet | image
    section_reference: str | None  # human-readable source pointer
    text: str | None  # normalized text (None/empty when no text exists)
    extraction_status: str  # constants.TextExtractionStatus
    structured_metadata: dict[str, Any] | None = None  # typed rows, tables, image info
    error_message: str | None = None


@dataclass
class ExtractionResult:
    sections: list[ExtractedSection] = field(default_factory=list)
    extractor_name: str = ""
    extractor_version: str = ""

    @property
    def aggregate_text_status(self) -> str:
        """Honest aggregate across units: extracted | no_text | ocr_required | mixed."""
        statuses = {section.extraction_status for section in self.sections}
        if not statuses or statuses == {TextExtractionStatus.NO_TEXT}:
            return TextExtractionStatus.NO_TEXT
        if statuses == {TextExtractionStatus.EXTRACTED}:
            return TextExtractionStatus.EXTRACTED
        if statuses == {TextExtractionStatus.OCR_REQUIRED}:
            return TextExtractionStatus.OCR_REQUIRED
        return "mixed"


class DocumentExtractor(ABC):
    """Interface every extractor implements. Stateless — safe as singletons."""

    name: str = ""
    version: str = ""

    @abstractmethod
    def extract(self, file: BinaryIO) -> ExtractionResult:
        """Extract content from a binary stream. Raises on unreadable files."""

"""Centralized platform constants — single source of truth for status values.

Document lifecycle (Step 4):

    uploaded -> processing -> processed
                     |
                     +--> failed

`queued` is defined for future async workers but is not set by any
current code path.
"""

from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"  # reserved for future async processing
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

    @classmethod
    def values(cls) -> set[str]:
        return {member.value for member in cls}


class TextExtractionStatus(StrEnum):
    """Per-page text outcome — honest about what extraction achieved."""

    EXTRACTED = "extracted"  # native text layer present (PDF/DOCX)
    OCR_EXTRACTED = "ocr_extracted"  # text recovered via OCR (Step 5)
    NO_TEXT = "no_text"  # valid file, but neither text layer nor OCR found text
    OCR_REQUIRED = "ocr_required"  # OCR could not run (engine unavailable) — future step
    FAILED = "failed"  # extractor could not read this unit

    @classmethod
    def values(cls) -> set[str]:
        return {member.value for member in cls}


class PageContentType(StrEnum):
    PAGE = "page"
    SHEET = "sheet"
    IMAGE = "image"

    @classmethod
    def values(cls) -> set[str]:
        return {member.value for member in cls}

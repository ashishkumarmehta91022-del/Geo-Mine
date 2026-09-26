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

    EXTRACTED = "extracted"  # meaningful text present
    NO_TEXT = "no_text"  # valid file, but no text layer (future: OCR)
    OCR_REQUIRED = "ocr_required"  # images always need the future OCR step
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

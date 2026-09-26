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


class ValidationStatus(StrEnum):
    """Deterministic validation outcomes.

    pass            — value satisfies the rule.
    warning         — value is unusual but not necessarily invalid.
    error           — value violates a deterministic rule.
    review_required — the system cannot safely decide; a human must inspect
                      the source. Uncertain data is never auto-promoted to valid.
    """

    PASS = "pass"
    WARNING = "warning"
    ERROR = "error"
    REVIEW_REQUIRED = "review_required"

    @classmethod
    def values(cls) -> set[str]:
        return {member.value for member in cls}


class ValidationSeverity(StrEnum):
    """Severity ladder — ordinary data-quality issues must not be inflated.

    info     — notable, no action required.
    warning  — unusual; worth checking.
    error    — violates a configured deterministic rule.
    critical — reserved for rules that explicitly declare it.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @classmethod
    def values(cls) -> set[str]:
        return {member.value for member in cls}


class ReviewStatus(StrEnum):
    """Human review workflow states for validation results."""

    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"

    @classmethod
    def values(cls) -> set[str]:
        return {member.value for member in cls}

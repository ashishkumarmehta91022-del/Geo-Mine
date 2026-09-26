"""OCR service layer: engine access, availability and policy helpers."""

from app.processing.ocr.base import (
    OCR_PACKAGE_NAME,
    OcrBoundingBox,
    OcrEngine,
    OcrResult,
    OcrUnavailableError,
    package_version,
)
from app.processing.ocr.rapidocr_engine import RapidOcrEngine

# Default engine instance (lazy — models load on first OCR call, not at import).
_default_engine: OcrEngine | None = None


def get_ocr_engine() -> OcrEngine:
    """Return the process-wide OCR engine (created on first call)."""
    global _default_engine
    if _default_engine is None:
        _default_engine = RapidOcrEngine()
    return _default_engine


def set_ocr_engine(engine: OcrEngine | None) -> None:
    """Replace the default engine (used by tests to inject fakes)."""
    global _default_engine
    _default_engine = engine


def ocr_engine_available() -> bool:
    """Whether the configured OCR engine can be imported in this environment.

    Deliberately does NOT instantiate the engine — availability means the
    package exists; model loading stays lazy.
    """
    return package_version(OCR_PACKAGE_NAME) != "unknown"


__all__ = [
    "OCR_PACKAGE_NAME",
    "OcrBoundingBox",
    "OcrEngine",
    "OcrResult",
    "OcrUnavailableError",
    "get_ocr_engine",
    "set_ocr_engine",
    "ocr_engine_available",
    "package_version",
]

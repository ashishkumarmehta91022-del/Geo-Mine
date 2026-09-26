"""OCR package: engines, models and service (Step 5)."""

from app.processing.ocr.base import (
    OCR_PACKAGE_NAME,
    OcrBoundingBox,
    OcrEngine,
    OcrResult,
    OcrUnavailableError,
    package_version,
)
from app.processing.ocr.rapidocr_engine import RapidOcrEngine
from app.processing.ocr.service import (
    get_ocr_engine,
    ocr_engine_available,
    set_ocr_engine,
)

__all__ = [
    "OCR_PACKAGE_NAME",
    "OcrBoundingBox",
    "OcrEngine",
    "OcrResult",
    "OcrUnavailableError",
    "RapidOcrEngine",
    "get_ocr_engine",
    "set_ocr_engine",
    "ocr_engine_available",
    "package_version",
]

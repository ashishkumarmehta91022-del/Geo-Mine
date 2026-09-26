"""OCR pipeline helper shared by extractors.

Bridges the OCR engine layer and the extraction layer: renders/fetches image
bytes go in, an honest (status, text, metadata) tuple comes out. Text is
preserved verbatim — this module never alters detected characters.
"""

import logging

from app.config import settings
from app.constants import TextExtractionStatus
from app.processing.ocr.base import OcrResult, OcrUnavailableError
from app.processing.ocr.service import get_ocr_engine, ocr_engine_available

logger = logging.getLogger(__name__)

# Cap stored boxes per page so a pathological image cannot bloat the JSONB row.
MAX_BOXES_STORED = 200


class OcrProcessingError(RuntimeError):
    """OCR ran into an engine failure — surfaced honestly to callers."""


def _result_to_metadata(result: OcrResult) -> dict:
    boxes = result.bounding_boxes[:MAX_BOXES_STORED]
    return {
        "engine": result.engine_metadata.get("engine"),
        "engine_version": result.engine_metadata.get("engine_version"),
        "confidence": result.confidence,
        "review_required": result.review_required,
        "low_confidence_count": len(result.low_confidence_boxes),
        "confidence_threshold": result.engine_metadata.get("confidence_threshold"),
        "bounding_boxes": [
            {
                "text": box.text,
                "x1": box.x1,
                "y1": box.y1,
                "x2": box.x2,
                "y2": box.y2,
                "confidence": box.confidence,
            }
            for box in boxes
        ],
        "bounding_boxes_truncated": len(result.bounding_boxes) > MAX_BOXES_STORED,
    }


def ocr_image_bytes(image_bytes: bytes) -> tuple[str, str | None, dict | None]:
    """Run OCR over encoded image bytes.

    Returns (extraction_status, text, ocr_metadata):
      - OCR_EXTRACTED: text found (verbatim; review_required flag inside metadata)
      - NO_TEXT: engine ran fine but detected nothing
      - FAILED: engine failure (metadata carries the error message)

    Never raises for engine problems — failures are a status, so one bad
    page can be isolated by the caller. Text is never modified.
    """
    if not ocr_engine_available():
        return (
            TextExtractionStatus.OCR_REQUIRED,
            None,
            {"error": "OCR engine not available in this environment."},
        )

    try:
        result = get_ocr_engine().extract(image_bytes)
    except OcrUnavailableError as exc:
        return TextExtractionStatus.OCR_REQUIRED, None, {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 — engine failures become honest status
        logger.warning("OCR failed on an image unit: %s", exc.__class__.__name__)
        return (
            TextExtractionStatus.FAILED,
            None,
            {"error": f"{exc.__class__.__name__}: {exc}"},
        )

    metadata = _result_to_metadata(result)
    if result.text.strip():
        return TextExtractionStatus.OCR_EXTRACTED, result.text, metadata
    return TextExtractionStatus.NO_TEXT, None, metadata

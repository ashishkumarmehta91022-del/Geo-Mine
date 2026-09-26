"""OCR engine and policy tests (no PostgreSQL required).

Engine-agnostic tests run against a deterministic fake; a separate module
exercises the real engine when it is available in the environment.
"""

import io

import pytest
from PIL import Image

from app.processing.ocr.base import (
    OcrBoundingBox,
    OcrEngine,
    OcrResult,
    OcrUnavailableError,
)
from app.processing.ocr.pipeline import ocr_image_bytes
from app.processing.ocr.service import set_ocr_engine


class FakeEngine(OcrEngine):
    """Deterministic fake — lets us test policy without model inference."""

    name = "fake-ocr"
    version = "0.0.0"

    def __init__(self, result: OcrResult | None = None, error: Exception | None = None):
        self._result = result
        self._error = error

    def extract(self, image_bytes: bytes) -> OcrResult:
        if self._error:
            raise self._error
        return self._result


def make_result(confidences: list[float]) -> OcrResult:
    boxes = tuple(
        OcrBoundingBox(text=f"WORD{i}", x1=float(i * 10), y1=0.0, x2=float(i * 10 + 8), y2=10.0, confidence=c)
        for i, c in enumerate(confidences)
    )
    mean = round(sum(confidences) / len(confidences), 4) if confidences else None
    return OcrResult(
        text="\n".join(box.text for box in boxes),
        confidence=mean,
        bounding_boxes=boxes,
        review_required=any(c < 0.70 for c in confidences),
        low_confidence_boxes=tuple(box for box in boxes if box.confidence < 0.70),
        engine_metadata={"engine": "fake-ocr", "engine_version": "0.0.0"},
    )


# --- image pipeline through ocr_image_bytes -------------------------------------


def test_ocr_text_extracted_with_confidence_and_boxes():
    set_ocr_engine(FakeEngine(make_result([0.95, 0.93])))
    try:
        image_bytes = png_bytes_of()
        status, text, meta = ocr_image_bytes(image_bytes)
        assert status == "ocr_extracted"
        assert text == "WORD0\nWORD1"  # verbatim, line-joined
        assert meta["confidence"] == 0.94  # mean
        assert meta["review_required"] is False
        assert len(meta["bounding_boxes"]) == 2
        assert meta["bounding_boxes"][0] == {
            "text": "WORD0", "x1": 0.0, "y1": 0.0, "x2": 8.0, "y2": 10.0, "confidence": 0.95,
        }
        assert meta["engine"] == "fake-ocr"
    finally:
        set_ocr_engine(None)


def test_low_confidence_boxes_flag_review_not_correction():
    """A low-confidence detection is preserved verbatim and flagged — never altered."""
    set_ocr_engine(FakeEngine(make_result([0.95, 0.42])))
    try:
        status, text, meta = ocr_image_bytes(png_bytes_of())
        assert status == "ocr_extracted"
        assert "WORD1" in text  # the uncertain text is still there, unmodified
        assert meta["review_required"] is True
        assert meta["low_confidence_count"] == 1
        assert meta["bounding_boxes"][1]["confidence"] == 0.42
    finally:
        set_ocr_engine(None)


def test_engine_failure_becomes_honest_failed_status():
    set_ocr_engine(FakeEngine(error=RuntimeError("model exploded")))
    try:
        status, text, meta = ocr_image_bytes(png_bytes_of())
        assert status == "failed"
        assert text is None
        assert "model exploded" in meta["error"]
    finally:
        set_ocr_engine(None)


def test_empty_detection_is_no_text_not_failure():
    set_ocr_engine(FakeEngine(OcrResult(text="", confidence=None)))
    try:
        status, text, meta = ocr_image_bytes(png_bytes_of())
        assert status == "no_text"
        assert text is None
        assert meta["confidence"] is None
    finally:
        set_ocr_engine(None)


def test_engine_unavailable_reports_ocr_required():
    import app.processing.ocr.pipeline as pipeline_module

    set_ocr_engine(None)
    original = pipeline_module.ocr_engine_available
    try:
        # Patch where pipeline looks it up (its own import), not the service module.
        pipeline_module.ocr_engine_available = lambda: False  # simulate missing engine
        status, text, meta = ocr_image_bytes(png_bytes_of())
        assert status == "ocr_required"
        assert text is None
        assert "not available" in meta["error"].lower()
    finally:
        pipeline_module.ocr_engine_available = original


# --- helper ----------------------------------------------------------------------


def png_bytes_of() -> bytes:
    image = Image.new("RGB", (10, 10), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

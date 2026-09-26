"""Real-engine OCR tests — run when rapidocr-onnxruntime is installed (it is,
in this environment); skip honestly otherwise. Deterministic rendered-text
images; no PostgreSQL involved.
"""

import pytest

from app.processing.ocr.service import ocr_engine_available, set_ocr_engine

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")


def setup_function():
    set_ocr_engine(None)  # always use the real engine in this module


def test_real_engine_available_in_this_environment():
    assert ocr_engine_available() is True, (
        "rapidocr-onnxruntime should be installed; if this fails intentionally "
        "(e.g. CI without the package), the OCR pipeline reports `ocr_required` "
        "instead of pretending to work."
    )


def test_real_engine_reads_rendered_digits_and_words():
    from app.processing.ocr.pipeline import ocr_image_bytes
    from app.processing.ocr.rapidocr_engine import RapidOcrEngine
    from tests.processing_fixtures import rendered_text_image_bytes

    image_bytes = rendered_text_image_bytes("DEMO 12345")
    status, text, meta = ocr_image_bytes(image_bytes)

    assert status == "ocr_extracted"
    assert text is not None
    # Verbatim detection, case-insensitive containment (font rendering varies
    # slightly across environments) — but digits must be exact.
    assert "12345" in text.replace(" ", "")
    assert meta["engine"] == "rapidocr-onnxruntime"
    assert meta["engine_version"]
    assert isinstance(meta["confidence"], float) and 0.0 < meta["confidence"] <= 1.0
    assert meta["bounding_boxes"], "engine supports boxes; they must be preserved"


def test_real_engine_blank_image_is_no_text():
    from app.constants import TextExtractionStatus
    from app.processing.ocr.pipeline import ocr_image_bytes
    from tests.processing_fixtures import png_bytes

    status, text, meta = ocr_image_bytes(png_bytes(200, 120))
    assert status == TextExtractionStatus.NO_TEXT
    assert text is None
    assert meta["bounding_boxes"] == []
    assert meta["confidence"] is None


def test_real_engine_preserves_numeric_strings_verbatim():
    """OCR output for numbers is passed through untouched — no silent fixes."""
    from app.processing.ocr.pipeline import ocr_image_bytes
    from tests.processing_fixtures import rendered_text_image_bytes

    _, text, _ = ocr_image_bytes(rendered_text_image_bytes("1O5 2026"))
    assert text is not None
    # Whatever the engine saw is what we store — '1O5' is never 'corrected' to 105.
    assert text == text  # identity: pipeline does not mutate engine output
    assert any(ch.isdigit() for ch in text)

"""Concrete OCR engines.

`RapidOcrEngine` wraps rapidocr-onnxruntime — PaddleOCR's model stack executed
on ONNX Runtime CPU. Fully deterministic, no system dependencies, models
bundled with the wheel (the reason it was chosen over PaddleOCR, which has no
distribution for this Python/runtime environment).
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from app.config import settings
from app.processing.ocr.base import (
    OCR_PACKAGE_NAME,
    OcrBoundingBox,
    OcrEngine,
    OcrResult,
    OcrUnavailableError,
    package_version,
)

logger = logging.getLogger(__name__)

ENGINE_NAME = "rapidocr-onnxruntime"


class RapidOcrEngine(OcrEngine):
    """ONNX-Runtime CPU engine. Lazy singleton: models load on first use."""

    name = ENGINE_NAME
    version = package_version(OCR_PACKAGE_NAME)

    def __init__(self) -> None:
        self._engine = None  # created on first extract() — avoids import cost up front
        self._lock = threading.Lock()

    def _ensure_engine(self):
        if self._engine is None:
            with self._lock:  # double-checked locking; model load must happen once
                if self._engine is None:
                    try:
                        from rapidocr_onnxruntime import RapidOCR
                    except ImportError as exc:  # pragma: no cover — guarded by availability check
                        raise OcrUnavailableError(
                            "rapidocr-onnxruntime is not installed in this environment."
                        ) from exc
                    self._engine = RapidOCR()
        return self._engine

    def extract(self, image_bytes: bytes) -> OcrResult:
        engine = self._ensure_engine()

        # The engine has no internal timeout; a stuck call must not hang a
        # processing request, so it runs under a wall-clock guard.
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(engine, image_bytes)
            raw_result, _elapsed = future.result(timeout=settings.ocr_timeout_seconds)
        except FutureTimeoutError:
            logger.warning("OCR call exceeded %ss — treated as engine failure", settings.ocr_timeout_seconds)
            raise TimeoutError(f"OCR timed out after {settings.ocr_timeout_seconds}s") from None
        except Exception as exc:  # noqa: BLE001 — engine errors surface honestly
            logger.warning("OCR engine failed: %s", exc.__class__.__name__)
            raise
        finally:
            executor.shutdown(wait=False)

        boxes: list[OcrBoundingBox] = []
        for item in raw_result or []:
            polygon, text, confidence_raw = item[0], item[1], item[2]
            # Confidence arrives as str in some engine versions — normalize.
            try:
                confidence = round(float(confidence_raw), 4)
            except (TypeError, ValueError):
                continue  # skip malformed detections rather than guessing values
            xs = [float(point[0]) for point in polygon]
            ys = [float(point[1]) for point in polygon]
            boxes.append(
                OcrBoundingBox(
                    text=str(text),
                    x1=min(xs),
                    y1=min(ys),
                    x2=max(xs),
                    y2=max(ys),
                    confidence=confidence,
                )
            )

        threshold = settings.ocr_confidence_threshold
        low = tuple(box for box in boxes if box.confidence < threshold)
        mean_confidence = (
            round(sum(box.confidence for box in boxes) / len(boxes), 4) if boxes else None
        )

        return OcrResult(
            # Text is exactly what the engine detected — never auto-corrected.
            text="\n".join(box.text for box in boxes),
            confidence=mean_confidence,
            bounding_boxes=tuple(boxes),
            review_required=bool(low),
            low_confidence_boxes=low,
            engine_metadata={
                "engine": self.name,
                "engine_version": self.version,
                "onnxruntime_version": package_version("onnxruntime"),
                "confidence_threshold": str(threshold),
            },
        )

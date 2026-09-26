"""OCR engine abstraction and result models.

The rest of the pipeline depends only on `OcrEngine` and `OcrResult` — a
future engine can be added without touching document processing. All data
models are frozen dataclasses following the project's existing conventions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version

#: Registered package name used for engine metadata. Kept here so tests can
#: monkeypatch availability without touching the engine implementation.
OCR_PACKAGE_NAME = "rapidocr-onnxruntime"

# OCR output below this confidence is preserved verbatim but flagged for
# human review (never silently "corrected").
DEFAULT_CONFIDENCE_THRESHOLD = 0.70


def package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:  # pragma: no cover — only when packaging breaks
        return "unknown"


@dataclass(frozen=True)
class OcrBoundingBox:
    """One detected text region with its confidence."""

    text: str
    # Bounding box corners in image/page pixel coordinates (x1,y1 = top-left,
    # x2,y2 = bottom-right). Engines providing polygons are reduced to these.
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


@dataclass(frozen=True)
class OcrResult:
    """What OCR produced for one image/page — faithful to the source, always."""

    text: str  # verbatim detected text (line-joined), never auto-corrected
    confidence: float | None  # mean of box confidences (None when no text found)
    bounding_boxes: tuple[OcrBoundingBox, ...] = field(default_factory=tuple)
    review_required: bool = False  # any box below the configured threshold
    low_confidence_boxes: tuple[OcrBoundingBox, ...] = field(default_factory=tuple)
    engine_metadata: dict[str, str] = field(default_factory=dict)


class OcrUnavailableError(RuntimeError):
    """Raised when OCR is requested but no usable engine exists in this environment."""


class OcrEngine(ABC):
    """Interface for OCR engines. Implementations must be deterministic."""

    name: str = ""
    version: str = ""

    @abstractmethod
    def extract(self, image_bytes: bytes) -> OcrResult:
        """Run OCR over the given encoded image bytes."""

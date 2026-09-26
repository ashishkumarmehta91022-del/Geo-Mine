"""Image extractor — OCR for PNG/JPG/JPEG (Step 5).

The original bytes are read exactly once; Pillow validation uses fresh
buffers so stream positions can never corrupt the OCR input. Reports
honestly: verbatim detected text, confidence, bounding boxes and a
`review_required` flag for low-confidence boxes. Never invents or
"corrects" OCR text.
"""

import io
from typing import Any

from app.config import settings
from app.constants import PageContentType, TextExtractionStatus
from app.processing.base import (
    DocumentExtractor,
    ExtractedSection,
    ExtractionResult,
    package_version,
)
from app.processing.ocr.pipeline import ocr_image_bytes

EXTRACTOR_NAME = "pillow+ocr"


class ImageExtractor(DocumentExtractor):
    name = EXTRACTOR_NAME
    version = package_version("pillow")  # base loader; OCR engine version lives in metadata

    def extract(self, file) -> ExtractionResult:
        from PIL import Image, UnidentifiedImageError

        result = ExtractionResult(
            extractor_name=self.name, extractor_version=self.version
        )

        data = file.read()  # single read; PIL and the OCR engine get identical bytes

        # --- structural validation on a fresh buffer ---
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
        except UnidentifiedImageError as exc:
            raise ValueError("File is not a recognizable image.") from exc
        except Exception as exc:  # noqa: BLE001 — corrupted images fail loudly
            raise ValueError(f"Image could not be validated: {exc.__class__.__name__}") from exc

        # --- metadata + guardrails on another fresh buffer ---
        try:
            with Image.open(io.BytesIO(data)) as image:
                pixels = image.width * image.height
                if pixels < 1:
                    raise ValueError("Image has invalid dimensions.")
                if pixels > settings.ocr_max_image_pixels:
                    raise ValueError(
                        f"Image too large for OCR ({image.width}x{image.height}); "
                        f"limit is {settings.ocr_max_image_pixels} pixels."
                    )
                image_metadata: dict[str, Any] = {
                    "format": image.format,
                    "mode": image.mode,
                    "width": image.width,
                    "height": image.height,
                }
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Image could not be read: {exc.__class__.__name__}") from exc

        # --- OCR on the untouched original bytes ---
        status, text, ocr_meta = ocr_image_bytes(data)

        result.sections.append(
            ExtractedSection(
                index=1,
                content_type=PageContentType.IMAGE,
                section_reference="image",
                text=text,
                extraction_status=status,
                structured_metadata={**image_metadata, "ocr": ocr_meta},
                error_message=(
                    ocr_meta.get("error")
                    if isinstance(ocr_meta, dict) and ocr_meta.get("error")
                    else None
                ),
            )
        )
        return result

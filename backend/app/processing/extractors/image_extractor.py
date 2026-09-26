"""Image extractor — Pillow metadata only, OCR explicitly out of scope (Step 4).

Validates the image opens, records width/height/format/mode, and marks text
extraction as `ocr_required`. No text is ever invented.
"""

from app.constants import PageContentType, TextExtractionStatus
from app.processing.base import (
    DocumentExtractor,
    ExtractedSection,
    ExtractionResult,
    package_version,
)

EXTRACTOR_NAME = "pillow"


class ImageExtractor(DocumentExtractor):
    name = EXTRACTOR_NAME
    version = package_version("pillow")

    def extract(self, file) -> ExtractionResult:
        from PIL import Image  # local import: Pillow is only needed for images

        result = ExtractionResult(
            extractor_name=self.name, extractor_version=self.version
        )

        with Image.open(file) as image:
            image.verify()  # structural integrity check (stream position irrelevant after)

        file.seek(0)
        with Image.open(file) as image:
            metadata = {
                "format": image.format,
                "mode": image.mode,
                "width": image.width,
                "height": image.height,
            }

        result.sections.append(
            ExtractedSection(
                index=1,
                content_type=PageContentType.IMAGE,
                section_reference="image",
                text=None,  # never invent text
                extraction_status=TextExtractionStatus.OCR_REQUIRED,
                structured_metadata=metadata,
            )
        )
        return result

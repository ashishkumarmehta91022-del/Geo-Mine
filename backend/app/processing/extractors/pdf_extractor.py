"""PDF extractor — PyMuPDF, page-by-page (never loads a whole PDF into memory).

Text layer honestly reported: pages without a text layer are marked
`no_text` (future OCR pipeline), never faked.
"""

import pymupdf

from app.constants import PageContentType, TextExtractionStatus
from app.processing.base import (
    DocumentExtractor,
    ExtractedSection,
    ExtractionResult,
    package_version,
)
from app.processing.normalization import normalize_text

EXTRACTOR_NAME = "pymupdf"


class PDFExtractor(DocumentExtractor):
    name = EXTRACTOR_NAME
    version = package_version("pymupdf")

    def extract(self, file) -> ExtractionResult:
        result = ExtractionResult(
            extractor_name=self.name, extractor_version=self.version
        )

        with pymupdf.open(stream=file.read(), filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise ValueError("Password-protected PDFs are not supported.")
            if pdf.is_closed or pdf.page_count == 0:
                raise ValueError("PDF contains no readable pages.")

            for page in pdf:  # iterate lazily, page-by-page
                text = normalize_text(page.get_text("text"))
                has_text = bool(text.strip())
                result.sections.append(
                    ExtractedSection(
                        index=page.number + 1,
                        content_type=PageContentType.PAGE,
                        section_reference=f"page {page.number + 1}",
                        text=text if has_text else None,
                        extraction_status=(
                            TextExtractionStatus.EXTRACTED
                            if has_text
                            else TextExtractionStatus.NO_TEXT
                        ),
                        structured_metadata={
                            "width": page.rect.width,
                            "height": page.rect.height,
                            "rotation": page.rotation,
                        },
                    )
                )

        return result

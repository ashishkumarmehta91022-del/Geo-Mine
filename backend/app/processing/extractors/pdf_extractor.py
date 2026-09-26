"""PDF extractor — PyMuPDF, page-by-page, native text or OCR (Step 5).

Each page is processed independently: pages with a reliable native text layer
use the Step 4 PyMuPDF path; image-only (scanned) pages are rendered at the
configured zoom and OCR'd. One scanned page never reclassifies the document.
"""

import pymupdf

from app.config import settings
from app.constants import PageContentType, TextExtractionStatus
from app.processing.base import (
    DocumentExtractor,
    ExtractedSection,
    ExtractionResult,
    package_version,
)
from app.processing.normalization import normalize_text
from app.processing.ocr.pipeline import ocr_image_bytes

EXTRACTOR_NAME = "pymupdf+ocr"
NATIVE_TEXT_MIN_CHARS = 8  # below this, a page is treated as scanned


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

            for page in pdf:  # page-by-page; each page decided independently
                native_text = normalize_text(page.get_text("text"))

                if len(native_text.strip()) >= NATIVE_TEXT_MIN_CHARS:
                    status = TextExtractionStatus.EXTRACTED
                    text = native_text
                    ocr_meta = None
                    section_meta = {
                        "width": page.rect.width,
                        "height": page.rect.height,
                        "rotation": page.rotation,
                    }
                else:
                    # Scanned/image-only page: render → OCR (never faked).
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(settings.pdf_ocr_zoom, settings.pdf_ocr_zoom))
                    status, text, ocr_meta = ocr_image_bytes(pix.tobytes("png"))
                    section_meta = {
                        "width": page.rect.width,
                        "height": page.rect.height,
                        "rotation": page.rotation,
                        "ocr_render_zoom": settings.pdf_ocr_zoom,
                    }

                if ocr_meta is not None:
                    section_meta["ocr"] = ocr_meta

                result.sections.append(
                    ExtractedSection(
                        index=page.number + 1,
                        content_type=PageContentType.PAGE,
                        section_reference=f"page {page.number + 1}",
                        text=text or None,
                        # Native path yields EXTRACTED; OCR path yields its own
                        # outcome (ocr_extracted / no_text / failed / ocr_required).
                        extraction_status=status,
                        structured_metadata=section_meta,
                        error_message=(
                            ocr_meta.get("error")
                            if isinstance(ocr_meta, dict) and ocr_meta.get("error")
                            else None
                        ),
                    )
                )

        return result

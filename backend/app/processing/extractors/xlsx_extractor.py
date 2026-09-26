"""XLSX extractor — openpyxl, sheet boundaries preserved, cell types kept.

Cell values keep their basic types (int, float, str, bool, datetime/date,
None) — no coercion to strings, no formula evaluation, no invented meaning.
Formulas are read as cached values only (data_only=True); sheets are
processed sequentially.
"""

from datetime import date, datetime
from typing import Any

from openpyxl import load_workbook

from app.constants import PageContentType, TextExtractionStatus
from app.processing.base import (
    DocumentExtractor,
    ExtractedSection,
    ExtractionResult,
    package_version,
)
from app.processing.normalization import normalize_text

EXTRACTOR_NAME = "openpyxl"

MAX_EXTRACTED_CELLS_PER_SHEET = 200_000  # guardrail against pathological sheets


def _cell_value(value: Any) -> Any:
    """Normalize openpyxl cell values, preserving basic JSON-compatible types."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, str):
        return value.replace("\x00", "")
    # Fallback: str() for anything exotic — value stays traceable, unmodified in spirit.
    return str(value)


def _sheet_rows(worksheet) -> list[list[Any]]:
    rows: list[list[Any]] = []
    cell_count = 0
    for row in worksheet.iter_rows(values_only=True):
        row_values = [_cell_value(value) for value in row]
        rows.append(row_values)
        cell_count += len(row_values)
        if cell_count > MAX_EXTRACTED_CELLS_PER_SHEET:
            raise ValueError(
                f"Sheet '{worksheet.title}' exceeds the {MAX_EXTRACTED_CELLS_PER_SHEET}-cell extraction guardrail."
            )
    return rows


class XLSXExtractor(DocumentExtractor):
    name = EXTRACTOR_NAME
    version = package_version("openpyxl")

    def extract(self, file) -> ExtractionResult:
        result = ExtractionResult(
            extractor_name=self.name, extractor_version=self.version
        )

        # data_only=True: read cached formula results, never evaluate formulas.
        # read_only=True: streaming mode, bounded memory on large workbooks.
        workbook = load_workbook(file, data_only=True, read_only=True, keep_links=False)
        try:
            for sheet_index, worksheet in enumerate(workbook.worksheets, start=1):
                rows = _sheet_rows(worksheet)
                sheet_text = normalize_text(
                    "\n".join(
                        "\t".join("" if value is None else str(value) for value in row)
                        for row in rows
                    )
                )
                has_text = bool(sheet_text.strip())
                result.sections.append(
                    ExtractedSection(
                        index=sheet_index,
                        content_type=PageContentType.SHEET,
                        section_reference=f"sheet {worksheet.title}",
                        text=sheet_text if has_text else None,
                        extraction_status=(
                            TextExtractionStatus.EXTRACTED
                            if has_text
                            else TextExtractionStatus.NO_TEXT
                        ),
                        structured_metadata={
                            "sheet_name": worksheet.title,
                            "row_count": len(rows),
                            "column_count": max((len(row) for row in rows), default=0),
                            "rows": rows,  # typed cell values preserved
                        },
                    )
                )
        finally:
            workbook.close()

        if not result.sections:
            raise ValueError("Workbook contains no sheets.")
        return result

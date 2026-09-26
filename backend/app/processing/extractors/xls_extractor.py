"""Legacy XLS extractor — xlrd 2.x (supports the old binary .xls format only).

Same contract as the XLSX extractor: sheet boundaries preserved, cell types
kept (numbers/strings/dates/booleans/empty), no formula evaluation — xlrd
never evaluates formulas, it reads cached values.
"""

from datetime import date, datetime, time as time_type
from typing import Any

import xlrd

from app.constants import PageContentType, TextExtractionStatus
from app.processing.base import (
    DocumentExtractor,
    ExtractedSection,
    ExtractionResult,
    package_version,
)
from app.processing.normalization import normalize_text

EXTRACTOR_NAME = "xlrd"

MAX_EXTRACTED_CELLS_PER_SHEET = 200_000


def _cell_value(sheet, row_index: int, col_index: int) -> Any:
    """Return the typed cell value from an xlrd sheet (cell_type-aware)."""
    cell_type = sheet.cell_type(row_index, col_index)
    if cell_type == xlrd.XL_CELL_EMPTY or cell_type == xlrd.XL_CELL_BLANK:
        return None
    value = sheet.cell_value(row_index, col_index)
    if cell_type == xlrd.XL_CELL_DATE:
        # Convert xlrd's date triple to an ISO string without inventing values.
        date_tuple = xlrd.xldate_as_tuple(value, sheet.book.datemode)
        if date_tuple[3:] == (0, 0, 0):
            return date(*date_tuple[:3]).isoformat()
        if date_tuple[:3] == (0, 0, 0):
            return time_type(*date_tuple[3:]).isoformat()
        return datetime(*date_tuple).isoformat()
    if cell_type == xlrd.XL_CELL_BOOLEAN:
        return bool(value)
    if cell_type == xlrd.XL_CELL_NUMBER:
        return value  # int-valued floats stay floats; no silent casting
    if cell_type == xlrd.XL_CELL_TEXT:
        return str(value).replace("\x00", "")
    return str(value)


def _sheet_rows(sheet) -> list[list[Any]]:
    rows: list[list[Any]] = []
    cell_count = 0
    for row_index in range(sheet.nrows):
        row_values = [_cell_value(sheet, row_index, col_index) for col_index in range(sheet.ncols)]
        rows.append(row_values)
        cell_count += len(row_values)
        if cell_count > MAX_EXTRACTED_CELLS_PER_SHEET:
            raise ValueError(
                f"Sheet '{sheet.name}' exceeds the {MAX_EXTRACTED_CELLS_PER_SHEET}-cell extraction guardrail."
            )
    return rows


class XLSExtractor(DocumentExtractor):
    name = EXTRACTOR_NAME
    version = package_version("xlrd")

    def extract(self, file) -> ExtractionResult:
        result = ExtractionResult(
            extractor_name=self.name, extractor_version=self.version
        )

        book = xlrd.open_workbook(file_contents=file.read(), formatting_info=False)
        for sheet_index, sheet in enumerate(book.sheets(), start=1):
            rows = _sheet_rows(sheet)
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
                    section_reference=f"sheet {sheet.name}",
                    text=sheet_text if has_text else None,
                    extraction_status=(
                        TextExtractionStatus.EXTRACTED if has_text else TextExtractionStatus.NO_TEXT
                    ),
                    structured_metadata={
                        "sheet_name": sheet.name,
                        "row_count": len(rows),
                        "column_count": max((len(row) for row in rows), default=0),
                        "rows": rows,
                    },
                )
            )

        if not result.sections:
            raise ValueError("Workbook contains no sheets.")
        return result

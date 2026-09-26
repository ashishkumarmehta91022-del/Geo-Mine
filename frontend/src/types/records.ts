/** Structured record types (mirror backend/app/schemas/records.py). */

export interface StructuredRecord {
  id: number;
  document_id: number;
  document_filename: string | null;
  page_id: number | null;
  page_number: number | null;
  entity_name: string;
  metric_name: string;
  /** Verbatim source value ("1O5" stays "1O5"). */
  value_raw: string | null;
  metric_value: string | null;
  /** Safely normalized value; null when not unambiguously derivable. */
  normalized_value: string | null;
  unit: string | null;
  reporting_period: string | null;
  source_reference: string | null;
  extraction_method: string | null;
  confidence: number | null;
  validation_status: string;
  record_metadata: Record<string, unknown> | null;
}

export interface RecordListResponse {
  items: StructuredRecord[];
  page: number;
  page_size: number;
  total: number;
}

export const EXTRACTION_METHODS = [
  "native_text",
  "ocr",
  "table",
  "spreadsheet",
  "docx",
] as const;

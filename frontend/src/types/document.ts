/** Document API types (mirror backend/app/schemas/documents.py). */

export type DocumentType = "pdf" | "docx" | "xlsx" | "image";

export interface DocumentRecord {
  id: number;
  filename: string;
  document_type: DocumentType | string;
  source: string;
  status: string;
  storage_reference: string;
  uploaded_at: string;
  /** Preserved processing error (null unless status == "failed"). */
  error_message?: string | null;
}

export interface DocumentListResponse {
  items: DocumentRecord[];
  page: number;
  page_size: number;
  total: number;
}

/** Supported upload categories shown in the UI. */
export const SUPPORTED_FILE_TYPES = ".pdf,.docx,.xlsx,.xls,.png,.jpg,.jpeg";
export const MAX_UPLOAD_SIZE_MB = 25;

/** Processing lifecycle (mirrors backend/app/constants.py). */
export type DocumentStatus = "uploaded" | "queued" | "processing" | "processed" | "failed";

export interface ExtractionStats {
  extracted: number;
  no_text: number;
  ocr_required: number;
  failed: number;
  total_units: number;
}

export interface ProcessingStatus {
  document_id: number;
  status: DocumentStatus | string;
  processed_at: string | null;
  extraction_status: string | null;
  extractor: { name: string | null; version: string | null };
  statistics: ExtractionStats;
  error_message: string | null;
}

export interface ContentSection {
  type: "page" | "sheet" | "image" | string;
  number: number;
  reference: string | null;
  text: string | null;
  extraction_status: string;
  structured: Record<string, unknown> | null;
}

export interface DocumentContent {
  document_id: number;
  status: string;
  extraction_status: string | null;
  sections: ContentSection[];
}

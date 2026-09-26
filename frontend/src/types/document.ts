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

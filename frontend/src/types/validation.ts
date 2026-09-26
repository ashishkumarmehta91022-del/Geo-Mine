/** Validation API types (mirror backend/app/schemas/validation.py). */

export interface ValidationSummary {
  total_checks: number;
  passed: number;
  warnings: number;
  errors: number;
  review_required: number;
}

export interface ConflictValue {
  document_id: number;
  record_id: number | null;
  source_reference: string | null;
  value: string;
  document_filename: string | null;
}

export interface ValidationItem {
  id: number;
  document_id: number;
  document_filename: string | null;
  extracted_record_id: number | null;
  page_id: number | null;
  source_reference: string | null;
  rule_code: string;
  status: "pass" | "warning" | "error" | "review_required" | string;
  severity: "info" | "warning" | "error" | "critical" | string;
  message: string | null;
  original_value: string | null;
  expected_value: string | null;
  details: Record<string, unknown> | null;
  review_status: "open" | "in_review" | "resolved" | "rejected" | string;
  review_notes: string | null;
  reviewed_at: string | null;
  created_at: string;
  confidence?: number | null;
}

export interface ValidationRunResponse extends ValidationSummary {
  document_id: number;
  results_created: number;
  ran_at: string;
}

export interface ValidationDocumentResponse {
  document_id: number;
  summary: ValidationSummary;
  items: ValidationItem[];
}

export interface ReviewQueueResponse {
  page: number;
  page_size: number;
  total: number;
  items: ValidationItem[];
}

export const REVIEW_STATUSES = ["open", "in_review", "resolved", "rejected"] as const;

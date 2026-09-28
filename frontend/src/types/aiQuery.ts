/** AI Query types (mirror backend/app/schemas/ai_query.py, Step 10). */

export interface ConflictNotice {
  entity: string | null;
  metric: string | null;
  reporting_period: string | null;
  values: string[];
  evidence_ids: number[];
}

export interface EvidenceItem {
  evidence_id: number;
  unit_type: string;
  document_id: number;
  document_name: string | null;
  page_id: number | null;
  page_number: number | null;
  record_id: number | null;
  validation_id: number | null;
  source_reference: string | null;
  extraction_method: string | null;
  validation_status: string | null;
  ocr_confidence: number | null;
  entity: string | null;
  metric: string | null;
  unit: string | null;
  reporting_period: string | null;
  value_raw: string | null;
  normalized_value: string | null;
  snippet: string | null;
  lexical_score: number | null;
  semantic_similarity: number | null;
  relevance: number | null;
}

export interface AIQueryResponse {
  status: "ok" | "insufficient_evidence" | "llm_unavailable" | "llm_error";
  question: string;
  answer: string | null;
  evidence: EvidenceItem[];
  evidence_ids: number[];
  retrieval_mode: string;
  retrieval_total: number | null;
  conflict_detected: boolean;
  conflicts: ConflictNotice[];
  insufficient_evidence: boolean;
  provider: string | null;
  model: string | null;
  limitations: string | null;
  error: string | null;
  retrieval_note: string | null;
  latency_ms: number | null;
  invalid_citations_dropped: number[];
  generated_at: string;
  grounding_note: string;
}

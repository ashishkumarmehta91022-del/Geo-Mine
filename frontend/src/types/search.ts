/** Search API types (mirror backend/app/schemas/search.py). */

export type SearchUnitType = "page" | "record" | "validation" | string;

/** Step 9 retrieval modes — omitted/lexical = exact Step 8 behavior. */
export type RetrievalMode = "lexical" | "semantic" | "hybrid";

export interface SearchResultItem {
  unit_type: SearchUnitType;
  document_id: number;
  document_name: string | null;
  page_id: number | null;
  page_number: number | null;
  record_id: number | null;
  validation_id: number | null;
  source_reference: string | null;
  extraction_method: string | null;
  title: string | null;
  snippet: string | null;
  entity: string | null;
  metric: string | null;
  value_raw: string | null;
  normalized_value: string | null;
  unit: string | null;
  reporting_period: string | null;
  validation_status: string | null;
  ocr_confidence: number | null;
  rank_score: number | null;
  /** Cosine similarity — a retrieval metric, never truth/correctness/trust. */
  semantic_similarity: number | null;
  /** Hybrid combined score (explicit documented formula) — relevance only. */
  relevance: number | null;
}

export interface SearchResponse {
  query: string;
  total: number;
  limit: number;
  offset: number;
  results: SearchResultItem[];
  /** Set for semantic/hybrid responses (or when lexical fell back). */
  mode?: RetrievalMode | null;
  semantic_available?: boolean | null;
  semantic_error?: string | null;
  /** Explicit note that scores are retrieval metrics, not trust. */
  retrieval_note?: string | null;
}

export interface KnowledgeStats {
  documents_indexed: number;
  pages_indexed: number;
  records_indexed: number;
  validation_results_indexed: number;
  total_units: number;
  last_index_update: string | null;
  /** Step 9: embedding state counters (factual, from the DB). */
  embedded_units: number;
  embedding_error_units: number;
  embedding_models: string[];
}

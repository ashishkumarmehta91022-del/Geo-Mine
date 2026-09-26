/** Search API types (mirror backend/app/schemas/search.py). */

export type SearchUnitType = "page" | "record" | "validation" | string;

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
}

export interface SearchResponse {
  query: string;
  total: number;
  limit: number;
  offset: number;
  results: SearchResultItem[];
}

export interface KnowledgeStats {
  documents_indexed: number;
  pages_indexed: number;
  records_indexed: number;
  validation_results_indexed: number;
  total_units: number;
  last_index_update: string | null;
}

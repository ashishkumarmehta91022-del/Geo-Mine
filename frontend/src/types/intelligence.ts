/** Document intelligence types (mirror backend/app/schemas/intelligence.py, Step 13). */

export interface SourceRef {
  document_id: number;
  page_id: number | null;
  page_number: number | null;
  unit_type: string;
  source_reference: string | null;
}

export interface Keyword {
  term: string;
  display_term: string;
  kind: "term" | "phrase";
  frequency: number;
  document_frequency: number;
  score: number;
  score_reason: string;
  sources: SourceRef[];
}

export interface WordCloudTerm {
  term: string;
  display_term: string;
  weight: number;
  frequency: number;
  document_frequency: number;
  kind: string;
  sources: SourceRef[];
}

export interface Topic {
  topic_id: string;
  label: string;
  score: number;
  representative_terms: string[];
  document_ids: number[];
  sources: SourceRef[];
  method: string;
}

export interface TopicDocumentMatch {
  topic_id: string;
  topic_label: string;
  document_id: number;
  score: number;
  supporting_terms: string[];
  sources: SourceRef[];
}

export interface DocumentSummary {
  document_id: number;
  document_name: string;
  document_type: string;
  page_count: number;
  extraction_status: string | null;
  validation_status: string | null;
  record_count: number;
  warning_error_review_count: number;
  pending_validation_count: number;
  conflict_count: number;
  summary_text: string;
  key_terms: { term: string; display_term: string; frequency: number }[];
  top_topics: Topic[];
  key_metrics: {
    record_id: number;
    entity: string | null;
    metric: string | null;
    value_raw: string | null;
    normalized_value: string | null;
    unit: string | null;
    reporting_period: string | null;
    validation_status: string | null;
    source_reference: string | null;
  }[];
  corpus_truncated: boolean;
  generated_at: string;
}

export interface AiSummary {
  state: "ok" | "unavailable" | "failed" | "insufficient_evidence";
  summary?: string;
  key_points?: string[];
  limitations?: string;
  reason?: string;
  notice?: string;
  provider?: string;
  model?: string;
  evidence_unit_ids?: number[];
}

export interface CorpusStats {
  document_count: number;
  unit_count: number;
  char_count: number;
  truncated_units: boolean;
  truncated_chars: boolean;
  limits: Record<string, number>;
}

export interface IntelligenceResponse {
  scope: "document" | "corpus";
  document_ids: number[];
  keywords: Keyword[];
  topics: Topic[];
  word_cloud: WordCloudTerm[];
  topic_document_matches: TopicDocumentMatch[];
  summaries: DocumentSummary[];
  corpus_stats: CorpusStats;
  ai_summary: AiSummary | null;
  limitations: string[];
  summary?: DocumentSummary;
}

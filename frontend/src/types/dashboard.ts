/** Dashboard types (mirror backend/app/schemas/dashboard.py, Step 14). */

export interface DashboardStatus {
  component: string;
  /** OPERATIONAL | CONNECTED | UNAVAILABLE | NOT CONFIGURED | DEGRADED */
  status: string;
  detail: string | null;
}

export interface DocumentMetrics {
  total: number;
  processed: number;
  failed: number;
  processing: number;
  uploaded: number;
  by_status: Record<string, number>;
}

export interface RecordMetrics {
  total: number;
  by_status: Record<string, number>;
  validated: number;
  pending: number;
  flagged: number;
}

export interface ValidationMetrics {
  total: number;
  by_status: Record<string, number>;
  review_required: number;
  errors: number;
  warnings: number;
}

export interface KnowledgeMetrics {
  total_units: number;
  pages: number;
  records: number;
  validations: number;
  embedded_units: number;
  embedding_coverage: number;
  documents_indexed: number;
}

export interface IntelligenceAvailability {
  available: boolean;
  indexed_documents: number;
  detail: string | null;
  topic_count: number | null;
  top_topics: { topic_id: string; label: string; score: number }[];
  top_terms: { term: string; display_term: string; frequency: number }[];
}

export interface RecentDocumentItem {
  document_id: number;
  filename: string;
  document_type: string;
  status: string;
  validation_status: string | null;
  extraction_status: string | null;
  uploaded_at: string | null;
  processed_at: string | null;
  record_count: number;
  requires_review: boolean;
}

export interface RecentActivityItem {
  action: string;
  entity_type: string | null;
  created_at: string;
}

export interface DashboardSummary {
  data_available: boolean;
  message: string | null;
  database: DashboardStatus;
  api: DashboardStatus;
  retrieval: DashboardStatus;
  embeddings: DashboardStatus;
  llm: DashboardStatus;
  documents: DocumentMetrics | null;
  records: RecordMetrics | null;
  validation: ValidationMetrics | null;
  knowledge: KnowledgeMetrics | null;
  intelligence: IntelligenceAvailability | null;
  recent_documents: RecentDocumentItem[];
  recent_activity: RecentActivityItem[];
  limitations: string[];
}

/** GET /api/dashboard/statuses payload (status-only). */
export interface DashboardStatuses {
  data_available: boolean;
  api: DashboardStatus;
  database: DashboardStatus;
  retrieval: DashboardStatus;
  embeddings: DashboardStatus;
  llm: DashboardStatus;
}

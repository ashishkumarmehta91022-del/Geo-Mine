/** Report analytics types (mirror backend/app/schemas/report_analytics.py, Step 12). */

export interface ReportFilters {
  validation_status?: string | null;
  extraction_method?: string | null;
  record_type?: string | null;
}

export interface AnalyzeRequest {
  title: string;
  report_type?: string | null;
  reporting_period?: string | null;
  document_ids?: number[] | null;
  entities?: string[] | null;
  metrics?: string[] | null;
  filters?: ReportFilters | null;
  requester?: string | null;
  include_narrative?: boolean;
}

export interface ExcludedValue {
  record_id: number;
  document_id: number;
  value_raw: string | null;
  normalized_value: string | null;
  reason: string;
}

export interface KPI {
  name: string;
  label: string;
  entity: string | null;
  metric: string | null;
  reporting_period: string | null;
  unit: string | null;
  /** Decimal serialized as string (or null for count-style KPIs). */
  value: string | null;
  count: number | null;
  source_record_ids: number[];
  source_document_ids: number[];
  validation_status: string | null;
  conflict_status: string;
  excluded: ExcludedValue[];
}

export interface TrendPoint {
  period: string;
  value: string;
  value_raw: string | null;
  record_ids: number[];
  document_ids: number[];
  validation_status: string | null;
}

export interface Trend {
  entity: string | null;
  metric: string | null;
  unit: string | null;
  points: TrendPoint[];
  missing_periods: string[];
  first_value: string | null;
  last_value: string | null;
  absolute_change: string | null;
  percent_change: string | null;
  percent_change_valid: boolean;
  direction: "increasing" | "decreasing" | "unchanged";
  status: string;
  source_record_ids: number[];
  source_document_ids: number[];
  excluded: ExcludedValue[];
}

export interface ComparisonSide {
  label: string;
  value: string | null;
  value_raw: string | null;
  unit: string | null;
  record_ids: number[];
  document_ids: number[];
  validation_status: string | null;
}

export interface Comparison {
  kind: string;
  metric: string | null;
  unit: string | null;
  period: string | null;
  sides: ComparisonSide[];
  absolute_difference: string | null;
  difference_unit: string | null;
  difference_valid: boolean;
  status: string;
  source_record_ids: number[];
  source_document_ids: number[];
  excluded: ExcludedValue[];
}

export interface DistributionBin {
  range: string;
  count: number;
}

export interface Distribution {
  metric: string | null;
  unit: string | null;
  bins: DistributionBin[];
  total_counted: number;
  excluded: ExcludedValue[];
}

export interface Insight {
  kind: "TREND" | "CHANGE" | "COMPARISON" | "DATA_GAP" | "VALIDATION_WARNING" | "CONFLICT";
  message: string;
  entity: string | null;
  metric: string | null;
  reporting_period: string | null;
  status: string;
  source_record_ids: number[];
  source_document_ids: number[];
  related_chart: string | null;
}

export interface ChartPoint {
  x: string;
  y: number | null;
}

export interface ChartSeries {
  name: string;
  unit: string | null;
  points: ChartPoint[];
  point_record_ids: number[][];
}

export interface ChartSpec {
  chart_type: "line" | "bar" | "comparison";
  title: string;
  x_axis: string;
  y_axis: string;
  unit: string | null;
  series: ChartSeries[];
  source_record_ids: number[];
  source_document_ids: number[];
  conflict_status: string;
  validation_statuses: string[];
  note: string | null;
}

export interface Narrative {
  state: "ok" | "unavailable" | "failed" | "deterministic";
  narrative?: string;
  summary_points?: string[];
  limitations?: string;
  reason?: string;
  notice?: string;
  provider?: string;
  model?: string;
  ai_attempt?: { state: string; reason?: string };
}

export interface AnalyzeResponse {
  status: string;
  report_id: string;
  fingerprint: string;
  specification: Record<string, unknown>;
  generated_at: string;
  record_count: number;
  document_count: number;
  conflict_count: number;
  validation_warning_error_count: number;
  excluded_value_count: number;
  kpis: KPI[];
  trends: Trend[];
  comparisons: Comparison[];
  distributions: Distribution[];
  insights: Insight[];
  charts: ChartSpec[];
  excluded_values: ExcludedValue[];
  narrative: Narrative | null;
  limitations: string[];
}

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { MetricCard } from "@/components/ui/Cards";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { listRecords } from "@/lib/recordsApi";
import { fetchDashboardSummary } from "@/lib/dashboardApi";
import {
  EXTRACTION_METHODS,
  type RecordListResponse,
  type StructuredRecord,
} from "@/types/records";
import type { ValidationMetrics } from "@/types/dashboard";

function validationTone(status: string | null | undefined): BadgeTone {
  switch (status) {
    case "valid":
    case "pass":
      return "ok";
    case "warning":
      return "warn";
    case "failed":
    case "error":
      return "bad";
    case "review_required":
      return "review";
    default:
      return "neutral";
  }
}

function methodTone(method: string | null): BadgeTone {
  switch (method) {
    case "ocr":
      return "review";
    case "spreadsheet":
      return "ok";
    case "table":
      return "info";
    case "docx":
      return "info";
    case "native_text":
    default:
      return "neutral";
  }
}

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

/** ExtractedRecord.validation_status vocabulary (mirrors the DB + API). */
const VALIDATION_OPTIONS = ["valid", "warning", "failed", "pending"] as const;

/** Data Explorer — structured extracted records with exact-match filters. */
export default function DataExplorerPage() {
  const [data, setData] = useState<RecordListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [validationMetrics, setValidationMetrics] = useState<ValidationMetrics | null>(null);
  const [recordTotal, setRecordTotal] = useState<number | null>(null);
  const [recordValidated, setRecordValidated] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [filters, setFilters] = useState({
    entity: "",
    metric: "",
    reporting_period: "",
    extraction_method: "",
    validation_status: "",
  });
  const [appliedFilters, setAppliedFilters] = useState(filters);

  const load = useCallback(async (targetPage: number, active: typeof filters) => {
    setIsLoading(true);
    setIsError(false);
    setError(null);
    try {
      setData(
        await listRecords({
          entity: active.entity || undefined,
          metric: active.metric || undefined,
          reporting_period: active.reporting_period || undefined,
          extraction_method: active.extraction_method || undefined,
          validation_status: active.validation_status || undefined,
          page: targetPage,
          page_size: 20,
        }),
      );
    } catch (cause: unknown) {
      setIsError(true);
      setError(cause instanceof Error ? cause.message : "Could not load records.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page, appliedFilters);
  }, [load, page, appliedFilters]);

  // Real summaries (dashboard aggregation over the same source of truth):
  // record-level metrics for the record cards, outcome-level for quality flags.
  useEffect(() => {
    fetchDashboardSummary()
      .then((s) => {
        setValidationMetrics(s.validation);
        setRecordTotal(s.records ? s.records.total : null);
        setRecordValidated(s.records ? s.records.validated : null);
      })
      .catch(() => {
        setValidationMetrics(null);
        setRecordTotal(null);
        setRecordValidated(null);
      });
  }, []);

  const applyFilters = () => {
    setPage(1);
    setAppliedFilters(filters);
  };

  const resetFilters = () => {
    const empty = { entity: "", metric: "", reporting_period: "", extraction_method: "", validation_status: "" };
    setFilters(empty);
    setPage(1);
    setAppliedFilters(empty);
  };

  return (
    <>
      <PageHeader
        title="Data Explorer"
        description="Explore extracted and validated geological, mining and production records."
      />

      {/* Summary (real aggregation from the dashboard service) */}
      <section aria-label="Record quality summary" className="mb-6">
        {validationMetrics ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <MetricCard label="Records" icon="data" value={recordTotal ?? "—"} hint="structured records" />
            <MetricCard label="Validated" icon="ok" tone="ok" value={recordValidated ?? "—"} hint="records passed all rules" to="/validation" />
            <MetricCard label="Warnings" icon="warn" tone="warn" value={validationMetrics.warnings} hint="rule warnings" to="/validation" />
            <MetricCard label="Errors" icon="warn" tone="bad" value={validationMetrics.errors} hint="rule errors" to="/validation" />
            <MetricCard label="Review Required" icon="review" tone={validationMetrics.review_required > 0 ? "warn" : "neutral"} value={validationMetrics.review_required} hint="awaiting human review" to="/review-queue" />
          </div>
        ) : (
          <div className="card p-4">
            <StateBlock variant="empty" title="Summary unavailable" description="Live record metrics could not be loaded — the workspace below still works." />
          </div>
        )}
      </section>

      {/* Filters (only filters the API actually supports) */}
      <section aria-label="Filters" className="card mb-6 p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Entity (exact)</label>
            <input
              className={inputClass}
              placeholder="e.g. DEMO_MINE_A"
              value={filters.entity}
              onChange={(e) => setFilters({ ...filters, entity: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Metric (exact)</label>
            <input
              className={inputClass}
              placeholder="e.g. demo_coal_production"
              value={filters.metric}
              onChange={(e) => setFilters({ ...filters, metric: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Reporting period</label>
            <input
              className={inputClass}
              placeholder="e.g. 2025-06-30"
              value={filters.reporting_period}
              onChange={(e) => setFilters({ ...filters, reporting_period: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Extraction method</label>
            <select
              className={inputClass}
              value={filters.extraction_method}
              onChange={(e) => setFilters({ ...filters, extraction_method: e.target.value })}
            >
              <option value="">Any</option>
              {EXTRACTION_METHODS.map((method) => (
                <option key={method} value={method}>
                  {method.split("_").join(" ")}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Validation status</label>
            <select
              className={inputClass}
              value={filters.validation_status}
              onChange={(e) => setFilters({ ...filters, validation_status: e.target.value })}
            >
              <option value="">Any</option>
              {VALIDATION_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {status.split("_").join(" ")}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end gap-2">
            <button type="button" className="btn-primary flex-1" onClick={applyFilters}>
              Apply
            </button>
            <button type="button" className="btn-secondary flex-1" onClick={resetFilters}>
              Reset
            </button>
          </div>
        </div>
        <p className="mt-3 text-xs text-gray-400">
          Prefer full-text search?{" "}
          <Link to="/knowledge" className="text-brand-600 underline">
            Open Knowledge Search
          </Link>{" "}
          — it searches pages, records and validation results with provenance.
        </p>
      </section>

      {/* Results */}
      {isLoading && <StateBlock variant="loading" title="Loading records…" />}
      {isError && (
        <StateBlock
          variant="error"
          title="Cannot load records"
          description={error ?? undefined}
          action={
            <button type="button" className="btn-primary" onClick={() => load(page, appliedFilters)}>
              Retry
            </button>
          }
        />
      )}
      {!isLoading && !isError && data && data.items.length === 0 && (
        <StateBlock
          variant="empty"
          title="No structured records found"
          description="Process a document first — structured records appear here after extraction. Adjust the filters if you expected results."
          action={<Link to="/documents" className="btn-primary">Go to Documents</Link>}
        />
      )}
      {!isLoading && !isError && data && data.items.length > 0 && (
        <>
          <div className="card overflow-x-auto">
            <table className="table-base min-w-[900px]">
              <thead>
                <tr>
                  <th scope="col">Record</th>
                  <th scope="col">Value</th>
                  <th scope="col">Normalized</th>
                  <th scope="col">Unit</th>
                  <th scope="col">Period</th>
                  <th scope="col">Document</th>
                  <th scope="col">Validation</th>
                  <th scope="col" className="text-right">Source</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((record: StructuredRecord) => (
                  <RecordRow
                    key={record.id}
                    record={record}
                    expanded={expandedId === record.id}
                    onToggle={() => setExpandedId(expandedId === record.id ? null : record.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {data.total > data.page_size && (
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-gray-500">
                Page {data.page} of {Math.ceil(data.total / data.page_size)} · {data.total} records
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-secondary !px-3 !py-1.5 text-xs"
                  disabled={data.page <= 1}
                  onClick={() => setPage(data.page - 1)}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn-secondary !px-3 !py-1.5 text-xs"
                  disabled={data.page >= Math.ceil(data.total / data.page_size)}
                  onClick={() => setPage(data.page + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}

/** One record row + expandable provenance/evidence panel. */
function RecordRow({
  record,
  expanded,
  onToggle,
}: {
  record: StructuredRecord;
  expanded: boolean;
  onToggle: () => void;
}) {
  const label = [record.entity_name, record.metric_name].filter(Boolean).join(" — ");
  return (
    <>
      <tr className={expanded ? "bg-brand-50/40" : undefined}>
        <td className="max-w-[220px]">
          <p className="truncate font-medium text-gray-900" title={label}>
            {record.entity_name}
          </p>
          <p className="truncate font-mono text-[11px] text-gray-500" title={record.metric_name}>
            {record.metric_name}
          </p>
        </td>
        <td className="font-mono text-sm font-semibold text-gray-900">
          {record.value_raw ?? <span className="font-sans text-xs text-gray-400">—</span>}
        </td>
        <td className="font-mono text-sm text-gray-600">
          {record.normalized_value ?? <span title="Not safely derivable — raw value preserved verbatim">—</span>}
        </td>
        <td className="text-gray-600">{record.unit ?? "—"}</td>
        <td className="whitespace-nowrap text-gray-600">{record.reporting_period ?? "—"}</td>
        <td className="max-w-[170px]">
          <p className="truncate text-gray-700" title={record.document_filename ?? `Document #${record.document_id}`}>
            {record.document_filename ?? `#${record.document_id}`}
          </p>
        </td>
        <td>
          <Badge tone={validationTone(record.validation_status)}>
            {(record.validation_status ?? "—").split("_").join(" ")}
          </Badge>
        </td>
        <td className="text-right">
          <button
            type="button"
            className="btn-ghost !px-2 !py-1 text-xs"
            onClick={onToggle}
            aria-expanded={expanded}
            aria-controls={`evidence-${record.id}`}
            title="Show provenance and evidence"
          >
            <Icon name={expanded ? "chevron-down" : "eye"} className="h-4 w-4" />
            Evidence
          </button>
        </td>
      </tr>
      {expanded && (
        <tr id={`evidence-${record.id}`} className="bg-slate-50">
          <td colSpan={8} className="px-4 py-3">
            <div className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="section-title mb-1">Source reference</p>
                <p className="break-words text-gray-700">{record.source_reference ?? "—"}</p>
              </div>
              <div>
                <p className="section-title mb-1">Extraction method</p>
                <Badge tone={methodTone(record.extraction_method)}>
                  {(record.extraction_method ?? "unknown").split("_").join(" ")}
                </Badge>
              </div>
              <div>
                <p className="section-title mb-1">Extraction confidence</p>
                <p className="text-gray-700">
                  {record.confidence != null ? `${Math.round(record.confidence * 100)}%` : "—"}
                </p>
              </div>
              <div>
                <p className="section-title mb-1">Provenance chain</p>
                <p className="text-gray-700">
                  Document #{record.document_id}
                  {record.page_id ? ` → Page #${record.page_id}` : ""} → Record #{record.id} →{" "}
                  {record.validation_status}
                </p>
              </div>
            </div>
            <p className="mt-2 flex items-center gap-1.5 text-[11px] text-gray-500">
              <Icon name="link" className="h-3.5 w-3.5 shrink-0" />
              This value came from the source above and is traceable end-to-end. Raw values are
              never altered — normalization is stored separately.
            </p>
          </td>
        </tr>
      )}
    </>
  );
}

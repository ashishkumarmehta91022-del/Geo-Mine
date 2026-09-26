import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { listRecords } from "@/lib/recordsApi";
import {
  EXTRACTION_METHODS,
  type RecordListResponse,
  type StructuredRecord,
} from "@/types/records";

function validationBadge(status: string): string {
  switch (status) {
    case "valid":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "warning":
      return "bg-amber-50 text-amber-700 border-amber-200";
    case "failed":
      return "bg-red-50 text-red-700 border-red-200";
    default:
      return "bg-gray-100 text-gray-600 border-gray-200";
  }
}

function methodBadge(method: string | null): string {
  switch (method) {
    case "ocr":
      return "bg-purple-50 text-purple-700 border-purple-200";
    case "spreadsheet":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "table":
      return "bg-blue-50 text-blue-700 border-blue-200";
    case "native_text":
      return "bg-gray-100 text-gray-700 border-gray-200";
    default:
      return "bg-gray-100 text-gray-600 border-gray-200";
  }
}

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

/** Data Explorer — structured extracted records with exact-match filters (Step 7). */
export default function DataExplorerPage() {
  const [data, setData] = useState<RecordListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const [filters, setFilters] = useState({
    entity: "",
    metric: "",
    reporting_period: "",
    extraction_method: "",
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

  const applyFilters = () => {
    setPage(1);
    setAppliedFilters(filters);
  };

  const resetFilters = () => {
    setFilters({ entity: "", metric: "", reporting_period: "", extraction_method: "" });
    setPage(1);
    setAppliedFilters({ entity: "", metric: "", reporting_period: "", extraction_method: "" });
  };

  return (
    <>
      <PageHeader
        title="Data Explorer"
        description="Structured records extracted from documents — raw value and normalized value shown side by side"
      />

      {/* Filters */}
      <section aria-label="Filters" className="card mb-6 p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
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
                  {method.replace("_", " ")}
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
        />
      )}
      {!isLoading && !isError && data && data.items.length > 0 && (
        <>
          <div className="card overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-2.5">Document</th>
                  <th className="px-4 py-2.5">Source</th>
                  <th className="px-4 py-2.5">Entity</th>
                  <th className="px-4 py-2.5">Metric</th>
                  <th className="px-4 py-2.5">Raw value</th>
                  <th className="px-4 py-2.5">Normalized</th>
                  <th className="px-4 py-2.5">Unit</th>
                  <th className="px-4 py-2.5">Period</th>
                  <th className="px-4 py-2.5">Method</th>
                  <th className="px-4 py-2.5">Validation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.map((record: StructuredRecord) => (
                  <tr key={record.id} className="text-gray-700">
                    <td className="max-w-[180px] truncate px-4 py-2.5" title={record.document_filename ?? ""}>
                      {record.document_filename ?? `#${record.document_id}`}
                    </td>
                    <td className="max-w-[160px] truncate px-4 py-2.5 text-xs text-gray-500" title={record.source_reference ?? ""}>
                      {record.source_reference ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 font-medium">{record.entity_name}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{record.metric_name}</td>
                    <td className="px-4 py-2.5 font-mono">{record.value_raw ?? "—"}</td>
                    <td className="px-4 py-2.5 font-mono text-gray-500">
                      {record.normalized_value ?? <span title="Not safely derivable — raw preserved">—</span>}
                    </td>
                    <td className="px-4 py-2.5">{record.unit ?? "—"}</td>
                    <td className="px-4 py-2.5">{record.reporting_period ?? "—"}</td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${methodBadge(record.extraction_method)}`}>
                        {record.extraction_method?.replace("_", " ") ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${validationBadge(record.validation_status)}`}>
                        {record.validation_status}
                      </span>
                    </td>
                  </tr>
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

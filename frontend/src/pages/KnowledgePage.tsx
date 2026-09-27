import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { fetchKnowledgeStats, searchKnowledge } from "@/lib/searchApi";
import type { KnowledgeStats, RetrievalMode, SearchResponse, SearchResultItem } from "@/types/search";

const RETRIEVAL_MODES: RetrievalMode[] = ["lexical", "semantic", "hybrid"];

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

function unitBadge(type: string): string {
  switch (type) {
    case "record":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "page":
      return "bg-blue-50 text-blue-700 border-blue-200";
    case "validation":
      return "bg-purple-50 text-purple-700 border-purple-200";
    default:
      return "bg-gray-100 text-gray-600 border-gray-200";
  }
}

function validationBadge(status: string | null): string {
  switch (status) {
    case "pass":
    case "valid":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "warning":
    case "review_required":
      return "bg-amber-50 text-amber-700 border-amber-200";
    case "error":
    case "failed":
      return "bg-red-50 text-red-700 border-red-200";
    default:
      return "bg-gray-100 text-gray-600 border-gray-200";
  }
}

/** Knowledge / Search page (Step 8 lexical + Step 9 semantic/hybrid modes). */
export default function KnowledgePage() {
  const [queryInput, setQueryInput] = useState("");
  const [filters, setFilters] = useState({
    entity: "",
    metric: "",
    reporting_period: "",
    extraction_method: "",
    validation_status: "",
  });
  const [mode, setMode] = useState<RetrievalMode>("lexical");
  const [applied, setApplied] = useState({ query: "", filters, mode: "lexical" as RetrievalMode });
  const [lastResponse, setLastResponse] = useState<SearchResponse | null>(null);
  const [results, setResults] = useState<SearchResultItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const PAGE_SIZE = 20;

  const loadStats = useCallback(async () => {
    try {
      setStats(await fetchKnowledgeStats());
      setStatsError(null);
    } catch (cause: unknown) {
      setStatsError(cause instanceof Error ? cause.message : "Could not load index statistics.");
    }
  }, []);

  const runSearch = useCallback(
    async (
      query: string,
      activeFilters: typeof filters,
      targetOffset: number,
      activeMode: RetrievalMode,
    ) => {
      setIsLoading(true);
      setIsError(false);
      setError(null);
      try {
        const data = await searchKnowledge({
          q: query || undefined,
          mode: activeMode === "lexical" ? undefined : activeMode,
          entity: activeFilters.entity || undefined,
          metric: activeFilters.metric || undefined,
          reporting_period: activeFilters.reporting_period || undefined,
          extraction_method: activeFilters.extraction_method || undefined,
          validation_status: activeFilters.validation_status || undefined,
          limit: PAGE_SIZE,
          offset: targetOffset,
        });
        setLastResponse(data);
        setResults(data.results);
        setTotal(data.total);
        setOffset(targetOffset);
      } catch (cause: unknown) {
        setLastResponse(null);
        setIsError(true);
        setError(cause instanceof Error ? cause.message : "Search failed.");
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const submit = () => {
    if (mode !== "lexical" && !queryInput.trim()) {
      setIsError(true);
      setError("Semantic and hybrid modes require a text query.");
      return;
    }
    setApplied({ query: queryInput, filters, mode });
    runSearch(queryInput, filters, 0, mode);
  };

  const changeMode = (next: RetrievalMode) => {
    setMode(next);
    if (results === null) return; // no search yet — mode applies on next submit
    if (next !== "lexical" && !applied.query.trim()) return; // need a query first
    setApplied({ query: applied.query, filters: applied.filters, mode: next });
    runSearch(applied.query, applied.filters, 0, next);
  };

  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Knowledge Search"
        description="Deterministic search over documents, structured records and validation results — every result links back to its source"
      />

      {/* Index statistics (actual DB values) */}
      <section aria-label="Index statistics" className="mb-6">
        {statsError ? (
          <p className="text-xs text-gray-400">{statsError}</p>
        ) : stats ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <div className="card p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Documents</p>
              <p className="text-xl font-bold text-gray-900">{stats.documents_indexed}</p>
            </div>
            <div className="card p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Pages</p>
              <p className="text-xl font-bold text-gray-900">{stats.pages_indexed}</p>
            </div>
            <div className="card p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Records</p>
              <p className="text-xl font-bold text-gray-900">{stats.records_indexed}</p>
            </div>
            <div className="card p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Validations</p>
              <p className="text-xl font-bold text-gray-900">{stats.validation_results_indexed}</p>
            </div>
            <div className="card p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Last update</p>
              <p className="truncate text-sm font-semibold text-gray-900" title={stats.last_index_update ?? ""}>
                {stats.last_index_update ? new Date(stats.last_index_update).toLocaleString() : "—"}
              </p>
            </div>
            <div
              className="card p-3"
              title={stats.embedding_models.length ? `Models: ${stats.embedding_models.join(", ")}` : "No units embedded yet"}
            >
              <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Embedded</p>
              <p className="text-xl font-bold text-gray-900">{stats.embedded_units}</p>
              {stats.embedding_error_units > 0 && (
                <p className="text-[10px] font-medium text-amber-600">{stats.embedding_error_units} in error</p>
              )}
            </div>
          </div>
        ) : (
          <div className="card h-16 animate-pulse bg-gray-50" />
        )}
      </section>

      {/* Search form */}
      <section aria-label="Search" className="card mb-6 p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label="Retrieval mode">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Mode</span>
          {RETRIEVAL_MODES.map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => changeMode(m)}
              className={`rounded-md border px-2.5 py-1 text-xs font-semibold capitalize transition-colors ${
                mode === m
                  ? "border-brand-500 bg-brand-50 text-brand-700"
                  : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
              }`}
            >
              {m}
            </button>
          ))}
          {mode !== "lexical" && (
            <span className="text-[11px] text-gray-400">matches meaning, not just keywords — requires a text query</span>
          )}
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className={`${inputClass} flex-1`}
            placeholder='Search… use "quotes" for exact phrases'
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          <button type="button" className="btn-primary sm:w-32" onClick={submit}>
            Search
          </button>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <input
            className={inputClass}
            placeholder="Entity (exact)"
            value={filters.entity}
            onChange={(e) => setFilters({ ...filters, entity: e.target.value })}
          />
          <input
            className={inputClass}
            placeholder="Metric (exact)"
            value={filters.metric}
            onChange={(e) => setFilters({ ...filters, metric: e.target.value })}
          />
          <input
            className={inputClass}
            placeholder="Reporting period"
            value={filters.reporting_period}
            onChange={(e) => setFilters({ ...filters, reporting_period: e.target.value })}
          />
          <select
            className={inputClass}
            value={filters.extraction_method}
            onChange={(e) => setFilters({ ...filters, extraction_method: e.target.value })}
          >
            <option value="">Any method</option>
            <option value="native_text">native text</option>
            <option value="ocr">OCR</option>
            <option value="table">table</option>
            <option value="spreadsheet">spreadsheet</option>
            <option value="docx">docx</option>
          </select>
          <select
            className={inputClass}
            value={filters.validation_status}
            onChange={(e) => setFilters({ ...filters, validation_status: e.target.value })}
          >
            <option value="">Any validation status</option>
            <option value="pass">pass</option>
            <option value="warning">warning</option>
            <option value="error">error</option>
            <option value="review_required">review required</option>
          </select>
        </div>
      </section>

      {/* Results */}
      {isLoading && <StateBlock variant="loading" title="Searching…" />}
      {isError && (
        <StateBlock
          variant="error"
          title="Search failed"
          description={error ?? undefined}
          action={
            <button
              type="button"
              className="btn-primary"
              onClick={() => runSearch(applied.query, applied.filters, offset, applied.mode)}
            >
              Retry
            </button>
          }
        />
      )}
      {!isLoading && !isError && results === null && (
        <StateBlock
          variant="empty"
          title="Search the knowledge base"
          description="Enter a query (use quotes for exact phrases) or filter by entity, metric, period, method or validation status. Results always show their document, page and source reference."
        />
      )}
      {!isLoading && !isError && results !== null && results.length === 0 && (
        <StateBlock
          variant="empty"
          title="No results"
          description="Nothing matched this query/filters. Note: documents appear in the index after processing."
        />
      )}
      {!isLoading && !isError && results !== null && results.length > 0 && (
        <>
          <p className="mb-3 text-sm text-gray-500">
            {total} result{total === 1 ? "" : "s"} · page {currentPage} of {totalPages}
          </p>
          {lastResponse?.semantic_error && (
            <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Semantic retrieval unavailable — {lastResponse.semantic_error}
              {lastResponse.mode === "hybrid" ? " Showing lexical results as fallback." : ""}
            </div>
          )}
          {lastResponse?.retrieval_note && (
            <p className="mb-3 text-[11px] text-gray-400">{lastResponse.retrieval_note}</p>
          )}
          <div className="space-y-3">
            {results.map((item) => (
              <article key={`${item.unit_type}-${item.validation_id ?? item.record_id ?? item.page_id ?? item.document_id}-${item.title ?? ""}`} className="card p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${unitBadge(item.unit_type)}`}>
                    {item.unit_type}
                  </span>
                  {item.validation_status && (
                    <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${validationBadge(item.validation_status)}`}>
                      {item.validation_status.replace("_", " ")}
                    </span>
                  )}
                  {typeof item.ocr_confidence === "number" && (
                    <span className="text-[10px] text-gray-400">
                      OCR confidence {(item.ocr_confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  {item.extraction_method && (
                    <span className="text-[10px] text-gray-400">via {item.extraction_method.replace("_", " ")}</span>
                  )}
                  {(typeof item.rank_score === "number" ||
                    typeof item.semantic_similarity === "number" ||
                    typeof item.relevance === "number") && (
                    <span className="ml-auto flex gap-3 text-[10px] text-gray-300">
                      {typeof item.rank_score === "number" && (
                        <span title="Deterministic lexical relevance score — retrieval metric, not a trust score">
                          lexical {item.rank_score}
                        </span>
                      )}
                      {typeof item.semantic_similarity === "number" && (
                        <span title="Cosine similarity — retrieval metric, never truth, correctness or trust">
                          semantic {item.semantic_similarity.toFixed(3)}
                        </span>
                      )}
                      {typeof item.relevance === "number" && (
                        <span title="Combined hybrid relevance (explicit weighted formula) — retrieval metric, not a trust score">
                          relevance {item.relevance.toFixed(3)}
                        </span>
                      )}
                    </span>
                  )}
                </div>

                <p className="mt-1.5 text-sm font-semibold text-gray-900">
                  {item.document_name ?? `Document #${item.document_id}`}
                  {item.page_number ? ` · page ${item.page_number}` : ""}
                </p>
                {item.title && <p className="text-xs text-gray-500">{item.title}</p>}
                {item.snippet && (
                  <p className="mt-1.5 whitespace-pre-wrap break-words text-sm text-gray-700">{item.snippet}</p>
                )}

                {(item.entity || item.metric || item.value_raw) && (
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
                    {item.entity && <span>entity: <span className="font-medium text-gray-800">{item.entity}</span></span>}
                    {item.metric && <span>metric: <span className="font-mono">{item.metric}</span></span>}
                    {item.value_raw && (
                      <span>
                        value: <span className="font-mono text-gray-800">{item.value_raw}</span>
                        {item.normalized_value && item.normalized_value !== item.value_raw && (
                          <span className="text-gray-400"> → {item.normalized_value}</span>
                        )}
                      </span>
                    )}
                    {item.unit && <span>unit: {item.unit}</span>}
                    {item.reporting_period && <span>period: {item.reporting_period}</span>}
                  </div>
                )}

                <p className="mt-2 text-[11px] text-gray-400">
                  Source: {item.source_reference ?? "—"}
                  {item.document_id ? ` · document #${item.document_id}` : ""}
                </p>
              </article>
            ))}
          </div>

          {total > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-gray-500">
                Page {currentPage} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-secondary !px-3 !py-1.5 text-xs"
                  disabled={offset === 0}
                  onClick={() => runSearch(applied.query, applied.filters, Math.max(0, offset - PAGE_SIZE), applied.mode)}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn-secondary !px-3 !py-1.5 text-xs"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => runSearch(applied.query, applied.filters, offset + PAGE_SIZE, applied.mode)}
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

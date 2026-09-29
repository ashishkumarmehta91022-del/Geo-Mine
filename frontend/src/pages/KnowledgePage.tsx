import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { fetchKnowledgeStats, searchKnowledge } from "@/lib/searchApi";
import type { KnowledgeStats, RetrievalMode, SearchResponse, SearchResultItem } from "@/types/search";

const RETRIEVAL_MODES: RetrievalMode[] = ["lexical", "semantic", "hybrid"];

const MODE_EXPLANATIONS: Record<RetrievalMode, string> = {
  lexical: "Matches source text and exact terms.",
  semantic: "Finds conceptually similar content.",
  hybrid: "Combines lexical and semantic relevance.",
};

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

function unitTone(type: string): BadgeTone {
  switch (type) {
    case "record":
      return "ok";
    case "page":
      return "info";
    case "validation":
      return "review";
    default:
      return "neutral";
  }
}

function validationTone(status: string | null): BadgeTone {
  switch (status) {
    case "pass":
    case "valid":
      return "ok";
    case "warning":
      return "warn";
    case "review_required":
      return "review";
    case "error":
    case "failed":
      return "bad";
    default:
      return "neutral";
  }
}

/** One search result rendered as a traceable evidence card. */
function ResultCard({ item }: { item: SearchResultItem }) {
  const [expanded, setExpanded] = useState(false);
  const chain: { label: string; id: number | null }[] = [
    { label: `Document #${item.document_id}`, id: item.document_id },
    ...(item.page_id !== null && item.page_id !== undefined
      ? [{ label: `Page #${item.page_id}`, id: item.page_id }]
      : []),
    ...(item.record_id !== null && item.record_id !== undefined
      ? [{ label: `Record #${item.record_id}`, id: item.record_id }]
      : []),
    ...(item.validation_id !== null && item.validation_id !== undefined
      ? [{ label: `Validation #${item.validation_id}`, id: item.validation_id }]
      : []),
  ];

  return (
    <article className="card p-4 transition-shadow hover:shadow-md">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={unitTone(item.unit_type)}>{item.unit_type}</Badge>
        {item.validation_status && (
          <Badge tone={validationTone(item.validation_status)}>
            {item.validation_status.split("_").join(" ")}
          </Badge>
        )}
        {item.extraction_method && (
          <span className="text-[10px] uppercase tracking-wide text-gray-400">
            via {item.extraction_method.split("_").join(" ")}
          </span>
        )}
        {typeof item.ocr_confidence === "number" && (
          <span className="text-[10px] text-gray-400">OCR {Math.round(item.ocr_confidence * 100)}%</span>
        )}
        {/* Scores: retrieval metrics only — never presented as trust. */}
        {(typeof item.rank_score === "number" ||
          typeof item.semantic_similarity === "number" ||
          typeof item.relevance === "number") && (
          <span className="ml-auto flex gap-2">
            {typeof item.rank_score === "number" && (
              <span
                className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500"
                title="Deterministic lexical relevance — retrieval metric, not a trust score"
              >
                lexical {item.rank_score.toFixed(2)}
              </span>
            )}
            {typeof item.semantic_similarity === "number" && (
              <span
                className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500"
                title="Cosine similarity — retrieval metric, never truth or trust"
              >
                semantic {item.semantic_similarity.toFixed(3)}
              </span>
            )}
            {typeof item.relevance === "number" && (
              <span
                className="rounded border border-brand-200 bg-brand-50 px-1.5 py-0.5 text-[10px] font-semibold text-brand-700"
                title="Combined hybrid relevance (explicit weighted formula) — retrieval metric, not a trust score"
              >
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
        <p className="mt-1.5 break-words rounded bg-slate-50 px-2.5 py-1.5 font-mono text-xs text-gray-700">
          {item.snippet}
        </p>
      )}

      {(item.entity || item.metric || item.value_raw) && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
          {item.entity && (
            <span>
              entity: <span className="font-medium text-gray-800">{item.entity}</span>
            </span>
          )}
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

      {/* Provenance chain — the core traceability guarantee, visually explicit */}
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-gray-100 pt-2.5">
        <span className="text-[10px] font-bold uppercase tracking-wide text-gray-400">Provenance</span>
        {chain.map((node, i) => (
          <span key={node.label} className="flex items-center gap-1.5">
            {i > 0 && <Icon name="chevron-right" className="h-3 w-3 text-gray-300" aria-hidden="true" />}
            <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-semibold text-gray-600">
              {node.label}
            </span>
          </span>
        ))}
        {item.source_reference && (
          <span className="max-w-[240px] truncate text-[11px] text-gray-500" title={item.source_reference}>
            — {item.source_reference}
          </span>
        )}
        <button
          type="button"
          className="btn-ghost ml-auto !px-2 !py-0.5 text-[11px]"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? "Hide evidence" : "View evidence"}
        </button>
      </div>

      {expanded && (
        <div className="mt-2 grid gap-x-6 gap-y-1.5 rounded bg-slate-50 p-3 text-[11px] sm:grid-cols-2">
          <p>
            <span className="font-semibold text-gray-500">Document:</span>{" "}
            <span className="text-gray-700">
              {item.document_name ?? "—"} (#{item.document_id})
            </span>
          </p>
          <p>
            <span className="font-semibold text-gray-500">Page:</span>{" "}
            <span className="text-gray-700">
              {item.page_number ?? "—"}
              {item.page_id ? ` (id ${item.page_id})` : ""}
            </span>
          </p>
          <p>
            <span className="font-semibold text-gray-500">Record:</span>{" "}
            <span className="text-gray-700">{item.record_id ?? "—"}</span>
          </p>
          <p>
            <span className="font-semibold text-gray-500">Validation:</span>{" "}
            <span className="text-gray-700">
              {item.validation_status ?? "—"}
              {item.validation_id ? ` (id ${item.validation_id})` : ""}
            </span>
          </p>
          <p>
            <span className="font-semibold text-gray-500">Source reference:</span>{" "}
            <span className="break-all text-gray-700">{item.source_reference ?? "—"}</span>
          </p>
          <p>
            <span className="font-semibold text-gray-500">Extraction method:</span>{" "}
            <span className="text-gray-700">{item.extraction_method?.split("_").join(" ") ?? "—"}</span>
          </p>
        </div>
      )}
    </article>
  );
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
  const [searchParams] = useSearchParams();
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

  // Step 13 search integration: /knowledge?q=<topic-term> deep-link from
  // the Topic Intelligence page — reuses the EXISTING search layer.
  const deepLinkQuery = searchParams.get("q") ?? "";
  useEffect(() => {
    if (!deepLinkQuery.trim()) return;
    setQueryInput(deepLinkQuery);
    setApplied({ query: deepLinkQuery, filters, mode });
    runSearch(deepLinkQuery, filters, 0, mode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLinkQuery]);

  const submit = () => {
    if (mode !== "lexical" && !queryInput.trim()) {
      setIsError(true);
      setError("Semantic and hybrid modes require a text query.");
      return;
    }
    setApplied({ query: queryInput, filters, mode });
    runSearch(queryInput, filters, 0, mode);
  };

  const clearSearch = () => {
    setQueryInput("");
    setResults(null);
    setLastResponse(null);
    setTotal(0);
    setOffset(0);
    setIsError(false);
    setError(null);
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
        description="Search across validated geological, mining and production knowledge with source-level traceability."
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

      {/* Search form — the primary visual focus */}
      <section aria-label="Search" className="card mb-6 p-5">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4.5 w-4.5 h-5 w-5 -translate-y-1/2 text-gray-400" />
            <input
              className={`${inputClass} !py-2.5 pl-10 text-base`}
              placeholder='Search… use "quotes" for exact phrases'
              aria-label="Search query"
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
            {queryInput && (
              <button
                type="button"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                onClick={clearSearch}
                aria-label="Clear search"
              >
                <Icon name="close" className="h-4 w-4" />
              </button>
            )}
          </div>
          <button type="button" className="btn-primary sm:w-32" onClick={submit}>
            Search
          </button>
        </div>

        {/* Mode selector with explanations */}
        <div className="mt-4" role="group" aria-label="Retrieval mode">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Mode</span>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {RETRIEVAL_MODES.map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={mode === m}
                onClick={() => changeMode(m)}
                className={`rounded-md border px-3 py-1.5 text-xs font-semibold capitalize transition-colors ${
                  mode === m
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-surface text-gray-600 hover:border-gray-300"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-[11px] text-gray-500">{MODE_EXPLANATIONS[mode]}</p>
        </div>

        {/* Exact-match filters */}
        <div className="mt-4 grid grid-cols-1 gap-3 border-t border-gray-100 pt-4 sm:grid-cols-3 lg:grid-cols-5">
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
      {isLoading && <StateBlock variant="loading" title="Searching the knowledge base…" />}
      {isError && (
        <StateBlock
          variant="error"
          title="Knowledge retrieval unavailable"
          description={
            error && !error.startsWith("Cannot reach")
              ? error
              : "The search index could not be queried — the database may be offline. The rest of the platform is unaffected."
          }
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
          title="Search your knowledge base"
          description="Retrieve evidence from processed geological, mining and production documents. Every result links back to its source."
        />
      )}
      {!isLoading && !isError && results !== null && results.length === 0 && (
        <StateBlock
          variant="empty"
          title="No matching evidence found"
          description="Try broader terms or another search mode. Documents appear in the index after processing."
        />
      )}
      {!isLoading && !isError && results !== null && results.length > 0 && (
        <>
          <p className="mb-3 text-sm text-gray-500" aria-live="polite">
            {total} result{total === 1 ? "" : "s"} · page {currentPage} of {totalPages} ·{" "}
            <span className="text-gray-400">Results are linked to source evidence.</span>
          </p>
          {lastResponse?.semantic_error && (
            <div className="mb-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <Icon name="warn" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                Semantic retrieval unavailable — {lastResponse.semantic_error}
                {lastResponse.mode === "hybrid" ? " Showing lexical results as fallback." : ""}
              </span>
            </div>
          )}
          {lastResponse?.retrieval_note && (
            <p className="mb-3 text-[11px] text-gray-400">{lastResponse.retrieval_note}</p>
          )}
          <div className="space-y-3">
            {results.map((item) => (
              <ResultCard
                key={`${item.unit_type}-${item.validation_id ?? item.record_id ?? item.page_id ?? item.document_id}-${item.title ?? ""}`}
                item={item}
              />
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

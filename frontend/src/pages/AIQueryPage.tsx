import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { ApiError } from "@/lib/api";
import { apiBaseUrl } from "@/lib/env";
import type { AIQueryResponse } from "@/types/aiQuery";

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

function statusBadge(status: string): { label: string; className: string } {
  switch (status) {
    case "ok":
      return { label: "ANSWERED FROM EVIDENCE", className: "bg-emerald-50 text-emerald-700 border-emerald-200" };
    case "insufficient_evidence":
      return { label: "INSUFFICIENT EVIDENCE", className: "bg-amber-50 text-amber-700 border-amber-200" };
    case "llm_error":
      return { label: "LLM ERROR", className: "bg-red-50 text-red-700 border-red-200" };
    default: // llm_unavailable
      return { label: "LLM NOT CONFIGURED", className: "bg-gray-100 text-gray-600 border-gray-200" };
  }
}

/** AI Query (Step 10 API) — grounded Q&A over the knowledge index. */
export default function AIQueryPage() {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"hybrid" | "lexical">("hybrid");
  const [result, setResult] = useState<AIQueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = useCallback(async () => {
    const trimmed = question.trim();
    if (!trimmed) return;
    setIsLoading(true);
    setIsError(false);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl()}/api/ai/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ question: trimmed, mode }),
      });
      if (!response.ok) {
        let message = `AI query failed with status ${response.status}.`;
        try {
          const body = (await response.json()) as { error?: { message?: string } };
          if (body.error?.message) message = body.error.message;
        } catch {
          // keep generic message
        }
        throw new ApiError(message, response.status);
      }
      setResult((await response.json()) as AIQueryResponse);
    } catch (cause: unknown) {
      setIsError(true);
      setError(cause instanceof Error ? cause.message : "The AI query failed.");
    } finally {
      setIsLoading(false);
    }
  }, [question, mode]);

  useEffect(() => {
    return () => {
      /* no in-flight cancellation needed for a single bounded POST */
    };
  }, []);

  return (
    <>
      <PageHeader
        title="AI Query"
        description="Ask questions answered ONLY from retrieved project evidence — the assistant never invents data and never resolves conflicting sources"
      />

      <section aria-label="Ask a question" className="card mb-6 p-4">
        <textarea
          className={`${inputClass} min-h-[80px]`}
          placeholder="e.g. What coal production values are reported for the mine?"
          maxLength={500}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            Retrieval mode
            <select
              className="rounded-md border border-gray-300 px-2 py-1.5 text-sm"
              value={mode}
              onChange={(e) => setMode(e.target.value as "hybrid" | "lexical")}
            >
              <option value="hybrid">Hybrid (lexical + semantic)</option>
              <option value="lexical">Lexical</option>
            </select>
          </label>
          <button type="button" className="btn-primary" disabled={isLoading || !question.trim()} onClick={ask}>
            {isLoading ? "Analyzing evidence…" : "Ask"}
          </button>
          <span className="text-xs text-gray-400">{question.length}/500</span>
        </div>
        <p className="mt-2 text-xs text-gray-400">
          If no LLM provider is configured you will still see the retrieved evidence with an honest
          "LLM not configured" status — no fabricated answers are ever produced.
        </p>
      </section>

      {isLoading && <StateBlock variant="loading" title="Retrieving evidence and generating the answer…" />}
      {isError && (
        <StateBlock
          variant="error"
          title="AI query failed"
          description={error ?? undefined}
          action={<button type="button" className="btn-primary" onClick={ask}>Retry</button>}
        />
      )}

      {!isLoading && !isError && result && (
        <div className="space-y-6">
          <section aria-label="Answer" className="card p-5">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${statusBadge(result.status).className}`}>
                {statusBadge(result.status).label}
              </span>
              {result.provider && (
                <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
                  provider: {result.provider}
                </span>
              )}
              {result.latency_ms !== null && result.latency_ms !== undefined && (
                <span className="text-[10px] text-gray-400">{result.latency_ms} ms</span>
              )}
            </div>
            <p className="whitespace-pre-wrap text-sm text-gray-800">
              {result.answer ?? "No answer was generated — see the status above."}
            </p>
            <p className="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-500">
              {result.grounding_note}
            </p>
            {result.limitations && (
              <p className="mt-1 text-xs text-amber-700">Limitations: {result.limitations}</p>
            )}
          </section>

          {result.conflicts.length > 0 && (
            <section aria-label="Conflicts" className="card border-amber-200 bg-amber-50 p-5">
              <h2 className="text-sm font-bold uppercase tracking-wide text-amber-700">
                Conflicting values — review required
              </h2>
              {result.conflicts.map((conflict, index) => (
                <div key={index} className="mt-2 text-sm text-amber-800">
                  <p className="font-semibold">
                    {[conflict.entity, conflict.metric, conflict.reporting_period].filter(Boolean).join(" · ")}
                  </p>
                  <p className="font-mono text-xs">values: {conflict.values.join(" | ")}</p>
                  <p className="text-xs text-amber-700">Evidence ids: {conflict.evidence_ids.join(", ")}</p>
                </div>
              ))}
              <p className="mt-2 text-xs text-amber-700">
                Both sources are preserved; the platform never selects a winning value.
              </p>
            </section>
          )}

          <section aria-label="Evidence" className="card p-5">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-gray-600">
              Evidence ({result.evidence.length})
            </h2>
            {result.evidence.length === 0 ? (
              <p className="text-sm text-gray-500">
                No evidence was retrieved. Process and index documents first.
              </p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {result.evidence.map((item) => (
                  <li key={item.evidence_id} className="py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 font-mono text-[10px] font-bold text-gray-500">
                        [{item.evidence_id}]
                      </span>
                      <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
                        {item.unit_type}
                      </span>
                      {item.document_name && (
                        <span className="max-w-[240px] truncate text-sm font-medium text-gray-800" title={item.document_name}>
                          {item.document_name}
                        </span>
                      )}
                      {item.page_number !== null && item.page_number !== undefined && (
                        <span className="text-xs text-gray-400">page {item.page_number}</span>
                      )}
                      {item.validation_status && (
                        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${
                          item.validation_status === "pass" || item.validation_status === "valid"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : "border-amber-200 bg-amber-50 text-amber-700"
                        }`}>
                          {item.validation_status}
                        </span>
                      )}
                    </div>
                    {item.snippet && <p className="mt-1 text-sm text-gray-600">{item.snippet}</p>}
                    <p className="mt-1 text-[11px] text-gray-400">
                      doc {item.document_id}
                      {item.record_id !== null && item.record_id !== undefined ? ` · record ${item.record_id}` : ""}
                      {item.source_reference ? ` · ${item.source_reference}` : ""}
                      {item.extraction_method ? ` · via ${item.extraction_method}` : ""}
                      {item.ocr_confidence !== null && item.ocr_confidence !== undefined
                        ? ` · OCR ${Math.round(item.ocr_confidence * 100)}%`
                        : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {result.retrieval_note && (
            <p className="text-xs text-gray-400">{result.retrieval_note}</p>
          )}
        </div>
      )}

      {!isLoading && !isError && !result && (
        <StateBlock
          variant="empty"
          title="No query yet"
          description="Ask a question — answers are grounded exclusively in the indexed project documents, with full evidence citations."
        />
      )}
    </>
  );
}

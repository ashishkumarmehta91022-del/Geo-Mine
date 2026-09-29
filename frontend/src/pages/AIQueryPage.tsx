import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { fetchDashboardStatuses } from "@/lib/dashboardApi";
import { networkError } from "@/lib/api";
import { apiBaseUrl } from "@/lib/env";
import type { AIQueryResponse } from "@/types/aiQuery";
import type { DashboardStatuses } from "@/types/dashboard";

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

/** Example questions grounded in the actual synthetic demo domain. */
const EXAMPLE_QUESTIONS = [
  "What was the coal production for Demo Mine Delta in September 2025?",
  "Which records require review?",
  "Show production information available for the selected period.",
];

/** AI pipeline stage strip — communicates the evidence-first flow. */
function QueryPipeline({ active }: { active: boolean }) {
  const stages = ["Question", "Evidence Retrieval", "Validation / Conflict Check", "AI Answer"];
  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label="AI query pipeline">
      {stages.map((stage, i) => (
        <li key={stage} className="flex items-center gap-1.5">
          <span
            className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[10px] font-semibold ${
              active
                ? "border-brand-300 bg-brand-50 text-brand-700"
                : "border-gray-200 bg-gray-50 text-gray-500"
            }`}
          >
            {active && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" aria-hidden="true" />}
            {stage}
          </span>
          {i < stages.length - 1 && <Icon name="chevron-right" className="h-3 w-3 text-gray-300" aria-hidden="true" />}
        </li>
      ))}
    </ol>
  );
}

function validationTone(status: string | null | undefined): BadgeTone {
  switch (status) {
    case "pass":
    case "valid":
      return "ok";
    case "warning":
      return "warn";
    case "error":
    case "failed":
      return "bad";
    case "review_required":
      return "review";
    default:
      return "neutral";
  }
}

function statusBadge(status: string): { label: string; tone: BadgeTone } {
  switch (status) {
    case "ok":
      return { label: "ANSWERED FROM EVIDENCE", tone: "ok" };
    case "insufficient_evidence":
      return { label: "INSUFFICIENT EVIDENCE", tone: "warn" };
    case "llm_error":
      return { label: "LLM ERROR", tone: "bad" };
    default: // llm_unavailable
      return { label: "LLM NOT CONFIGURED", tone: "neutral" };
  }
}

/** AI Query (Step 10 API) — evidence-first grounded Q&A. */
export default function AIQueryPage() {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"hybrid" | "lexical">("hybrid");
  const [result, setResult] = useState<AIQueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [llmNotConfigured, setLlmNotConfigured] = useState(false);
  const [statuses, setStatuses] = useState<DashboardStatuses | null>(null);
  const { error: toastError } = useToast();

  useEffect(() => {
    fetchDashboardStatuses().then(setStatuses).catch(() => setStatuses(null));
  }, []);

  const ask = useCallback(
    async (rawQuestion?: string) => {
      const trimmed = (rawQuestion ?? question).trim();
      if (!trimmed) return;
      setQuestion(trimmed);
      setIsLoading(true);
      setIsError(false);
      setError(null);
      setLlmNotConfigured(false);
      try {
        let response: Response;
        try {
          response = await fetch(`${apiBaseUrl()}/api/ai/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ question: trimmed, mode }),
          });
        } catch {
          throw networkError();
        }
        if (!response.ok) {
          let message = `AI query failed with status ${response.status}.`;
          let code: string | null = null;
          try {
            const body = (await response.json()) as { error?: { message?: string; code?: string } };
            if (body.error?.message) message = body.error.message;
            if (body.error?.code) code = body.error.code;
          } catch {
            // keep generic message
          }
          // Implemented 503 contract: evidence was retrieved but no LLM is
          // configured. Informational state, not a failure.
          if (response.status === 503 && code === "llm_unavailable") {
            setLlmNotConfigured(true);
            return;
          }
          throw new Error(message);
        }
        setResult((await response.json()) as AIQueryResponse);
      } catch (cause: unknown) {
        setIsError(true);
        const message = cause instanceof Error ? cause.message : "The AI query failed.";
        setError(message);
        toastError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [question, mode, toastError],
  );

  const reset = () => {
    setQuestion("");
    setResult(null);
    setIsError(false);
    setError(null);
    setLlmNotConfigured(false);
  };

  const retrievalOk = statuses?.retrieval.status === "OPERATIONAL";
  const embeddingsOk = statuses?.embeddings.status === "OPERATIONAL";
  const llmOk = statuses?.llm.status === "OPERATIONAL";

  return (
    <>
      <PageHeader
        title="AI Query"
        description="Ask questions across validated geological, mining and production information."
      />

      {/* Pipeline status panel — partial operability stated honestly */}
      <section aria-label="Pipeline status" className="mb-6">
        <div className="card flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3">
          <QueryPipeline active={isLoading} />
          <div className="ml-auto flex flex-wrap items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${retrievalOk ? "bg-emerald-500" : "bg-amber-400"}`} aria-hidden="true" />
              <span className="font-medium text-gray-600">Retrieval</span>
              <span className={retrievalOk ? "text-emerald-700" : "text-gray-500"}>
                {retrievalOk ? "✓ Operational" : "— Unavailable"}
              </span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${embeddingsOk ? "bg-emerald-500" : "bg-gray-300"}`} aria-hidden="true" />
              <span className="font-medium text-gray-600">Embeddings</span>
              <span className={embeddingsOk ? "text-emerald-700" : "text-gray-500"}>
                {embeddingsOk ? "✓ Operational" : "— Not embedded"}
              </span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${llmOk ? "bg-emerald-500" : "bg-gray-300"}`} aria-hidden="true" />
              <span className="font-medium text-gray-600">LLM</span>
              <span className={llmOk ? "text-emerald-700" : "text-gray-500"}>
                {llmOk ? "✓ Operational" : "— Not Configured"}
              </span>
            </span>
          </div>
        </div>
      </section>

      {/* Query panel */}
      <section aria-label="Ask a question" className="card mb-6 p-5">
        <label htmlFor="ai-question" className="sr-only">
          Your question
        </label>
        <textarea
          id="ai-question"
          className={`${inputClass} min-h-[84px] text-base`}
          placeholder="e.g. What coal production values are reported for the mine?"
          maxLength={500}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) ask();
          }}
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
          <button
            type="button"
            className="btn-primary"
            disabled={isLoading || !question.trim()}
            onClick={() => ask()}
          >
            {isLoading ? "Analyzing evidence…" : "Ask AI"}
          </button>
          {(question || result || llmNotConfigured) && (
            <button type="button" className="btn-ghost" onClick={reset}>
              Clear
            </button>
          )}
          <span className="text-xs text-gray-400">{question.length}/500</span>
          <span className="hidden text-[11px] text-gray-400 sm:block">Ctrl+Enter to submit</span>
        </div>

        {/* Example questions — populate on click */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Try:</span>
          {EXAMPLE_QUESTIONS.map((example) => (
            <button
              key={example}
              type="button"
              className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-[11px] text-gray-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
              onClick={() => {
                setQuestion(example);
                ask(example);
              }}
            >
              {example}
            </button>
          ))}
        </div>
      </section>

      {isLoading && <StateBlock variant="loading" title="Retrieving evidence and checking for conflicts…" />}

      {/* 503 llm_unavailable — informational, evidence stays available */}
      {llmNotConfigured && (
        <section aria-label="AI generation not configured" className="card mb-6 border-brand-200 bg-brand-50/40 p-6">
          <div className="flex flex-col items-center text-center">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-brand-100 text-brand-700">
              <Icon name="info" className="h-5 w-5" />
            </span>
            <h3 className="mt-3 text-base font-semibold text-gray-900">AI generation is not configured</h3>
            <p className="mt-1 max-w-lg text-sm text-gray-600">
              Evidence retrieval is operational. Configure an approved LLM provider to enable
              generated natural-language answers — meanwhile the platform still searches, validates,
              reports and reasons over evidence without one.
            </p>
            <div className="mt-3 flex gap-2">
              <Link to="/knowledge" className="btn-secondary">Search the knowledge base</Link>
            </div>
            <p className="mt-3 text-xs text-gray-500">
              No fabricated answers are ever produced. Every response is built only from retrieved,
              validated project evidence.
            </p>
          </div>
        </section>
      )}

      {isError && (
        <StateBlock
          variant="error"
          title="AI query failed"
          description={error ?? undefined}
          action={<button type="button" className="btn-primary" onClick={() => ask()}>Retry</button>}
        />
      )}

      {!isLoading && !isError && result && (
        <div className="space-y-6">
          {/* Conflict banner — both values, no winner */}
          {(result.conflict_detected || result.conflicts.length > 0) && (
            <section
              aria-label="Conflicting values"
              className="card border-amber-300 bg-amber-50/70 p-5"
              role="alert"
            >
              <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-amber-800">
                <Icon name="warn" className="h-4 w-4" />
                Conflicting source values detected
              </h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {result.conflicts.flatMap((conflict, ci) =>
                  conflict.values.map((value, vi) => (
                    <div
                      key={`${ci}-${vi}`}
                      className="rounded-md border border-amber-200 bg-white px-3 py-2.5"
                    >
                      <p className="text-[11px] font-bold uppercase tracking-wide text-amber-700">
                        {conflict.entity ?? "Unknown entity"}
                        {conflict.reporting_period ? ` · ${conflict.reporting_period}` : ""}
                      </p>
                      <p className="mt-0.5 text-lg font-bold text-gray-900">{value}</p>
                    </div>
                  )),
                )}
              </div>
              <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-amber-800">
                Human review required — both sources are preserved; the platform never selects a
                winning value.
              </p>
            </section>
          )}

          {/* Insufficient evidence */}
          {result.status === "insufficient_evidence" && (
            <section aria-label="Insufficient evidence" className="card p-5">
              <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-amber-700">
                <Icon name="info" className="h-4 w-4" />
                Insufficient evidence
              </h2>
              <p className="mt-1 text-sm text-gray-600">
                Available sources do not provide enough validated information to answer this
                question reliably.
              </p>
            </section>
          )}

          {/* Answer — visually secondary to evidence */}
          {result.answer && (
            <section aria-label="Answer" className="card p-5">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Badge tone={statusBadge(result.status).tone}>{statusBadge(result.status).label}</Badge>
                {result.provider && (
                  <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
                    provider: {result.provider}
                  </span>
                )}
                {result.latency_ms !== null && result.latency_ms !== undefined && (
                  <span className="text-[10px] text-gray-400">{result.latency_ms} ms</span>
                )}
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800">{result.answer}</p>
              <p className="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-500">{result.grounding_note}</p>
              {result.limitations && <p className="mt-1 text-xs text-amber-700">Limitations: {result.limitations}</p>}
            </section>
          )}

          {/* Evidence — the primary output */}
          <section aria-label="Evidence" className="card p-5">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-bold uppercase tracking-wide text-gray-600">
                Evidence ({result.evidence.length})
              </h2>
              <Link to="/knowledge" className="text-xs font-semibold text-brand-600 hover:underline">
                Explore retrieved evidence →
              </Link>
            </div>
            {result.evidence.length === 0 ? (
              <p className="py-4 text-center text-sm text-gray-500">
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
                      <Badge tone="neutral">{item.unit_type}</Badge>
                      {item.document_name && (
                        <span
                          className="max-w-[260px] truncate text-sm font-medium text-gray-800"
                          title={item.document_name}
                        >
                          {item.document_name}
                        </span>
                      )}
                      {item.page_number !== null && item.page_number !== undefined && (
                        <span className="text-xs text-gray-400">page {item.page_number}</span>
                      )}
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
                    </div>
                    {item.snippet && (
                      <p className="mt-1.5 break-words rounded bg-slate-50 px-2.5 py-1.5 font-mono text-xs text-gray-700">
                        {item.snippet}
                      </p>
                    )}
                    {item.value_raw && (
                      <p className="mt-1 text-xs text-gray-600">
                        value: <span className="font-mono font-semibold text-gray-800">{item.value_raw}</span>
                        {item.normalized_value && item.normalized_value !== item.value_raw && (
                          <span className="text-gray-400"> → {item.normalized_value}</span>
                        )}
                        {item.unit ? ` ${item.unit}` : ""}
                      </p>
                    )}
                    {/* Provenance chain */}
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-gray-500">
                      <span className="font-semibold uppercase tracking-wide text-gray-400">Provenance</span>
                      <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5">
                        Document #{item.document_id}
                      </span>
                      {item.page_id != null && (
                        <Icon name="chevron-right" className="h-3 w-3 text-gray-300" aria-hidden="true" />
                      )}
                      {item.page_id != null && (
                        <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5">
                          Page #{item.page_id}
                        </span>
                      )}
                      {item.record_id != null && (
                        <>
                          <Icon name="chevron-right" className="h-3 w-3 text-gray-300" aria-hidden="true" />
                          <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5">
                            Record #{item.record_id}
                          </span>
                        </>
                      )}
                      {item.source_reference && <span>— {item.source_reference}</span>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {result.retrieval_note && <p className="text-xs text-gray-400">{result.retrieval_note}</p>}
        </div>
      )}

      {!isLoading && !isError && !result && !llmNotConfigured && (
        <StateBlock
          variant="empty"
          title="No query yet"
          description="Ask a question — answers are grounded exclusively in the indexed project documents, with full evidence citations. Try an example above."
        />
      )}
    </>
  );
}

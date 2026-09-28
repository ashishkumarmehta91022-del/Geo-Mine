import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { fetchDashboardSummary } from "@/lib/dashboardApi";
import type { DashboardStatus, DashboardSummary } from "@/types/dashboard";

/** Honest status tone — an unavailable dependency must never look healthy. */
function statusTone(status: string): string {
  switch (status) {
    case "OPERATIONAL":
    case "CONNECTED":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "DEGRADED":
      return "bg-amber-50 text-amber-700 border-amber-200";
    case "NOT CONFIGURED":
      return "bg-gray-100 text-gray-600 border-gray-200";
    default: // UNAVAILABLE and anything unexpected
      return "bg-red-50 text-red-700 border-red-200";
  }
}

function StatusTile({ status }: { status: DashboardStatus }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          {status.component}
        </p>
        <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${statusTone(status.status)}`}>
          {status.status}
        </span>
      </div>
      {status.detail && <p className="mt-1.5 text-[11px] leading-snug text-gray-500">{status.detail}</p>}
    </div>
  );
}

function MetricTile({
  label,
  value,
  hint,
  tone = "neutral",
  to,
}: {
  label: string;
  value: number | string;
  hint?: string;
  tone?: "ok" | "warn" | "bad" | "neutral";
  to?: string;
}) {
  const toneClass =
    tone === "ok" ? "text-emerald-700"
    : tone === "warn" ? "text-amber-700"
    : tone === "bad" ? "text-red-700"
    : "text-gray-800";
  const body = (
    <div className="card h-full p-4 transition-shadow hover:shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${toneClass}`}>{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-gray-400">{hint}</p>}
    </div>
  );
  return to ? <Link to={to} className="block">{body}</Link> : body;
}

function SectionCard({
  title,
  subtitle,
  children,
  linkTo,
  linkLabel,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  linkTo?: string;
  linkLabel?: string;
}) {
  return (
    <section aria-label={title} className="card p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wide text-gray-600">{title}</h3>
          {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
        </div>
        {linkTo && (
          <Link to={linkTo} className="text-xs font-semibold text-brand-600 underline">
            {linkLabel ?? "Open"} →
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

function statusBadge(status: string): string {
  switch (status) {
    case "processed":
    case "pass":
    case "valid":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "warning":
      return "bg-amber-50 text-amber-700 border-amber-200";
    case "failed":
    case "error":
      return "bg-red-50 text-red-700 border-red-200";
    case "review_required":
      return "bg-purple-50 text-purple-700 border-purple-200";
    default:
      return "bg-gray-100 text-gray-600 border-gray-200";
  }
}

/**
 * Production Dashboard (Step 14): read-only operational entry point over the
 * existing platform modules. Handles offline/empty states honestly — it
 * never shows fabricated numbers when the database cannot be queried.
 */
export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setError(null);
    try {
      setSummary(await fetchDashboardSummary());
    } catch (cause: unknown) {
      setIsError(true);
      setError(cause instanceof Error ? cause.message : "Could not load the dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const offline = summary !== null && !summary.data_available;

  return (
    <>
      <PageHeader
        title="Operations Dashboard"
        description="Read-only operational view over the platform's source-of-truth data — documents, validation, knowledge, intelligence, reports"
        actions={
          <button type="button" className="btn-secondary" onClick={load}>
            Refresh
          </button>
        }
      />

      {isLoading && <StateBlock variant="loading" title="Loading operational summary…" />}
      {isError && (
        <StateBlock
          variant="error"
          title="Cannot reach the backend API"
          description={error ?? undefined}
          action={<button type="button" className="btn-primary" onClick={load}>Retry</button>}
        />
      )}

      {!isLoading && !isError && summary && (
        <div className="space-y-6">
          {/* A. System health */}
          <section aria-label="System health">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">System health</h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <StatusTile status={summary.api} />
              <StatusTile status={summary.database} />
              <StatusTile status={summary.retrieval} />
              <StatusTile status={summary.embeddings} />
              <StatusTile status={summary.llm} />
            </div>
          </section>

          {/* Offline banner: distinguish "cannot query" from "0 records". */}
          {offline && (
            <section aria-label="Offline state">
              <div className="rounded-md border border-amber-300 bg-amber-50 p-4">
                <p className="text-sm font-semibold text-amber-800">Database unavailable — no live data</p>
                <p className="mt-1 text-xs text-amber-700">{summary.message}</p>
                <p className="mt-1 text-xs text-amber-600">
                  Metric sections below are intentionally blank; no demo values are shown.
                </p>
              </div>
            </section>
          )}

          {/* B. Key operational metrics */}
          {!offline && summary.documents && summary.records && summary.validation && summary.knowledge && (
            <section aria-label="Key operational metrics">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Key metrics</h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                <MetricTile label="Documents" value={summary.documents.total} hint={`${summary.documents.processed} processed`} to="/documents" />
                <MetricTile label="Structured records" value={summary.records.total} hint={`${summary.records.validated} validated`} to="/data-explorer" />
                <MetricTile label="Indexed units" value={summary.knowledge.total_units} hint={`${summary.knowledge.pages} pages · ${summary.knowledge.records} records`} to="/knowledge" />
                <MetricTile label="Validation pass" value={summary.validation.by_status["pass"] ?? 0} tone="ok" to="/validation" />
                <MetricTile label="Warnings / errors" value={(summary.validation.warnings ?? 0) + (summary.validation.errors ?? 0)} tone="warn" to="/validation" />
                <MetricTile label="Review required" value={summary.validation.review_required} tone={summary.validation.review_required > 0 ? "warn" : "neutral"} to="/validation" />
              </div>
            </section>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* C. Documents / processing */}
            {!offline && summary.documents && ((): JSX.Element | null => {
              const documents = summary.documents;
              if (!documents) return null;
              return (
              <SectionCard title="Documents & processing" subtitle="Lifecycle status of uploaded reports" linkTo="/documents" linkLabel="All documents">
                <dl className="space-y-2 text-sm">
                  {(["uploaded", "processing", "processed", "failed"] as const).map((key) => (
                    <div key={key} className="flex items-center justify-between gap-3">
                      <dt className="capitalize text-gray-600">{key}</dt>
                      <dd className="font-mono font-semibold text-gray-800">{documents.by_status[key] ?? 0}</dd>
                    </div>
                  ))}
                </dl>
              </SectionCard>
              );
            })()}

            {/* D/E. Validation & review + Knowledge & intelligence */}
            {!offline && summary.validation && (
              <SectionCard title="Validation & review" subtitle="Rule outcomes across extracted data" linkTo="/validation" linkLabel="Review queue">
                <dl className="space-y-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-gray-600">Pass</dt>
                    <dd className="font-mono font-semibold text-emerald-700">{summary.validation.by_status["pass"] ?? 0}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-gray-600">Warning</dt>
                    <dd className="font-mono font-semibold text-amber-700">{summary.validation.warnings}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-gray-600">Error</dt>
                    <dd className="font-mono font-semibold text-red-700">{summary.validation.errors}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-gray-600">Review required</dt>
                    <dd className="font-mono font-semibold text-purple-700">{summary.validation.review_required}</dd>
                  </div>
                </dl>
                <p className="mt-3 text-[11px] text-gray-400">
                  Conflicted values stay marked REVIEW REQUIRED — the platform never picks a winning value.
                </p>
              </SectionCard>
            )}
          </div>

          {/* F. Knowledge & intelligence */}
          {!offline && summary.knowledge && summary.intelligence && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <SectionCard title="Knowledge & retrieval" subtitle={`${summary.knowledge.documents_indexed} document(s) indexed`} linkTo="/knowledge" linkLabel="Knowledge Search">
                <dl className="space-y-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-gray-600">Indexed units</dt>
                    <dd className="font-mono font-semibold text-gray-800">{summary.knowledge.total_units}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-gray-600">Embedded units</dt>
                    <dd className="font-mono font-semibold text-gray-800">
                      {summary.knowledge.embedded_units}
                      <span className="ml-1 text-xs font-normal text-gray-400">
                        ({Math.round(summary.knowledge.embedding_coverage * 100)}% coverage)
                      </span>
                    </dd>
                  </div>
                </dl>
              </SectionCard>
              <SectionCard title="Intelligence & topics" subtitle={summary.intelligence.available ? "Deterministic topic engine active" : "Not yet available"} linkTo="/topic-intelligence" linkLabel="Topic Intelligence">
                {summary.intelligence.available ? (
                  <>
                    <p className="text-sm text-gray-600">
                      {summary.intelligence.topic_count} topic(s) derived from {summary.intelligence.indexed_documents} indexed document(s).
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {summary.intelligence.top_topics.map((topic) => (
                        <span key={topic.topic_id} className="rounded-full border border-brand-200 bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700">
                          {topic.label}
                        </span>
                      ))}
                    </div>
                    {summary.intelligence.top_terms.length > 0 && (
                      <p className="mt-2 text-[11px] text-gray-400">
                        Top terms: {summary.intelligence.top_terms.map((term) => term.display_term).slice(0, 6).join(", ")}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-gray-500">{summary.intelligence.detail ?? "No indexed content to analyze yet."}</p>
                )}
              </SectionCard>
            </div>
          )}

          {/* G. Reports & analytics entry points */}
          <section aria-label="Platform modules">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Reports & analytics</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { to: "/report-generator", label: "Report Generator", description: "Deterministic DOCX reports" },
                { to: "/report-generator", label: "Report Analytics", description: "KPIs, trends, comparisons" },
                { to: "/knowledge", label: "Knowledge Search", description: "Lexical · semantic · hybrid" },
                { to: "/ai-query", label: "AI Query", description: "Grounded Q&A over evidence" },
                { to: "/topic-intelligence", label: "Topic Intelligence", description: "Keywords, topics, cloud" },
                { to: "/validation", label: "Validation / Review", description: "Rule outcomes & review queue" },
                { to: "/documents", label: "Documents", description: "Upload & processing" },
                { to: "/data-explorer", label: "Data Explorer", description: "Structured records" },
              ].map((item) => (
                <Link key={item.label} to={item.to} className="card block p-4 transition-shadow hover:shadow-sm">
                  <p className="text-sm font-semibold text-gray-800">{item.label}</p>
                  <p className="mt-0.5 text-xs text-gray-400">{item.description}</p>
                </Link>
              ))}
            </div>
          </section>

          {/* H. Recent documents / activity */}
          {!offline && summary.recent_documents.length > 0 && (
            <SectionCard title="Recent documents" subtitle="Metadata only — click through for details" linkTo="/documents" linkLabel="All documents">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                      <th className="px-3 py-2">Document</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2">Validation</th>
                      <th className="px-3 py-2">Records</th>
                      <th className="px-3 py-2">Review</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {summary.recent_documents.map((document) => (
                      <tr key={document.document_id} className="text-gray-700">
                        <td className="max-w-[220px] truncate px-3 py-2 font-medium" title={document.filename}>
                          <Link to="/documents" className="hover:text-brand-700">{document.filename}</Link>
                          <span className="ml-1 text-[10px] text-gray-400">{document.document_type}</span>
                        </td>
                        <td className="px-3 py-2">
                          <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${statusBadge(document.status)}`}>
                            {document.status}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${statusBadge(document.validation_status ?? "")}`}>
                            {document.validation_status ?? "—"}
                          </span>
                        </td>
                        <td className="px-3 py-2 font-mono">{document.record_count}</td>
                        <td className="px-3 py-2">
                          {document.requires_review ? (
                            <Link to="/validation" className="rounded border border-purple-200 bg-purple-50 px-1.5 py-0.5 text-[10px] font-semibold text-purple-700">
                              REVIEW →
                            </Link>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          )}

          {!offline && summary.recent_activity.length > 0 && (
            <SectionCard title="Recent platform activity" subtitle="Audit metadata (actions only)">
              <ul className="divide-y divide-gray-100 text-sm">
                {summary.recent_activity.map((activity, index) => (
                  <li key={index} className="flex items-center justify-between gap-3 py-2">
                    <span className="font-mono text-xs text-gray-700">{activity.action}</span>
                    <span className="text-xs text-gray-400">{new Date(activity.created_at).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            </SectionCard>
          )}

          {!offline && summary.recent_documents.length === 0 && summary.recent_activity.length === 0 && (
            <StateBlock
              variant="empty"
              title="No recent activity"
              description="Upload and process documents to populate documents, records, validation and intelligence views."
            />
          )}

          {summary.limitations.length > 0 && (
            <section aria-label="Limitations">
              <div className="card p-4">
                <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-gray-500">Known limitations</h3>
                <ul className="list-disc pl-5 text-xs text-gray-500">
                  {summary.limitations.map((limitation) => (
                    <li key={limitation}>{limitation}</li>
                  ))}
                </ul>
              </div>
            </section>
          )}
        </div>
      )}
    </>
  );
}

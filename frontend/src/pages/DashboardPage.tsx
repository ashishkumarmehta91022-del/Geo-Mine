import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { MetricCard, Panel, SectionHeader } from "@/components/ui/Cards";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Icon, type IconName } from "@/components/ui/Icon";
import { fetchDashboardSummary } from "@/lib/dashboardApi";
import type { DashboardStatus, DashboardSummary } from "@/types/dashboard";

/** Honest status tone — an unavailable dependency must never look healthy. */
function statusToneClass(status: string): string {
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

function statusGlyph(status: string): string {
  switch (status) {
    case "OPERATIONAL":
    case "CONNECTED":
      return "✓";
    case "DEGRADED":
      return "⚠";
    case "NOT CONFIGURED":
      return "—";
    default:
      return "✕";
  }
}

function StatusTile({ status }: { status: DashboardStatus }) {
  const notConfigured = status.status === "NOT CONFIGURED";
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          {status.component}
        </p>
        <span
          className={`rounded border px-2 py-0.5 text-[10px] font-bold ${statusToneClass(status.status)}`}
          aria-label={`${status.component}: ${status.status}`}
        >
          {statusGlyph(status.status)} {status.status}
        </span>
      </div>
      {status.detail && (
        <p className={`mt-1.5 text-[11px] leading-snug ${notConfigured ? "text-gray-500" : "text-gray-500"}`}>
          {status.detail}
        </p>
      )}
    </div>
  );
}

/* --- B. Data pipeline visual -------------------------------------------- */

interface PipelineStage {
  label: string;
  icon: IconName;
  value: string | null;
  hint: string;
  to: string;
}

function PipelineStep({ stage, isLast }: { stage: PipelineStage; isLast: boolean }) {
  return (
    <li className="flex flex-1 items-center gap-2 min-w-0">
      <Link
        to={stage.to}
        className="group flex min-w-0 flex-1 items-center gap-2.5 rounded-md border border-gray-200 bg-surface px-3 py-2.5 transition-colors hover:border-brand-300 hover:bg-brand-50/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-navy-50 text-navy-700">
          <Icon name={stage.icon} className="h-4 w-4" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-xs font-semibold text-gray-800">{stage.label}</span>
          <span className="block truncate text-[11px] text-gray-500">
            {stage.value ?? "—"} · {stage.hint}
          </span>
        </span>
      </Link>
      {!isLast && (
        <span className="shrink-0 text-gray-300" aria-hidden="true">
          <Icon name="chevron-right" className="h-4 w-4" />
        </span>
      )}
    </li>
  );
}

function DataPipeline({ s }: { s: DashboardSummary }) {
  const d = s.documents;
  const r = s.records;
  const v = s.validation;
  const k = s.knowledge;
  const stages: PipelineStage[] = [
    { label: "Documents", icon: "documents", value: d ? String(d.total) : null, hint: "ingested", to: "/documents" },
    { label: "Extraction", icon: "layers", value: d ? `${d.processed}/${d.total}` : null, hint: "pages + OCR", to: "/documents" },
    { label: "Structuring", icon: "data", value: r ? String(r.total) : null, hint: "records", to: "/data-explorer" },
    { label: "Validation", icon: "validation", value: v ? `${v.errors + v.warnings + v.review_required} flags` : null, hint: "rule engine", to: "/validation" },
    { label: "Knowledge Index", icon: "search", value: k ? String(k.total_units) : null, hint: `${k ? Math.round(k.embedding_coverage * 100) : 0}% embedded`, to: "/knowledge" },
    { label: "AI Intelligence", icon: "ai", value: k && k.total_units > 0 ? "ready" : null, hint: "evidence-grounded", to: "/ai-query" },
  ];
  return (
    <Panel title="Data pipeline" subtitle="Unstructured documents → verified, traceable intelligence">
      <ol className="flex flex-col gap-1.5 md:flex-row md:items-center md:gap-0" aria-label="Data pipeline stages">
        {stages.map((stage, i) => (
          <PipelineStep key={stage.label} stage={stage} isLast={i === stages.length - 1} />
        ))}
      </ol>
    </Panel>
  );
}

/* --- Recent documents table ---------------------------------------------- */

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

/* -------------------------------------------------------------------------- */

/**
 * Production Dashboard: read-only operational entry point over the
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
        title="Geological & Mining Intelligence Dashboard"
        description="Verified, traceable intelligence from geological, mining and production documents."
        actions={
          <button type="button" className="btn-secondary" onClick={load}>
            <Icon name="refresh" className="h-4 w-4" /> Refresh
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
          {/* Offline banner: distinguish "cannot query" from "0 records". */}
          {offline && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-4" role="alert">
              <p className="text-sm font-semibold text-amber-800">Database unavailable — no live data</p>
              <p className="mt-1 text-xs text-amber-700">{summary.message}</p>
              <p className="mt-1 text-xs text-amber-600">
                Metric sections below are intentionally blank; no demo values are shown.
              </p>
            </div>
          )}

          {/* A. System health strip */}
          <section aria-label="System health">
            <SectionHeader title="System health" />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <StatusTile status={summary.api} />
              <StatusTile status={summary.database} />
              <StatusTile status={summary.retrieval} />
              <StatusTile status={summary.embeddings} />
              <StatusTile status={summary.llm} />
            </div>
          </section>

          {/* KPI cards */}
          {!offline && summary.documents && summary.records && summary.validation && summary.knowledge && (
            <section aria-label="Key operational metrics">
              <SectionHeader title="Key metrics" />
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                <MetricCard label="Documents" icon="documents" value={summary.documents.total}
                  hint={`${summary.documents.processed} processed · ${summary.documents.failed} failed`} to="/documents" />
                <MetricCard label="Extracted Records" icon="data" value={summary.records.total}
                  hint={`${summary.records.validated} validated`} to="/data-explorer" />
                <MetricCard label="Indexed Units" icon="layers" value={summary.knowledge.total_units}
                  hint={`${summary.knowledge.pages} pages · ${summary.knowledge.records} records`} to="/knowledge" />
                <MetricCard label="Validation Issues" icon="warn"
                  tone={summary.validation.errors > 0 ? "bad" : summary.validation.warnings > 0 ? "warn" : "ok"}
                  value={summary.validation.errors + summary.validation.warnings}
                  hint={`${summary.validation.errors} errors · ${summary.validation.warnings} warnings`} to="/validation" />
                <MetricCard label="Embedding Coverage" icon="chip"
                  tone={summary.knowledge.embedding_coverage >= 0.99 ? "ok" : summary.knowledge.embedding_coverage > 0 ? "warn" : "neutral"}
                  value={`${Math.round(summary.knowledge.embedding_coverage * 100)}%`}
                  hint={`${summary.knowledge.embedded_units}/${summary.knowledge.total_units} units embedded`} to="/knowledge" />
              </div>
            </section>
          )}

          {/* B. Data pipeline */}
          {!offline && <DataPipeline s={summary} />}

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            {/* C. Recent documents */}
            {!offline && (
              <Panel
                title="Recent documents"
                actions={<Link to="/documents" className="text-xs font-semibold text-brand-600 hover:underline">All documents →</Link>}
              >
                {summary.recent_documents.length === 0 ? (
                  <p className="py-6 text-center text-sm text-gray-500">
                    No documents yet. Upload one from the Documents page to begin.
                  </p>
                ) : (
                  <div className="-mx-5 overflow-x-auto px-5">
                    <table className="table-base min-w-[440px]">
                      <thead>
                        <tr>
                          <th scope="col">Document</th>
                          <th scope="col">Type</th>
                          <th scope="col">Status</th>
                          <th scope="col" className="text-right">Records</th>
                          <th scope="col">Uploaded</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.recent_documents.map((doc) => (
                          <tr key={doc.document_id}>
                            <td className="max-w-[220px]">
                              <Link to="/documents" className="block truncate font-medium text-brand-700 hover:underline" title={doc.filename}>
                                {doc.filename}
                              </Link>
                              {doc.requires_review && (
                                <span className="mt-0.5 inline-block"><Badge tone="review">review</Badge></span>
                              )}
                            </td>
                            <td className="uppercase text-gray-500">{doc.document_type}</td>
                            <td><StatusBadge status={doc.status} /></td>
                            <td className="text-right tabular-nums">{doc.record_count}</td>
                            <td className="whitespace-nowrap text-gray-500">{timeAgo(doc.uploaded_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            )}

            {/* D. Validation / review summary */}
            {!offline && summary.validation && (
              <Panel
                title="Validation & review"
                subtitle="Conflicted values stay marked review-required — the system never picks a winner"
                actions={<Link to="/review-queue" className="text-xs font-semibold text-brand-600 hover:underline">Review queue →</Link>}
              >
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3">
                    <p className="text-xs font-semibold uppercase text-emerald-700">Passed</p>
                    <p className="mt-1 text-xl font-bold text-emerald-800">{summary.validation.by_status["pass"] ?? 0}</p>
                  </div>
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
                    <p className="text-xs font-semibold uppercase text-amber-700">Warnings</p>
                    <p className="mt-1 text-xl font-bold text-amber-800">{summary.validation.warnings}</p>
                  </div>
                  <div className="rounded-md border border-red-200 bg-red-50 p-3">
                    <p className="text-xs font-semibold uppercase text-red-700">Errors</p>
                    <p className="mt-1 text-xl font-bold text-red-800">{summary.validation.errors}</p>
                  </div>
                  <div className="rounded-md border border-violet-200 bg-violet-50 p-3">
                    <p className="text-xs font-semibold uppercase text-violet-700">Review required</p>
                    <p className="mt-1 text-xl font-bold text-violet-800">{summary.validation.review_required}</p>
                  </div>
                </div>
                {summary.intelligence?.top_terms?.length ? (
                  <p className="mt-3 text-xs text-gray-500">
                    Top corpus terms:{" "}
                    {summary.intelligence.top_terms.slice(0, 5).map((t) => t.term).join(" · ")}
                  </p>
                ) : null}
              </Panel>
            )}
          </div>

          {/* E. Quick actions + F. Trust panel */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Panel title="Quick actions">
              <div className="flex flex-wrap gap-2">
                <Link to="/documents" className="btn-primary"><Icon name="upload" className="h-4 w-4" /> Upload Document</Link>
                <Link to="/data-explorer" className="btn-secondary"><Icon name="data" className="h-4 w-4" /> Explore Data</Link>
                <Link to="/knowledge" className="btn-secondary"><Icon name="search" className="h-4 w-4" /> Search Knowledge</Link>
                <Link to="/report-generator" className="btn-secondary"><Icon name="report" className="h-4 w-4" /> Generate Report</Link>
                <Link to="/ai-query" className="btn-secondary"><Icon name="ai" className="h-4 w-4" /> Ask AI</Link>
              </div>
            </Panel>

            <Panel title="Evidence-first intelligence" subtitle="Every value keeps its provenance end-to-end">
              <ol className="space-y-2 text-sm">
                {[
                  { label: "Source Document", desc: "Original file stored verbatim; pages referenced, never replaced", icon: "documents" as IconName },
                  { label: "Extracted Value", desc: "Verbatim value_raw preserved alongside the normalized value", icon: "data" as IconName },
                  { label: "Validation", desc: "Deterministic rule engine; conflicts raise review, never auto-resolution", icon: "validation" as IconName },
                  { label: "Evidence", desc: "Search/AI answers cite document, page, record and validation IDs", icon: "link" as IconName },
                  { label: "Report / Answer", desc: "DOCX reports and answers are built from validated records only", icon: "report" as IconName },
                ].map((step, i, all) => (
                  <li key={step.label} className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-navy-50 text-navy-700">
                      <Icon name={step.icon} className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0">
                      <p className="font-medium text-gray-800">
                        {step.label}
                        {i < all.length - 1 && <span className="ml-2 text-gray-300" aria-hidden="true">→</span>}
                      </p>
                      <p className="text-xs text-gray-500">{step.desc}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}

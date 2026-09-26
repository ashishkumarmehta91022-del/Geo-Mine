import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import {
  fetchDocumentValidation,
  fetchReviewQueue,
  updateReviewStatus,
} from "@/lib/validationApi";
import type {
  ValidationDocumentResponse,
  ValidationItem,
} from "@/types/validation";

function statusClasses(status: string): string {
  switch (status) {
    case "pass":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "warning":
      return "bg-amber-50 text-amber-700 border-amber-200";
    case "error":
      return "bg-red-50 text-red-700 border-red-200";
    case "review_required":
      return "bg-purple-50 text-purple-700 border-purple-200";
    default:
      return "bg-gray-100 text-gray-600 border-gray-200";
  }
}

function severityBadge(severity: string): string {
  switch (severity) {
    case "critical":
      return "bg-red-100 text-red-800";
    case "error":
      return "bg-red-50 text-red-700";
    case "warning":
      return "bg-amber-50 text-amber-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

function reviewBadge(status: string): string {
  switch (status) {
    case "open":
      return "bg-blue-50 text-blue-700";
    case "in_review":
      return "bg-amber-50 text-amber-700";
    case "resolved":
      return "bg-emerald-50 text-emerald-700";
    case "rejected":
      return "bg-gray-100 text-gray-500";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

function StatCard({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${accent}`}>{value}</p>
    </div>
  );
}

function ConflictSummary({ details }: { details: Record<string, unknown> | null }) {
  const values = (details?.values as Array<Record<string, unknown>>) ?? [];
  if (values.length < 2) return null;
  const [a, b] = values;
  return (
    <div className="mt-2 grid grid-cols-1 gap-2 rounded-md border border-purple-200 bg-purple-50 p-3 sm:grid-cols-2">
      {[a, b].map((side, i) => (
        <div key={i} className="text-xs">
          <p className="font-semibold text-gray-700">
            Source {i === 0 ? "A" : "B"} · doc #{String(side.document_id)}
            {side.document_filename ? ` · ${String(side.document_filename)}` : ""}
          </p>
          <p className="mt-1 text-lg font-bold text-gray-900">{String(side.value)}</p>
          <p className="text-gray-500">{String(side.source_reference ?? "")}</p>
        </div>
      ))}
      <p className="text-[11px] text-purple-700 sm:col-span-2">
        Conflict detected — both values preserved, no automatic winner selected.
      </p>
    </div>
  );
}

function ResultRow({
  item,
  onReview,
  showDocument = true,
}: {
  item: ValidationItem;
  onReview?: (item: ValidationItem, decision: string) => void;
  showDocument?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const isConflict = item.rule_code === "CROSS_DOCUMENT_CONFLICT";

  const decide = async (decision: string) => {
    setBusy(true);
    try {
      await onReview?.(item, decision);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-5 py-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${statusClasses(item.status)}`}>
          {item.status.replace("_", " ")}
        </span>
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${severityBadge(item.severity)}`}>
          {item.severity}
        </span>
        <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] text-gray-600">
          {item.rule_code}
        </span>
        {showDocument && item.document_filename && (
          <span className="truncate text-xs text-gray-500">{item.document_filename}</span>
        )}
        {typeof item.confidence === "number" && (
          <span className="text-[10px] text-gray-400">
            confidence {(item.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      <p className="mt-1.5 text-sm text-gray-800">{item.message}</p>

      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-500">
        {item.source_reference && <span>source: {item.source_reference}</span>}
        {item.original_value !== null && (
          <span>
            value: <span className="font-mono text-gray-700">{item.original_value}</span>
          </span>
        )}
        {item.expected_value && <span>expected: {item.expected_value}</span>}
      </div>

      {isConflict && <ConflictSummary details={item.details} />}

      {onReview && item.review_status === "open" && (
        <div className="mt-2.5 flex items-center gap-2">
          <button
            type="button"
            className="btn-primary !px-2.5 !py-1 text-xs"
            disabled={busy}
            onClick={() => decide("resolved")}
          >
            Mark resolved
          </button>
          <button
            type="button"
            className="btn-secondary !px-2.5 !py-1 text-xs"
            disabled={busy}
            onClick={() => decide("in_review")}
          >
            Start review
          </button>
          <button
            type="button"
            className="btn-secondary !px-2.5 !py-1 text-xs !text-red-600 hover:!bg-red-50"
            disabled={busy}
            onClick={() => decide("rejected")}
          >
            Reject
          </button>
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${reviewBadge(item.review_status)}`}>
            {item.review_status.replace("_", " ")}
          </span>
        </div>
      )}
      {onReview && item.review_status !== "open" && (
        <span className={`mt-2 inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold ${reviewBadge(item.review_status)}`}>
          {item.review_status.replace("_", " ")}
        </span>
      )}
    </div>
  );
}

/** Validation & Data Quality page (Step 6). */
export default function ValidationPage() {
  const [documentIdInput, setDocumentIdInput] = useState("");
  const [summary, setSummary] = useState<ValidationDocumentResponse | null>(null);
  const [isSummaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [queue, setQueue] = useState<ValidationItem[] | null>(null);
  const [queueTotal, setQueueTotal] = useState(0);
  const [isQueueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError(null);
    try {
      const data = await fetchReviewQueue(1, "open");
      setQueue(data.items);
      setQueueTotal(data.total);
    } catch (cause: unknown) {
      setQueueError(cause instanceof Error ? cause.message : "Could not load the review queue.");
    } finally {
      setQueueLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const loadDocument = useCallback(async (id: number) => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      setSummary(await fetchDocumentValidation(id));
    } catch (cause: unknown) {
      setSummary(null);
      setSummaryError(cause instanceof Error ? cause.message : "Could not load validation results.");
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const handleReview = useCallback(
    async (item: ValidationItem, decision: string) => {
      await updateReviewStatus(item.id, decision);
      await loadQueue();
      if (summary && item.document_id === summary.document_id) {
        await loadDocument(summary.document_id);
      }
    },
    [loadQueue, loadDocument, summary],
  );

  return (
    <>
      <PageHeader
        title="Validation"
        description="Deterministic data-quality checks over extracted and OCR data"
      />

      {/* Document lookup */}
      <section aria-label="Validate a document" className="mb-8">
        <div className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="doc-id" className="mb-1 block text-xs font-semibold text-gray-600">
              Document ID
            </label>
            <input
              id="doc-id"
              type="number"
              min={1}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
              placeholder="e.g. 1"
              value={documentIdInput}
              onChange={(e) => setDocumentIdInput(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn-primary"
            disabled={!documentIdInput}
            onClick={() => loadDocument(Number(documentIdInput))}
          >
            Load results
          </button>
        </div>
        {isSummaryLoading && <div className="mt-3"><StateBlock variant="loading" title="Loading results…" /></div>}
        {summaryError && (
          <div className="mt-3">
            <StateBlock variant="error" title="Cannot load validation results" description={summaryError} />
          </div>
        )}
        {summary && (
          <div className="mt-4 space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <StatCard label="Total checks" value={summary.summary.total_checks} accent="text-gray-900" />
              <StatCard label="Passed" value={summary.summary.passed} accent="text-emerald-700" />
              <StatCard label="Warnings" value={summary.summary.warnings} accent="text-amber-600" />
              <StatCard label="Errors" value={summary.summary.errors} accent="text-red-600" />
              <StatCard label="Review required" value={summary.summary.review_required} accent="text-purple-700" />
            </div>

            <div className="card divide-y divide-gray-100">
              {summary.items.length === 0 && (
                <p className="px-5 py-6 text-center text-sm text-gray-500">
                  No validation results stored for this document — run validation first.
                </p>
              )}
              {summary.items.map((item) => (
                <ResultRow key={item.id} item={item} showDocument={false} />
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Review queue */}
      <section aria-label="Human review queue">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Review queue {queueTotal > 0 && <span className="text-gray-400">({queueTotal} open)</span>}
          </h3>
          <button type="button" className="btn-secondary !px-3 !py-1.5 text-xs" onClick={loadQueue}>
            Refresh
          </button>
        </div>

        {isQueueLoading && <StateBlock variant="loading" title="Loading review queue…" />}
        {queueError && (
          <StateBlock
            variant="error"
            title="Cannot load the review queue"
            description={queueError}
            action={
              <button type="button" className="btn-primary" onClick={loadQueue}>
                Retry
              </button>
            }
          />
        )}
        {!isQueueLoading && !queueError && queue && queue.length === 0 && (
          <StateBlock
            variant="empty"
            title="Review queue is empty"
            description="Validation items flagged for human review (low-confidence OCR, conflicts, data-quality warnings) will appear here."
          />
        )}
        {!isQueueLoading && !queueError && queue && queue.length > 0 && (
          <div className="card divide-y divide-gray-100">
            {queue.map((item) => (
              <ResultRow key={item.id} item={item} onReview={handleReview} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}

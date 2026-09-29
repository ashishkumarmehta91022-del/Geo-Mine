import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/Toast";
import { fetchReviewQueue, updateReviewStatus } from "@/lib/validationApi";
import type { ReviewQueueResponse, ValidationItem } from "@/types/validation";

const QUEUE_TABS = [
  { key: "open", label: "Open" },
  { key: "in_review", label: "In Review" },
  { key: "resolved", label: "Resolved" },
  { key: "rejected", label: "Rejected" },
] as const;

type TabKey = (typeof QUEUE_TABS)[number]["key"];

/** Human-readable presentation of a validation item's issue. */
function issueSummary(item: ValidationItem): { title: string; detail: string } {
  const value = item.original_value ? `"${item.original_value}"` : "value";
  const rule = item.rule_code.split("_").join(" ").toLowerCase();
  if (item.rule_code.startsWith("CROSS_DOCUMENT")) {
    return {
      title: "Conflicting values across sources",
      detail: item.message ?? "Two sources disagree for the same metric/period.",
    };
  }
  switch (item.rule_code) {
    case "OCR_LOW_CONFIDENCE":
      return {
        title: "Low-confidence OCR extraction",
        detail: `${value} read at ${item.confidence != null ? `${Math.round(item.confidence * 100)}%` : "low"} confidence — verify against the source page.`,
      };
    case "OCR_REVIEW_FLAGGED":
      return { title: "OCR flagged for review", detail: item.message ?? "The OCR engine requested human verification." };
    case "REQUIRED_FIELD_MISSING":
      return { title: "Required field missing", detail: item.message ?? "A required field is absent for this record." };
    default:
      return { title: rule, detail: item.message ?? `${rule} flagged ${value} for review.` };
  }
}

/** Review Queue — the human-in-the-loop workflow over real validation items. */
export default function ReviewQueuePage() {
  const [tab, setTab] = useState<TabKey>("open");
  const [data, setData] = useState<ReviewQueueResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notesFor, setNotesFor] = useState<number | null>(null);
  const [notesText, setNotesText] = useState("");
  const { success, error: toastError } = useToast();

  const load = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setError(null);
    try {
      setData(await fetchReviewQueue(1, tab));
    } catch (cause: unknown) {
      setIsError(true);
      setError(cause instanceof Error ? cause.message : "Could not load the review queue.");
    } finally {
      setIsLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  const transition = useCallback(
    async (item: ValidationItem, nextStatus: "in_review" | "resolved" | "rejected", notes?: string) => {
      setBusyId(item.id);
      try {
        await updateReviewStatus(item.id, nextStatus, notes ?? item.review_notes ?? undefined);
        success(
          nextStatus === "in_review"
            ? `Review #${item.id} started.`
            : nextStatus === "resolved"
              ? `Review #${item.id} resolved.`
              : `Review #${item.id} rejected.`,
        );
        setNotesFor(null);
        setNotesText("");
        await load();
      } catch (cause: unknown) {
        toastError(cause instanceof Error ? cause.message : "Could not update the review item.");
      } finally {
        setBusyId(null);
      }
    },
    [load, success, toastError],
  );

  return (
    <>
      <PageHeader
        title="Review Queue"
        description="Conflicts and low-confidence values wait here for a human decision. The system never auto-resolves."
      />

      {/* Workflow state tabs */}
      <div className="mb-4 flex flex-wrap gap-1" role="tablist" aria-label="Review workflow state">
        {QUEUE_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
              tab === t.key ? "bg-navy-800 text-white" : "bg-surface text-gray-600 hover:bg-gray-100 border border-gray-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading && <StateBlock variant="loading" title="Loading review items…" />}
      {isError && (
        <StateBlock
          variant="error"
          title="Could not load the review queue"
          description={error ?? undefined}
          action={<button type="button" className="btn-primary" onClick={load}>Retry</button>}
        />
      )}

      {!isLoading && !isError && data && (
        data.items.length === 0 ? (
          <StateBlock
            variant="empty"
            title={tab === "open" ? "No items awaiting review" : `No ${t_label(tab)} items`}
            description={
              tab === "open"
                ? "The queue is clear. Items appear here when validation flags a conflict, a low-confidence OCR value, or a missing required field."
                : "Items with this review state will appear here."
            }
          />
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-gray-500" aria-live="polite">
              {data.total} item{data.total === 1 ? "" : "s"} in this state
            </p>
            {data.items.map((item) => (
              <ReviewCard
                key={item.id}
                item={item}
                busy={busyId === item.id}
                notesOpen={notesFor === item.id}
                notesText={notesText}
                onNotesChange={setNotesText}
                onToggleNotes={() => {
                  setNotesFor(notesFor === item.id ? null : item.id);
                  setNotesText(item.review_notes ?? "");
                }}
                onStart={() => transition(item, "in_review")}
                onResolve={() => transition(item, "resolved", notesFor === item.id ? notesText : undefined)}
                onReject={() => transition(item, "rejected", notesFor === item.id ? notesText : undefined)}
              />
            ))}
          </div>
        )
      )}
    </>
  );
}

function t_label(tab: TabKey): string {
  return QUEUE_TABS.find((t) => t.key === tab)?.label.toLowerCase() ?? tab;
}

function ReviewCard({
  item,
  busy,
  notesOpen,
  notesText,
  onNotesChange,
  onToggleNotes,
  onStart,
  onResolve,
  onReject,
}: {
  item: ValidationItem;
  busy: boolean;
  notesOpen: boolean;
  notesText: string;
  onNotesChange: (v: string) => void;
  onToggleNotes: () => void;
  onStart: () => void;
  onResolve: () => void;
  onReject: () => void;
}) {
  const issue = issueSummary(item);
  const conflict = item.rule_code.startsWith("CROSS_DOCUMENT");
  const values = (item.details?.values as Array<{ value?: string; source_reference?: string; document_filename?: string }> | undefined) ?? [];

  return (
    <article className={`card p-4 ${conflict ? "border-amber-300" : ""}`} aria-label={`Review item ${item.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wide text-gray-400">Review #{item.id}</span>
            <StatusBadge status={item.review_status} />
            <Badge tone={conflict ? "warn" : item.severity === "error" ? "bad" : "warn"}>
              {item.rule_code.split("_").join(" ")}
            </Badge>
            {conflict && <Badge tone="review">conflict — human review required</Badge>}
          </div>
          <h3 className="mt-1.5 text-sm font-semibold text-gray-900">{issue.title}</h3>
          <p className="mt-0.5 text-sm text-gray-600">{issue.detail}</p>
          <p className="mt-1 text-xs text-gray-500">
            <Link to="/documents" className="text-brand-600 hover:underline">{item.document_filename ?? `Document #${item.document_id}`}</Link>
            {item.source_reference && <> · source: <span className="font-medium">{item.source_reference}</span></>}
            · {new Date(item.created_at).toLocaleString()}
          </p>
        </div>

        {/* Workflow actions */}
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {item.review_status === "open" && (
            <button type="button" className="btn-primary !py-1.5" disabled={busy} onClick={onStart}>
              Start Review
            </button>
          )}
          {(item.review_status === "open" || item.review_status === "in_review") && (
            <>
              <button type="button" className="btn-secondary !py-1.5" disabled={busy} onClick={onResolve}>
                Resolve
              </button>
              <button type="button" className="btn-danger !py-1.5" disabled={busy} onClick={onReject}>
                Reject
              </button>
            </>
          )}
          <button type="button" className="btn-ghost !py-1.5" onClick={onToggleNotes} aria-expanded={notesOpen}>
            {notesOpen ? "Hide notes" : "Notes"}
          </button>
        </div>
      </div>

      {/* Conflict values — both sources shown, no winner picked */}
      {conflict && values.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {values.map((v, i) => (
            <div key={i} className="rounded-md border border-amber-200 bg-amber-50/60 px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">
                Source {String.fromCharCode(65 + i)}
              </p>
              <p className="text-base font-bold text-gray-900">{v.value ?? "—"}</p>
              <p className="text-xs text-gray-500">
                {v.document_filename ?? v.source_reference ?? "unknown source"}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Notes editor */}
      {notesOpen && (
        <div className="mt-3">
          <label htmlFor={`notes-${item.id}`} className="mb-1 block text-xs font-semibold text-gray-600">
            Review notes
          </label>
          <textarea
            id={`notes-${item.id}`}
            className="input-base min-h-[64px]"
            placeholder="Record the decision rationale (optional)…"
            value={notesText}
            onChange={(e) => onNotesChange(e.target.value)}
          />
        </div>
      )}

      {/* Prior decision trail */}
      {item.review_notes && !notesOpen && (
        <p className="mt-2 text-xs text-gray-500">
          <span className="font-semibold">Notes:</span> {item.review_notes}
          {item.reviewed_at && <> · {new Date(item.reviewed_at).toLocaleString()}</>}
        </p>
      )}
    </article>
  );
}

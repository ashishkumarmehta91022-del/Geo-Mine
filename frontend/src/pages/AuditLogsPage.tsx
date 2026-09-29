import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { Badge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { fetchAuditLogs } from "@/lib/auditApi";
import type { AuditLogItem, AuditLogListResponse } from "@/types/audit";

/** Human labels for known audit actions (unknown actions render as-is). */
function actionLabel(action: string): string {
  const known: Record<string, string> = {
    "document.uploaded": "Document uploaded",
    "document.processed": "Document processed",
    "document.deleted": "Document deleted",
    "record.extracted": "Record extracted",
    "validation.run": "Validation run",
    "ai.query": "AI query",
    "report.generate": "Report generated",
    "report.analyze": "Analytics run",
    "intelligence.analyze": "Topic intelligence",
    "dashboard.summary": "Dashboard viewed",
    "dashboard.statuses": "Status check",
  };
  return known[action] ?? action.split(".").join(" · ");
}

function actionTone(action: string): "ok" | "info" | "warn" | "neutral" {
  if (action.startsWith("document.")) return "info";
  if (action.startsWith("report.") || action.startsWith("intelligence.")) return "ok";
  if (action.includes("delete") || action.includes("error")) return "warn";
  return "neutral";
}

/** Compact details renderer — metadata only; strings/lists render inline. */
function DetailsList({ details }: { details: Record<string, unknown> }) {
  const entries = Object.entries(details).slice(0, 12);
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
      {entries.map(([key, value]) => (
        <div key={key} className="col-span-2 grid grid-cols-subgrid">
          <dt className="font-semibold text-gray-500">{key.split("_").join(" ")}</dt>
          <dd className="break-all text-gray-700">
            {typeof value === "object" && value !== null ? JSON.stringify(value) : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function AuditRow({ item }: { item: AuditLogItem }) {
  const [open, setOpen] = useState(false);
  const hasDetails = item.details !== null && Object.keys(item.details).length > 0;
  return (
    <>
      <tr className="cursor-pointer" onClick={() => hasDetails && setOpen((o) => !o)}>
        <td className="whitespace-nowrap tabular-nums text-gray-500">
          {new Date(item.created_at).toLocaleString()}
        </td>
        <td>
          <Badge tone={actionTone(item.action)}>{actionLabel(item.action)}</Badge>
        </td>
        <td className="text-gray-600">{item.entity_type ?? "—"}</td>
        <td className="tabular-nums text-gray-600">{item.entity_id ?? "—"}</td>
        <td className="text-gray-500">system</td>
        <td className="text-right text-gray-400">
          {hasDetails && (
            <Icon name={open ? "chevron-down" : "chevron-right"} className="ml-auto h-4 w-4" />
          )}
        </td>
      </tr>
      {open && hasDetails && (
        <tr>
          <td colSpan={6} className="bg-slate-50 px-4 py-3">
            <DetailsList details={item.details as Record<string, unknown>} />
          </td>
        </tr>
      )}
    </>
  );
}

/** Audit Logs — metadata-only traceability trail (real entries, expandable). */
export default function AuditLogsPage() {
  const [data, setData] = useState<AuditLogListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    try {
      setData(await fetchAuditLogs(page, 25, actionFilter || undefined));
    } catch {
      setIsError(true);
    } finally {
      setIsLoading(false);
    }
  }, [page, actionFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <>
      <PageHeader
        title="Audit Logs"
        description="Metadata-only audit trail — what happened, when, on which entity. Sensitive content is never recorded."
        actions={
          <div className="flex items-center gap-2">
            <label htmlFor="audit-action" className="sr-only">Filter by action</label>
            <select
              id="audit-action"
              className="input-base !w-56"
              value={actionFilter}
              onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
            >
              <option value="">All actions</option>
              <option value="document.uploaded">Document uploaded</option>
              <option value="ai.query">AI query</option>
              <option value="report.generate">Report generated</option>
              <option value="report.analyze">Analytics run</option>
              <option value="dashboard.summary">Dashboard viewed</option>
            </select>
            <button type="button" className="btn-secondary" onClick={load}>
              <Icon name="refresh" className="h-4 w-4" /> Refresh
            </button>
          </div>
        }
      />

      {isLoading && <StateBlock variant="loading" title="Loading audit trail…" />}
      {isError && (
        <StateBlock
          variant="error"
          title="Could not load the audit trail"
          description="The database may be unavailable. The trail will appear once the connection is restored."
          action={<button type="button" className="btn-primary" onClick={load}>Retry</button>}
        />
      )}

      {!isLoading && !isError && data && (
        <div className="card overflow-hidden">
          {data.items.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <p className="text-sm font-medium text-gray-700">No audit entries found</p>
              <p className="mt-1 text-xs text-gray-500">
                Actions are recorded as the platform is used. {actionFilter ? "Try clearing the filter." : ""}
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="table-base min-w-[760px]">
                  <thead>
                    <tr>
                      <th scope="col">Timestamp</th>
                      <th scope="col">Action</th>
                      <th scope="col">Entity</th>
                      <th scope="col">Entity ID</th>
                      <th scope="col">Actor</th>
                      <th scope="col"><span className="sr-only">Details</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((item) => <AuditRow key={item.id} item={item} />)}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between border-t border-gray-100 px-4 py-2.5 text-xs text-gray-500">
                <span>
                  {data.total} entries · page {data.page} of {totalPages}
                </span>
                <div className="flex gap-2">
                  <button type="button" className="btn-secondary !px-2.5 !py-1" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </button>
                  <button type="button" className="btn-secondary !px-2.5 !py-1" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}

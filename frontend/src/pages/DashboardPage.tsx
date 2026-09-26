import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { useHealth } from "@/hooks/useHealth";
import { NAV_ITEMS } from "@/components/layout/navigation";

function StatusCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "ok" | "bad" | "neutral";
}) {
  const toneClasses =
    tone === "ok"
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : tone === "bad"
        ? "text-red-700 bg-red-50 border-red-200"
        : "text-gray-700 bg-gray-50 border-gray-200";
  return (
    <div className="card p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
      <span className={`mt-3 inline-block rounded border px-2.5 py-1 text-sm font-semibold ${toneClasses}`}>
        {value}
      </span>
    </div>
  );
}

/** Dashboard: the only page with live data in Step 1 (backend health). */
export default function DashboardPage() {
  const { health, isLoading, isError, error, refetch } = useHealth();

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Platform overview and system status"
        actions={
          <button type="button" className="btn-secondary" onClick={() => refetch()}>
            Refresh status
          </button>
        }
      />

      {isLoading && (
        <StateBlock variant="loading" title="Checking platform services…" />
      )}

      {!isLoading && isError && (
        <StateBlock
          variant="error"
          title="Cannot reach the backend API"
          description={error ?? undefined}
          action={
            <button type="button" className="btn-primary" onClick={() => refetch()}>
              Retry
            </button>
          }
        />
      )}

      {!isLoading && !isError && health && (
        <div className="space-y-6">
          <section aria-label="System status">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
              System status
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <StatusCard
                label="API service"
                value={health.status === "ok" ? "Operational" : `Status: ${health.status}`}
                tone={health.status === "ok" ? "ok" : "bad"}
              />
              <StatusCard
                label="Database"
                value={health.database.connected ? "Connected" : `Offline (${health.database.detail})`}
                tone={health.database.connected ? "ok" : "neutral"}
              />
              <StatusCard label="Service" value={health.service} tone="neutral" />
            </div>
          </section>

          <section aria-label="Modules">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Platform modules
            </h3>
            <StateBlock
              variant="empty"
              title="No module data yet"
              description="Documents, AI Query, Report Generator and other modules will surface their data here once implemented in later steps."
            />
          </section>

          <section aria-label="Planned modules">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Roadmap
            </h3>
            <div className="card divide-y divide-gray-100">
              {NAV_ITEMS.map((item) => (
                <div key={item.path} className="flex items-center justify-between gap-4 px-5 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">{item.label}</p>
                    <p className="truncate text-xs text-gray-500">{item.description}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                    {item.path === "/dashboard"
                      ? "Live (Step 1)"
                      : item.path === "/documents"
                        ? "Live (Steps 3–5)"
                        : item.path === "/validation"
                          ? "Live (Step 6)"
                          : "Planned"}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </>
  );
}

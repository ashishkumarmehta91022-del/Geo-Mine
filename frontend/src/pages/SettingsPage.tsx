import { useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { Panel } from "@/components/ui/Cards";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { useHealth } from "@/hooks/useHealth";
import { useTheme } from "@/hooks/useTheme";
import { fetchDashboardStatuses } from "@/lib/dashboardApi";
import { fetchKnowledgeStats } from "@/lib/searchApi";
import type { DashboardStatuses } from "@/types/dashboard";
import type { KnowledgeStats } from "@/types/search";
import { MAX_UPLOAD_SIZE_MB, SUPPORTED_FILE_TYPES } from "@/types/document";

/** Read-only settings row. */
function Row({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 py-2.5 last:border-none">
      <div>
        <p className="text-sm font-medium text-gray-700">{label}</p>
        {hint && <p className="text-xs text-gray-400">{hint}</p>}
      </div>
      <div className="text-sm text-gray-600">{value}</div>
    </div>
  );
}

/**
 * Settings — read-only system reference. Shows operational status only;
 * credentials, connection strings and secrets are never displayed.
 */
export default function SettingsPage() {
  const { health, isError: healthError, refetch } = useHealth();
  const { theme, setTheme } = useTheme();
  const [statuses, setStatuses] = useState<DashboardStatuses | null>(null);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [statsUnavailable, setStatsUnavailable] = useState(false);
  const [documentsSummary, setDocumentsSummary] = useState<{ total: number; processed: number } | null>(null);

  useEffect(() => {
    fetchDashboardStatuses().then(setStatuses).catch(() => setStatuses(null));
    fetchKnowledgeStats()
      .then(setStats)
      .catch(() => setStatsUnavailable(true));
    // Real processing counters (dashboard aggregation over the same DB).
    import("@/lib/dashboardApi")
      .then(({ fetchDashboardSummary }) => fetchDashboardSummary())
      .then((s) =>
        setDocumentsSummary(
          s.documents ? { total: s.documents.total, processed: s.documents.processed } : null,
        ),
      )
      .catch(() => setDocumentsSummary(null));
  }, [refetch]);

  if (healthError) {
    return (
      <>
        <PageHeader title="Settings" description="Read-only system configuration and health reference." />
        <StateBlock
          variant="error"
          title="Cannot reach the backend API"
          description="System information is unavailable while the API is offline."
          action={<button type="button" className="btn-primary" onClick={refetch}>Retry</button>}
        />
      </>
    );
  }

  const dbConnected = health?.database.connected === true;

  return (
    <>
      <PageHeader
        title="System Settings"
        description="Read-only system configuration and health reference. Credentials are never displayed."
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Application" subtitle="Platform identity and runtime">
          <Row label="Application" value="CMPDI AI Reporting Platform" />
          <Row label="Problem statement" value="SIH26023 — SIH 2026" />
          <Row label="Environment" value="Development (local)" />
          <Row label="API status" value={<StatusBadge status={health ? "OPERATIONAL" : null} />} />
          <Row label="Data mode" value={<Badge tone="warn">Demo environment · synthetic data</Badge>} hint="Seeded dataset is synthetic — not official CMPDI/CIL figures" />
        </Panel>

        <Panel title="Database" subtitle="PostgreSQL source of truth">
          <Row
            label="Connection"
            value={<StatusBadge status={dbConnected ? "connected" : "UNAVAILABLE"} />}
            hint={health ? `Detail: ${health.database.detail}` : undefined}
          />
          <Row label="Host" value="localhost:5432" hint="Configured via environment; credentials are never shown" />
          <Row label="Schema migrations" value="Alembic chain 0001 → 0007" hint="Applied via alembic upgrade head" />
          <Row label="Provenance storage" value="documents · pages · records · validations · audit_logs" />
        </Panel>

        <Panel title="Retrieval" subtitle="Knowledge index and search modes">
          <Row label="Lexical search" value={<Badge tone={stats && stats.total_units > 0 ? "ok" : "neutral"}>Available</Badge>} hint="PostgreSQL full-text (tsvector)" />
          <Row label="Semantic search" value={<Badge tone={statuses?.embeddings.status === "OPERATIONAL" ? "ok" : "neutral"}>{statuses?.embeddings.status === "OPERATIONAL" ? "Available" : "Awaiting embeddings"}</Badge>} hint="Local FastEmbed model" />
          <Row label="Hybrid search" value={<Badge tone={statuses?.embeddings.status === "OPERATIONAL" ? "ok" : "neutral"}>{statuses?.embeddings.status === "OPERATIONAL" ? "Available" : "Lexical fallback"}</Badge>} hint="Reciprocal-rank fusion of both modes" />
          <Row
            label="Embedding model"
            value={stats?.embedding_models?.[0] ?? "—"}
            hint={stats ? `${stats.embedded_units}/${stats.total_units} units embedded` : "Index statistics unavailable"}
          />
        </Panel>

        <Panel title="AI / LLM" subtitle="Evidence-grounded answering (LLM optional)">
          <Row
            label="LLM status"
            value={<StatusBadge status={statuses?.llm.status ?? "NOT CONFIGURED"} />}
            hint="Not configured — AI Query still retrieves evidence and reports this honestly"
          />
          <Row
            label="Provider name"
            value={statuses?.llm.status === "OPERATIONAL" ? (statuses.llm.detail ?? "configured") : "—"}
            hint="Shown only when the backend reports a configured provider; keys are never exposed"
          />
          <Row label="Grounding" value="Retrieval-first" hint="Answers cite evidence IDs; no evidence → no answer" />
          <Row label="Prompt protection" value="Delimiters neutralized" hint="Untrusted document text is bounded and framed as data" />
        </Panel>

        <Panel title="Storage / Processing" subtitle="Document intake and extraction">
          <Row
            label="Supported formats"
            value={SUPPORTED_FILE_TYPES.split(",").join(" · ").toUpperCase()}
            hint="Signature-verified on upload"
          />
          <Row
            label="OCR availability"
            value={<Badge tone="ok">Available</Badge>}
            hint="Per-page dispatch renders scanned pages and runs local OCR"
          />
          <Row
            label="Documents processed"
            value={documentsSummary ? `${documentsSummary.processed} / ${documentsSummary.total}` : "—"}
            hint={documentsSummary ? "Lifecycle status from the live database" : "Processing statistics unavailable"}
          />
          <Row
            label="Upload size limit"
            value={`${MAX_UPLOAD_SIZE_MB} MB`}
            hint="Enforced server-side during streaming"
          />
        </Panel>

        <Panel title="Theme" subtitle="Appearance (saved to this browser)">
          <Row
            label="Color theme"
            value={
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setTheme("light")}
                  aria-pressed={theme === "light"}
                  className={`rounded-md border px-3 py-1.5 text-xs font-semibold ${
                    theme === "light"
                      ? "border-brand-500 bg-brand-50 text-brand-700"
                      : "border-gray-200 bg-surface text-gray-600 hover:border-gray-300"
                  }`}
                >
                  Light
                </button>
                <button
                  type="button"
                  onClick={() => setTheme("dark")}
                  aria-pressed={theme === "dark"}
                  className={`rounded-md border px-3 py-1.5 text-xs font-semibold ${
                    theme === "dark"
                      ? "border-brand-500 bg-brand-50 text-brand-700"
                      : "border-gray-200 bg-surface text-gray-600 hover:border-gray-300"
                  }`}
                >
                  Dark
                </button>
              </div>
            }
            hint="Also available from the top bar; respects system preference until you choose"
          />
        </Panel>

        <Panel title="Security" subtitle="Always-on protections (read-only)" className="xl:col-span-2">
          <div className="grid gap-x-8 sm:grid-cols-2">
            <Row label="Upload validation" value={`Signature checks on ${SUPPORTED_FILE_TYPES.split(",").join(", ").toUpperCase()}`} hint="File headers verified, not just extensions" />
            <Row label="Upload size limit" value={`${MAX_UPLOAD_SIZE_MB} MB`} hint="Enforced server-side during streaming" />
            <Row label="Path traversal" value={<Badge tone="ok">Protected</Badge>} hint="Storage keys are generated UUIDs; reads resolve inside the storage root" />
            <Row label="Audit trail" value={<Badge tone="ok">Metadata-only</Badge>} hint="No question text, answers, or document contents recorded" />
            <Row label="Credentials" value={<Badge tone="ok">Environment-only</Badge>} hint="No secrets in Git, bundle, or API responses" />
            <Row label="CORS" value={<Badge tone="ok">Origin allow-list</Badge>} hint="Configurable via CORS_ORIGINS environment variable" />
          </div>
          <p className="mt-3 flex items-start gap-2 text-xs text-gray-500">
            <Icon name="info" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            All settings on this page are read-only. Configuration changes are made through
            environment variables by the system administrator.
          </p>
          {statsUnavailable && (
            <p className="mt-1 text-xs text-gray-400">
              Retrieval statistics could not be loaded — the knowledge index may be empty or the
              database unavailable.
            </p>
          )}
        </Panel>
      </div>
    </>
  );
}

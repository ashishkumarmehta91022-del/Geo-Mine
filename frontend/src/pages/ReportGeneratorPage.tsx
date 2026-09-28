import { useMemo, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { analyzeReports, generateReportDocx } from "@/lib/reportAnalyticsApi";
import type {
  AnalyzeResponse,
  ChartSpec,
  Comparison,
  KPI,
  Trend,
} from "@/types/reportAnalytics";

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

/** Visual trust states — conflicted/review data must never look certain. */
function trustBadge(status: string): { label: string; className: string } {
  if (status === "review_required") {
    return {
      label: "REVIEW REQUIRED",
      className: "bg-amber-50 text-amber-700 border-amber-300",
    };
  }
  return { label: "VERIFIED", className: "bg-emerald-50 text-emerald-700 border-emerald-200" };
}

function kpiValue(kpi: KPI): string {
  if (kpi.value !== null) return kpi.value;
  return kpi.count !== null ? String(kpi.count) : "—";
}

function KpiCards({ kpis }: { kpis: KPI[] }) {
  const counts = kpis.filter((k) => k.name.startsWith("count_"));
  const aggregates = kpis.filter((k) => !k.name.startsWith("count_"));
  return (
    <section aria-label="KPI summary" className="mb-6 space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {counts.map((kpi) => (
          <div key={kpi.name} className="card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{kpi.label}</p>
            <p className="mt-1 text-2xl font-bold text-gray-800">{kpi.count ?? "—"}</p>
          </div>
        ))}
      </div>
      {aggregates.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <th className="px-4 py-2.5">Indicator</th>
                <th className="px-4 py-2.5">Metric</th>
                <th className="px-4 py-2.5">Period</th>
                <th className="px-4 py-2.5">Value</th>
                <th className="px-4 py-2.5">Unit</th>
                <th className="px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {aggregates.map((kpi) => {
                const badge = trustBadge(kpi.conflict_status);
                return (
                  <tr key={`${kpi.name}-${kpi.metric}-${kpi.reporting_period}`} className="text-gray-700">
                    <td className="px-4 py-2.5 font-medium">{kpi.label}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{kpi.metric ?? "—"}</td>
                    <td className="px-4 py-2.5">{kpi.reporting_period ?? "—"}</td>
                    <td className="px-4 py-2.5 font-mono">{kpiValue(kpi)}</td>
                    <td className="px-4 py-2.5">{kpi.unit ?? "—"}</td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${badge.className}`}>
                        {badge.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** Minimal inline-SVG line chart driven by the backend chart specification. */
function LineChart({ spec }: { spec: ChartSpec }) {
  const series = spec.series[0];
  if (!series) return null;
  const width = 560;
  const height = 220;
  const padding = { top: 16, right: 16, bottom: 34, left: 56 };
  const numeric = series.points.filter((p) => p.y !== null) as { x: string; y: number }[];
  const yValues = numeric.map((p) => p.y);
  const yMin = Math.min(...yValues, 0);
  const yMax = Math.max(...yValues, 1);
  const xLabels = series.points.map((p) => p.x);
  const xScale = (index: number) =>
    padding.left +
    (xLabels.length <= 1 ? 0 : (index * (width - padding.left - padding.right)) / (xLabels.length - 1));
  const yScale = (value: number) =>
    height - padding.bottom - ((value - yMin) / (yMax - yMin || 1)) * (height - padding.top - padding.bottom);
  const badge = trustBadge(spec.conflict_status);
  const path = numeric
    .map((point, i) => {
      const realIndex = series.points.findIndex((p) => p === point);
      return `${i === 0 ? "M" : "L"}${xScale(realIndex).toFixed(1)},${yScale(point.y).toFixed(1)}`;
    })
    .join(" ");
  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-700">{spec.title}</h3>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${badge.className}`}>
          {badge.label}
        </span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={spec.title} className="w-full">
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const y = padding.top + fraction * (height - padding.top - padding.bottom);
          const value = yMax - fraction * (yMax - yMin);
          return (
            <g key={fraction}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="#e5e7eb" strokeWidth="1" />
              <text x={padding.left - 6} y={y + 3} textAnchor="end" fontSize="9" fill="#9ca3af">
                {Math.round(value)}
              </text>
            </g>
          );
        })}
        <path d={path} fill="none" stroke="#2563eb" strokeWidth="2" />
        {series.points.map((point, index) => (
          <g key={point.x}>
            {point.y === null ? (
              <text x={xScale(index)} y={height - padding.bottom - 6} textAnchor="middle" fontSize="10" fill="#d97706">
                gap
              </text>
            ) : (
              <circle cx={xScale(index)} cy={yScale(point.y)} r="3.5" fill="#2563eb" />
            )}
            <text x={xScale(index)} y={height - padding.bottom + 14} textAnchor="middle" fontSize="9" fill="#6b7280">
              {point.x}
            </text>
          </g>
        ))}
      </svg>
      {spec.note && <p className="mt-2 text-xs text-amber-700">{spec.note}</p>}
    </div>
  );
}

/** Comparison bar chart with explicit gaps for unverified entities. */
function ComparisonChart({ spec, comparison }: { spec: ChartSpec; comparison?: Comparison }) {
  const series = spec.series[0];
  if (!series) return null;
  const badge = trustBadge(spec.conflict_status);
  const width = 560;
  const height = 220;
  const padding = { top: 16, right: 16, bottom: 34, left: 56 };
  const numeric = series.points.filter((p) => p.y !== null) as { x: string; y: number }[];
  const yMax = Math.max(...numeric.map((p) => p.y), 1);
  const slot = (width - padding.left - padding.right) / series.points.length;
  const barWidth = slot * 0.55;
  const yScale = (value: number) =>
    height - padding.bottom - (value / yMax) * (height - padding.top - padding.bottom);
  const sideFor = (label: string) =>
    comparison?.sides.find((side) => side.label === label);
  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-700">{spec.title}</h3>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${badge.className}`}>
          {badge.label}
        </span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={spec.title} className="w-full">
        {[0, 0.5, 1].map((fraction) => {
          const y = padding.top + fraction * (height - padding.top - padding.bottom);
          const value = yMax - fraction * yMax;
          return (
            <g key={fraction}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="#e5e7eb" strokeWidth="1" />
              <text x={padding.left - 6} y={y + 3} textAnchor="end" fontSize="9" fill="#9ca3af">
                {Math.round(value)}
              </text>
            </g>
          );
        })}
        {series.points.map((point, index) => {
          const x = padding.left + index * slot + (slot - barWidth) / 2;
          const side = sideFor(point.x);
          const conflicted = side?.validation_status === "review_required";
          return (
            <g key={point.x}>
              {point.y === null ? (
                <>
                  <rect x={x} y={padding.top} width={barWidth} height={height - padding.top - padding.bottom}
                        fill="repeating-linear-gradient(45deg,#fef3c7,#fef3c7 4px,#fde68a 4px,#fde68a 8px)"
                        opacity="0.5" />
                  <text x={x + barWidth / 2} y={height / 2} textAnchor="middle" fontSize="10" fill="#b45309">
                    no verified value
                  </text>
                </>
              ) : (
                <rect
                  x={x}
                  y={yScale(point.y)}
                  width={barWidth}
                  height={height - padding.bottom - yScale(point.y)}
                  fill={conflicted ? "#d97706" : "#2563eb"}
                >
                  <title>{`${point.x}: ${point.y}${spec.unit ? " " + spec.unit : ""}${conflicted ? " (review required)" : ""}`}</title>
                </rect>
              )}
              <text x={x + barWidth / 2} y={height - padding.bottom + 14} textAnchor="middle" fontSize="9" fill="#6b7280">
                {point.x}
              </text>
            </g>
          );
        })}
      </svg>
      {spec.note && <p className="mt-2 text-xs text-amber-700">{spec.note}</p>}
    </div>
  );
}

function TrendSection({ trends }: { trends: Trend[] }) {
  if (trends.length === 0) return null;
  return (
    <section aria-label="Trends" className="mb-6 space-y-3">
      {trends.map((trend) => {
        const badge = trustBadge(trend.status);
        return (
          <div key={`${trend.entity}-${trend.metric}`} className="card p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-gray-700">
                {trend.metric ?? "Value"}
                {trend.entity ? ` — ${trend.entity}` : ""}
                {trend.unit ? ` (${trend.unit})` : ""}
              </h3>
              <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${badge.className}`}>
                {badge.label}
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-600">
              {trend.direction}
              {trend.absolute_change !== null && (
                <> · change {trend.absolute_change}
                  {trend.percent_change !== null && <> ({trend.percent_change}%)</>}
                </>
              )}
            </p>
            {trend.missing_periods.length > 0 && (
              <p className="mt-1 text-xs text-amber-700">
                Missing periods: {trend.missing_periods.join(", ")}
              </p>
            )}
          </div>
        );
      })}
    </section>
  );
}

function InsightsSection({ insights }: { insights: AnalyzeResponse["insights"] }) {
  if (insights.length === 0) return null;
  const kindStyle: Record<string, string> = {
    CONFLICT: "bg-red-50 text-red-700 border-red-200",
    VALIDATION_WARNING: "bg-amber-50 text-amber-700 border-amber-200",
    DATA_GAP: "bg-blue-50 text-blue-700 border-blue-200",
    TREND: "bg-emerald-50 text-emerald-700 border-emerald-200",
    COMPARISON: "bg-purple-50 text-purple-700 border-purple-200",
    CHANGE: "bg-gray-100 text-gray-700 border-gray-200",
  };
  return (
    <section aria-label="Analytical insights" className="mb-6">
      <div className="card divide-y divide-gray-100">
        {insights.map((insight, index) => (
          <div key={index} className="flex items-start gap-3 p-3">
            <span className={`mt-0.5 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${kindStyle[insight.kind] ?? kindStyle.CHANGE}`}>
              {insight.kind}
            </span>
            <p className="text-sm text-gray-700">{insight.message}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Report Generator (Step 12): deterministic analytics over structured records. */
export default function ReportGeneratorPage() {
  const [title, setTitle] = useState("Periodic Analytics Report");
  const [reportType, setReportType] = useState("production");
  const [reportingPeriod, setReportingPeriod] = useState("");
  const [entities, setEntities] = useState("");
  const [metrics, setMetrics] = useState("");
  const [includeNarrative, setIncludeNarrative] = useState(false);
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const request = useMemo(
    () => ({
      title: title.trim() || "Periodic Analytics Report",
      report_type: reportType.trim() || null,
      reporting_period: reportingPeriod.trim() || null,
      entities: entities.split(",").map((e) => e.trim()).filter(Boolean),
      metrics: metrics.split(",").map((m) => m.trim()).filter(Boolean),
      include_narrative: includeNarrative,
    }),
    [title, reportType, reportingPeriod, entities, metrics, includeNarrative],
  );

  const load = async () => {
    setIsLoading(true);
    setIsError(false);
    setError(null);
    try {
      setData(await analyzeReports(request));
    } catch (cause: unknown) {
      setIsError(true);
      setError(cause instanceof Error ? cause.message : "Could not run the analysis.");
    } finally {
      setIsLoading(false);
    }
  };

  const download = async () => {
    setIsDownloading(true);
    try {
      await generateReportDocx(request);
    } catch (cause: unknown) {
      setIsError(true);
      setError(cause instanceof Error ? cause.message : "Could not generate the report.");
    } finally {
      setIsDownloading(false);
    }
  };

  const comparisonsByChart = useMemo(() => {
    const map = new Map<string, Comparison>();
    for (const comparison of data?.comparisons ?? []) {
      map.set(`${comparison.metric ?? ""} (${comparison.period ?? ""})`, comparison);
    }
    return map;
  }, [data]);

  return (
    <>
      <PageHeader
        title="Report Generator"
        description="Deterministic KPIs, trends, comparisons and insights over validated structured records — conflicting values are flagged for review, never averaged"
      />

      <section aria-label="Report specification" className="card mb-6 p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Title</label>
            <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Report type</label>
            <input className={inputClass} value={reportType} onChange={(e) => setReportType(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Reporting period</label>
            <input className={inputClass} placeholder="e.g. 2025-06 (blank = all)" value={reportingPeriod}
                   onChange={(e) => setReportingPeriod(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Entities (comma-separated)</label>
            <input className={inputClass} placeholder="blank = all" value={entities}
                   onChange={(e) => setEntities(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-600">Metrics (comma-separated)</label>
            <input className={inputClass} placeholder="blank = all" value={metrics}
                   onChange={(e) => setMetrics(e.target.value)} />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input type="checkbox" checked={includeNarrative}
                   onChange={(e) => setIncludeNarrative(e.target.checked)} />
            Include optional AI narrative (labeled; falls back to deterministic text)
          </label>
          <button type="button" className="btn-primary" disabled={isLoading} onClick={load}>
            {isLoading ? "Analyzing…" : "Run analysis"}
          </button>
          <button type="button" className="btn-secondary" disabled={isDownloading} onClick={download}>
            {isDownloading ? "Generating…" : "Download DOCX report"}
          </button>
        </div>
        <p className="mt-2 text-xs text-gray-400">
          Values come only from validated, non-conflicting records. Excluded values keep their raw form with reasons;
          conflicted data shows as gaps and is marked REVIEW REQUIRED.
        </p>
      </section>

      {isLoading && <StateBlock variant="loading" title="Running deterministic analysis…" />}
      {isError && (
        <StateBlock
          variant="error"
          title="Analysis failed"
          description={error ?? undefined}
          action={<button type="button" className="btn-primary" onClick={load}>Retry</button>}
        />
      )}
      {!isLoading && !isError && data && (
        <>
          {data.narrative && (
            <section aria-label="Narrative" className="card mb-6 p-4">
              <div className="mb-1 flex items-center gap-2">
                <h2 className="text-sm font-semibold text-gray-700">
                  {data.narrative.state === "ok" ? "Narrative (AI-generated)" : "Narrative (deterministic)"}
                </h2>
                <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${
                  data.narrative.state === "ok"
                    ? "bg-purple-50 text-purple-700 border-purple-200"
                    : "bg-gray-100 text-gray-600 border-gray-200"
                }`}>
                  {data.narrative.state === "ok" ? "AI-GENERATED — VERIFY" : "DETERMINISTIC"}
                </span>
              </div>
              <p className="text-sm text-gray-700">{data.narrative.narrative}</p>
              {data.narrative.state === "ok" && data.narrative.notice && (
                <p className="mt-2 text-xs text-purple-700">{data.narrative.notice}</p>
              )}
            </section>
          )}

          <KpiCards kpis={data.kpis} />
          <TrendSection trends={data.trends} />

          <section aria-label="Charts" className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {data.charts
              .filter((chart) => chart.chart_type === "line" || chart.chart_type === "comparison")
              .map((chart) =>
                chart.chart_type === "line" ? (
                  <LineChart key={chart.title} spec={chart} />
                ) : (
                  <ComparisonChart
                    key={chart.title}
                    spec={chart}
                    comparison={comparisonsByChart.get(chart.title)}
                  />
                ),
              )}
          </section>

          <InsightsSection insights={data.insights} />

          {data.excluded_values.length > 0 && (
            <section aria-label="Excluded values" className="card mb-6 p-4">
              <h2 className="text-sm font-semibold text-gray-700">
                Values excluded from arithmetic ({data.excluded_values.length})
              </h2>
              <p className="mt-1 text-xs text-gray-500">
                Raw values are preserved verbatim; reasons are explicit. Nothing was silently converted or resolved.
              </p>
              <ul className="mt-2 space-y-1 text-xs text-gray-600">
                {data.excluded_values.slice(0, 20).map((item) => (
                  <li key={`${item.record_id}-${item.reason}`} className="font-mono">
                    record {item.record_id} · raw “{item.value_raw ?? "—"}” · {item.reason}
                  </li>
                ))}
                {data.excluded_values.length > 20 && (
                  <li>… {data.excluded_values.length - 20} more</li>
                )}
              </ul>
            </section>
          )}
        </>
      )}
      {!isLoading && !isError && !data && (
        <StateBlock
          variant="empty"
          title="No analysis yet"
          description="Set a title and run the analysis — KPI cards, trend and comparison charts, insights and conflict indicators appear here."
        />
      )}
    </>
  );
}

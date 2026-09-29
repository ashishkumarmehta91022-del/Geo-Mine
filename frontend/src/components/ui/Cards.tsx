import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Icon, type IconName } from "@/components/ui/Icon";

/** MetricCard — polished KPI tile with label, large value, hint and status. */
export function MetricCard({
  label,
  value,
  hint,
  icon,
  tone = "neutral",
  to,
}: {
  label: string;
  value: number | string;
  hint?: string;
  icon?: IconName;
  tone?: "ok" | "warn" | "bad" | "neutral";
  to?: string;
}) {
  const accent =
    tone === "ok" ? "text-emerald-600" : tone === "warn" ? "text-amber-600" : tone === "bad" ? "text-red-600" : "text-brand-600";
  const body = (
    <div className="card h-full p-4 transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
        {icon && <Icon name={icon} className={`h-4.5 w-4.5 h-5 w-5 shrink-0 ${accent}`} />}
      </div>
      <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
      {hint && <p className="mt-1 text-[11px] leading-snug text-gray-500">{hint}</p>}
    </div>
  );
  return to ? (
    <Link to={to} className="block rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
      {body}
    </Link>
  ) : (
    body
  );
}

/** SectionHeader — small uppercase card/section title with optional link. */
export function SectionHeader({
  title,
  subtitle,
  linkTo,
  linkLabel,
}: {
  title: string;
  subtitle?: string;
  linkTo?: string;
  linkLabel?: string;
}) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <div>
        <h3 className="text-sm font-bold uppercase tracking-wide text-gray-600">{title}</h3>
        {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
      </div>
      {linkTo && (
        <Link to={linkTo} className="shrink-0 text-xs font-semibold text-brand-600 hover:underline">
          {linkLabel ?? "Open"} →
        </Link>
      )}
    </div>
  );
}

/** Panel — white card with a titled header used across all pages. */
export function Panel({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section aria-label={title ?? "section"} className={`card ${className}`}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 px-5 py-3">
          <div>
            {title && <h3 className="text-sm font-bold text-gray-700">{title}</h3>}
            {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

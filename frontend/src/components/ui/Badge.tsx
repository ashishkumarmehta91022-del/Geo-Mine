import type { ReactNode } from "react";

/**
 * Unified status badge vocabulary. Every state color in the app flows
 * through this component so meaning stays consistent:
 *   green = operational/pass · amber = warning/review · red = error/failed
 *   blue = informational/processing · gray = not configured / inactive
 *   violet = human-review workflow states
 */
export type BadgeTone = "ok" | "warn" | "bad" | "info" | "neutral" | "review";

const TONE_CLASSES: Record<BadgeTone, string> = {
  ok: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200",
  bad: "bg-red-50 text-red-700 border-red-200",
  info: "bg-brand-50 text-brand-700 border-brand-200",
  neutral: "bg-gray-100 text-gray-600 border-gray-200",
  review: "bg-violet-50 text-violet-700 border-violet-200",
};

export function Badge({
  tone,
  children,
  className = "",
}: {
  tone: BadgeTone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-2 py-0.5 text-[11px] font-semibold leading-none ${TONE_CLASSES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/** Map a validation/document/review status string onto the badge vocabulary. */
export function statusTone(status: string | null | undefined): BadgeTone {
  switch (status) {
    case "processed":
    case "pass":
    case "passed":
    case "valid":
    case "resolved":
    case "connected":
    case "OPERATIONAL":
    case "CONNECTED":
      return "ok";
    case "warning":
    case "review_required":
    case "in_review":
    case "DEGRADED":
      return "warn";
    case "failed":
    case "error":
    case "rejected":
    case "UNAVAILABLE":
      return "bad";
    case "processing":
    case "in review":
      return "info";
    case "NOT CONFIGURED":
    case "not_configured":
    case "open":
    case "uploaded":
    default:
      return "neutral";
  }
}

/** Pre-formatted badge for any backend status string. */
export function StatusBadge({ status }: { status: string | null | undefined }) {
  return <Badge tone={statusTone(status)}>{(status ?? "—").replace(/_/g, " ")}</Badge>;
}

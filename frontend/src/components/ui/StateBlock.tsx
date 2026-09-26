import type { ReactNode } from "react";

interface StateBlockProps {
  variant: "loading" | "empty" | "error";
  title: string;
  description?: string;
  /** Optional call-to-action, e.g. a Retry button. */
  action?: ReactNode;
}

const STYLES: Record<StateBlockProps["variant"], { border: string; badge: string; badgeText: string }> = {
  loading: {
    border: "border-gray-200",
    badge: "bg-gray-100",
    badgeText: "text-gray-600",
  },
  empty: {
    border: "border-gray-200",
    badge: "bg-brand-50",
    badgeText: "text-brand-700",
  },
  error: {
    border: "border-red-200 bg-red-50",
    badge: "bg-red-100",
    badgeText: "text-red-700",
  },
};

/**
 * Shared presentation for the three core UI states (loading, empty, error).
 * Every page shows one of these until real content is available.
 */
export default function StateBlock({ variant, title, description, action }: StateBlockProps) {
  const style = STYLES[variant];

  return (
    <div className={`card flex flex-col items-center justify-center px-6 py-16 text-center ${style.border}`}>
      {variant === "loading" && (
        <span
          className="mb-4 h-8 w-8 animate-spin rounded-full border-[3px] border-brand-600 border-t-transparent"
          role="status"
          aria-label="Loading"
        />
      )}
      {variant === "error" && (
        <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-lg font-bold text-red-600">
          !
        </span>
      )}
      {variant === "empty" && (
        <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-brand-50 text-lg font-bold text-brand-600">
          ⌀
        </span>
      )}

      <span className={`rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${style.badge} ${style.badgeText}`}>
        {variant}
      </span>
      <h3 className="mt-3 text-base font-semibold text-gray-900">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-gray-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

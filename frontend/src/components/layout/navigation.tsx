import type { IconName } from "@/components/ui/Icon";

export interface NavItem {
  label: string;
  path: string;
  icon: IconName;
  description: string;
}

/** Primary navigation — one entry per planned platform module. */
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", path: "/dashboard", icon: "dashboard", description: "Platform overview and system status" },
  { label: "Documents", path: "/documents", icon: "documents", description: "Browse and manage uploaded reports" },
  { label: "Data Explorer", path: "/data-explorer", icon: "data", description: "Explore extracted geological and mining data" },
  { label: "Knowledge Search", path: "/knowledge", icon: "search", description: "Search documents, records and validation results" },
  { label: "AI Query", path: "/ai-query", icon: "ai", description: "Ask questions over the knowledge base" },
  { label: "Report Generator", path: "/report-generator", icon: "report", description: "Compose standardised technical reports" },
  { label: "Topic Intelligence", path: "/topic-intelligence", icon: "topics", description: "Topic modelling and emerging themes" },
  { label: "Validation", path: "/validation", icon: "validation", description: "Rule-based checks on extracted data" },
  { label: "Review Queue", path: "/review-queue", icon: "review", description: "Human-in-the-loop review workflow" },
  { label: "Audit Logs", path: "/audit-logs", icon: "audit", description: "Traceability of every platform action" },
  { label: "Settings", path: "/settings", icon: "settings", description: "Platform configuration" },
];

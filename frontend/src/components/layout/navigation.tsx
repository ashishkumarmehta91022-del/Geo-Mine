import type { IconName } from "@/components/ui/Icon";

export interface NavItem {
  label: string;
  path: string;
  icon: IconName;
  description: string;
  /** Longer page context shown in the top bar. */
  context?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/** Primary navigation — grouped into the platform's logical domains. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [
      {
        label: "Dashboard",
        path: "/dashboard",
        icon: "dashboard",
        description: "Platform overview and system status",
        context: "Verified, traceable intelligence from geological, mining and production documents.",
      },
    ],
  },
  {
    label: "Data",
    items: [
      {
        label: "Documents",
        path: "/documents",
        icon: "documents",
        description: "Browse and manage uploaded reports",
        context: "Upload, process and inspect source documents with full provenance.",
      },
      {
        label: "Data Explorer",
        path: "/data-explorer",
        icon: "data",
        description: "Explore extracted geological and mining data",
        context: "Structured records extracted from documents, with validation status and sources.",
      },
      {
        label: "Knowledge Search",
        path: "/knowledge",
        icon: "search",
        description: "Search documents, records and validation results",
        context: "Lexical, semantic and hybrid retrieval over the knowledge index. Results are linked to source evidence.",
      },
    ],
  },
  {
    label: "Intelligence",
    items: [
      {
        label: "AI Query",
        path: "/ai-query",
        icon: "ai",
        description: "Ask questions over the knowledge base",
        context: "Evidence-grounded answers built only from retrieved, validated project data.",
      },
      {
        label: "Topic Intelligence",
        path: "/topic-intelligence",
        icon: "topics",
        description: "Topic modelling and emerging themes",
        context: "Deterministic keyword, topic and corpus analysis across the document set.",
      },
      {
        label: "Report Generator",
        path: "/report-generator",
        icon: "report",
        description: "Compose standardised technical reports",
        context: "Analytics and DOCX reporting generated from validated structured records.",
      },
    ],
  },
  {
    label: "Quality & Governance",
    items: [
      {
        label: "Validation",
        path: "/validation",
        icon: "validation",
        description: "Rule-based checks on extracted data",
        context: "Deterministic rule engine outcomes — errors, warnings and review flags per record.",
      },
      {
        label: "Review Queue",
        path: "/review-queue",
        icon: "review",
        description: "Human-in-the-loop review workflow",
        context: "Conflicts and low-confidence values wait here for a human decision — never auto-resolved.",
      },
      {
        label: "Audit Logs",
        path: "/audit-logs",
        icon: "audit",
        description: "Traceability of every platform action",
        context: "Metadata-only audit trail — what happened, when, on which entity.",
      },
    ],
  },
  {
    label: "System",
    items: [
      {
        label: "Settings",
        path: "/settings",
        icon: "settings",
        description: "Platform configuration",
        context: "Read-only system configuration and health reference.",
      },
    ],
  },
];

/** Flat list (routes, active-state helpers). */
export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

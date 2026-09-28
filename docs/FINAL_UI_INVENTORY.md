# Final UI Inventory

All routes transcribed from `frontend/src/App.tsx` + `navigation.tsx`.
Review-queue functionality is inside the **Validation** page; audit
activity is represented through the **Dashboard** — both verified against
the code.

## Live pages

| ROUTE | PAGE | PURPOSE | STATUS |
| --- | --- | --- | --- |
| `/` | — | Redirect to `/dashboard` | LIVE (redirect) |
| `/dashboard` | DashboardPage | Operational overview: health tiles, metrics, knowledge units, recent activity (audit metadata) | LIVE |
| `/documents` | DocumentsPage | Upload/browse documents; process; content viewer (native/OCR, confidence, provenance) | LIVE |
| `/data-explorer` | DataExplorerPage | Structured records + analytics views (KPI/trend/comparison, conflict exclusions) | LIVE |
| `/knowledge` | KnowledgePage | Knowledge search — lexical/semantic/hybrid with provenance | LIVE |
| `/validation` | ValidationPage | Validation results + embedded Review Queue (workflow states) | LIVE |
| `/report-generator` | ReportGeneratorPage | Report composition + DOCX generation/download | LIVE |
| `/topic-intelligence` | TopicIntelligencePage | Keywords, topics, word cloud, document relationships | LIVE |
| `/ai-query` | AIQueryPage | Evidence-grounded Q&A with citations + honest states | LIVE |

## Placeholder pages (nav entries exist; pages are placeholders)

| ROUTE | PURPOSE | STATUS |
| --- | --- | --- |
| `/review-queue` | Standalone review page — functionality lives in `/validation` | PLACEHOLDER (use Validation) |
| `/audit-logs` | Dedicated audit page — audit metadata renders in Dashboard recent activity | PLACEHOLDER (use Dashboard) |
| `/settings` | Platform configuration | PLACEHOLDER |

## Not implemented

| ROUTE | STATUS |
| --- | --- |
| `/settings` full functionality | NOT IMPLEMENTED (placeholder page only) |
| Authentication screens (login/RBAC UI) | NOT IMPLEMENTED (FUTURE) |

**UI build status:** `tsc -b && vite build` passes (TypeScript strict);
SPA served by nginx with same-origin `/api` proxy (statically verified;
container runtime NOT VERIFIED without Docker).

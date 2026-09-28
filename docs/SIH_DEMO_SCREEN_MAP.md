# SIH — Demo Screen Map (≈5 minutes)

Live routes only. Review Queue is inside **Validation**; audit activity is
represented through the **Dashboard**; placeholder routes (`/review-queue`,
`/audit-logs`, `/settings`) are never presented as live features. All data
shown is synthetic `DEMO_`-labelled demonstration data — not official
CMPDI/CIL figures.

| Demo Time | Screen | What Judge Sees | What It Proves |
| --- | --- | --- | --- |
| 0:00–0:20 | Problem framing (slide or verbal) | One scanned page + one spreadsheet of the same metric | The reporting problem is real, unstructured, multi-format |
| 0:20–1:00 | `/dashboard` | Health tiles (honest statuses), document/record/validation metrics, knowledge units, recent activity | Single operational view over the source of truth |
| 1:00–1:30 | `/documents` | Upload/open `DEMO_borehole_log.pdf`; processing + extraction statuses; provenance fields | Defensible ingestion with traceable storage |
| 1:30–2:10 | `/documents` content viewer | Native text vs OCR pages, extraction method, OCR confidence, verbatim original values | Extraction is transparent, originals preserved |
| 2:10–3:00 | `/validation` | PASS/WARNING/ERROR rollups; the 1200-vs-1350 conflict with both sources; review workflow states | Rule-based validation; conflicts go to humans, never auto-resolved |
| 3:00–3:30 | `/knowledge` | Search "coal production" (hybrid) — ranked results with document/page/record references | Retrieval over validated, provenance-carrying content |
| 3:30–4:00 | `/ai-query` | Grounded question on DEMO_MINE_A production; answer with evidence IDs + validation status | AI answers from evidence only — or refuses honestly |
| 4:00–4:20 | `/topic-intelligence` | Keywords, topics, word cloud, document relationships | Recurring themes identified deterministically |
| 4:20–4:40 | `/data-explorer` | KPI/trend/comparison views; conflict group excluded with explicit indicator | Analytics never silently include invalid values |
| 4:40–5:00 | `/report-generator` → `/dashboard` | DOCX generated (sources per figure, conflict section); return to dashboard recent activity for audit | Automated reporting + end-to-end traceability |

**Evidence-first rule:** at every screen, point at the provenance element
(source reference, evidence IDs, validation status) — the demo shows
evidence, not just UI. Full spoken script:
[`SIH_FINAL_DEMO_SCRIPT.md`](SIH_FINAL_DEMO_SCRIPT.md); recovery for any
failure mid-demo: [`SIH_DEMO_FAILURE_CHECKLIST.md`](SIH_DEMO_FAILURE_CHECKLIST.md);
per-screen evidence pointers: [`SIH_JUDGE_EVIDENCE_CHECKLIST.md`](SIH_JUDGE_EVIDENCE_CHECKLIST.md).

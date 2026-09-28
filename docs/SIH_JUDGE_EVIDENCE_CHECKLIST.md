# SIH — Judge Evidence Checklist

What can be shown **live**, and where. Each row names the application
screen (live routes only) and the backing API. If a judge asks "prove it",
this is the page to open.

| # | Evidence | Application screen | Backing API |
| --- | --- | --- | --- |
| 1 | Uploaded document | `/documents` (list + detail) | `POST /api/documents/upload`, `GET /api/documents` |
| 2 | Extracted text | `/documents` → content viewer (per page) | `GET /api/documents/{id}/content` |
| 3 | OCR result (text, boxes, confidence) | `/documents` content viewer, OCR page | `GET /api/documents/{id}/content`; OCR pipeline in `app/processing/ocr/` |
| 4 | Source reference (document/page/section) | Content viewer; every search/AI/report result | Provenance fields across `document_pages`, `extracted_records` |
| 5 | Validation result (rule, original vs expected) | `/validation` | `POST /api/validation/run/{id}`, `GET /api/validation/{id}` |
| 6 | Review-required conflict (both sources) | `/validation` (embedded Review Queue, workflow states) | `GET /api/validation/review-queue`, `PATCH`-style status update endpoint |
| 7 | Search result with provenance | `/knowledge` (lexical/semantic/hybrid) | `GET /api/search?...&mode=` |
| 8 | AI evidence with citations | `/ai-query` | `POST /api/ai/query` (evidence IDs filtered to real units) |
| 9 | Topic/keyword output | `/topic-intelligence` | `GET /api/intelligence/documents/{id}/keywords` `/topics` `/word-cloud`, `POST /api/intelligence/corpus/analyze` |
| 10 | KPI / trend / comparison | `/data-explorer` | Report analytics engines (`app/reports/analytics/`, `POST /api/reports/analyze`) |
| 11 | Generated DOCX | `/report-generator` (download) | `POST /api/reports/generate` |
| 12 | Audit activity | `/dashboard` → "Recent platform activity" | `audit_logs` rows; `GET /api/dashboard/summary` |

**Static back-ups if live infra is unavailable** (exact commands:
[`SIH_DEMO_RUNBOOK.md`](SIH_DEMO_RUNBOOK.md)):

- Test suites: 342 passed / 113 skipped (DB-dependent tests skip honestly
  without PostgreSQL) — `backend/tests/`.
- Provenance proof: `backend/tests/test_report_generation.py` ::
  `test_report_provenance_reaches_the_docx`.
- Deployment validation: `backend/tests/test_deployment_static.py` (20 tests).
- Embedding runtime proof: local model cache check (`EMBED_OK dims=384`,
  Step 17 log).
- Honesty proof: `/api/health` + `/api/dashboard/statuses` under a
  deliberate DB outage (Step 17 tests demonstrate the exact payloads).

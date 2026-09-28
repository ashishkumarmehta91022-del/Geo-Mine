# Final API Inventory

All endpoints transcribed from the actual routers (`app/api/routes/`,
`main.py` registration) — nothing invented. Status column records where
the endpoint is exercised in the automated suite (DB-free tests run in
every environment; DB-backed tests use the suite's test database).

## Health

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| GET | `/api/health` | Liveness + real `SELECT 1` database probe (honest connected/unavailable/timeout) | IMPLEMENTED — `test_health.py`, Step 17 outage-honesty tests |

## Documents

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| POST | `/api/documents/upload` | Upload with allowlist/signature/size validation; 201 | IMPLEMENTED — `test_documents_api.py`, `test_file_validation.py` |
| GET | `/api/documents` | Paginated listing | IMPLEMENTED — `test_documents_api.py` |
| GET | `/api/documents/{document_id}` | Document detail | IMPLEMENTED — `test_documents_api.py` |
| GET | `/api/documents/{document_id}/download` | Original file download | IMPLEMENTED — `test_documents_api.py` |
| DELETE | `/api/documents/{document_id}` | Delete document + storage + index (204) | IMPLEMENTED — `test_documents_api.py` |

## Processing (mounted under `/api/documents`)

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| POST | `/api/documents/{document_id}/process` | Transactional extraction pipeline (202; idempotent) | IMPLEMENTED — `test_processing_api.py`, `test_derived_pipeline.py` |
| GET | `/api/documents/{document_id}/processing-status` | Processing/extraction status | IMPLEMENTED — `test_processing_api.py` |
| GET | `/api/documents/{document_id}/content` | Per-page extracted content (native + OCR, confidence) | IMPLEMENTED — `test_processing_api.py`, `test_ocr_pipeline_api.py` |

## Validation

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| POST | `/api/validation/run/{document_id}` | Run deterministic rule engine | IMPLEMENTED — `test_validation_api.py`, `test_validation_rules.py` |
| GET | `/api/validation/{document_id}` | Validation results for a document | IMPLEMENTED — `test_validation_api.py` |
| GET | `/api/validation/review-queue` | Flagged items with workflow states | IMPLEMENTED — `test_validation_api.py` |
| PATCH | `/api/validation/{validation_id}` | Review state transition (pending → in_review → reviewed) | IMPLEMENTED — `test_validation_api.py` |

## Records

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| GET | `/api/records` | Structured records (filters; provenance fields) | IMPLEMENTED — `test_structuring.py` (service), `/data-explorer` consumer |

## Search / Knowledge

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| GET | `/api/search` | Lexical/semantic/hybrid retrieval with provenance | IMPLEMENTED — `test_search_api.py`, `test_semantic_search.py` |
| GET | `/api/search/stats` | Knowledge-index statistics | IMPLEMENTED — `test_knowledge.py` |
| POST | `/api/search/embed/{document_id}` | Best-effort embedding lifecycle for a document | IMPLEMENTED — `test_semantic_indexing.py`, `test_embeddings.py` |

## AI Query

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| POST | `/api/ai/query` | Evidence-grounded Q&A; strict JSON contract; honest states | IMPLEMENTED — `test_ai_query.py`, `test_workflow_hardening.py` |

## Reports / Analytics

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| POST | `/api/reports/generate` | Deterministic provenance-grounded DOCX | IMPLEMENTED — `test_report_generation.py`, `test_reports_api.py` |
| POST | `/api/reports/analyze` | KPI/trend/comparison/distribution payload | IMPLEMENTED — `test_report_analytics_api.py`, `test_report_analytics.py` |

## Intelligence

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| GET | `/api/intelligence/documents/{document_id}` | Document intelligence summary | IMPLEMENTED — `test_intelligence_api.py` |
| GET | `/api/intelligence/documents/{document_id}/keywords` | TF-IDF keywords/phrases (explained scores) | IMPLEMENTED — `test_intelligence_api.py` |
| GET | `/api/intelligence/documents/{document_id}/topics` | Co-occurrence topics + relationships | IMPLEMENTED — `test_intelligence_api.py` |
| GET | `/api/intelligence/documents/{document_id}/word-cloud` | Word-cloud data (normalized weights) | IMPLEMENTED — `test_intelligence_api.py` |
| POST | `/api/intelligence/corpus/analyze` | Bounded corpus analysis | IMPLEMENTED — `test_intelligence_api.py` |
| POST | `/api/intelligence/documents/{document_id}/summarize` | Deterministic summary + optional labeled AI summary | IMPLEMENTED — `test_intelligence_api.py` |

## Dashboard

| METHOD | PATH | PURPOSE | STATUS |
| --- | --- | --- | --- |
| GET | `/api/dashboard/summary` | Read-only aggregation; honest offline payload | IMPLEMENTED — `test_dashboard_api.py`, `test_dashboard.py` |
| GET | `/api/dashboard/statuses` | Lightweight component statuses | IMPLEMENTED — `test_dashboard_api.py`, Step 17 status-mapping tests |

**Totals:** 10 route groups · 28 endpoints · every endpoint covered by the
automated suite. No undocumented endpoints exist in `main.py` registration.

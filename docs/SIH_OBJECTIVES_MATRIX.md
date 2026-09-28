# SIH — Objectives → Features Matrix

Objective → Feature → Technical implementation → Demo screen → Evidence/test.
Screens are live routes only (placeholders are never presented; see
[`SIH_DEMO_SCREEN_MAP.md`](SIH_DEMO_SCREEN_MAP.md)).

| # | Objective | Feature | Technical implementation | Demo screen | Evidence / test |
| --- | --- | --- | --- | --- | --- |
| 1 | Automated document processing | Ingestion + processing pipeline | Defense-in-depth upload validation; transactional, idempotent pipeline; per-page native-vs-OCR dispatch | `/documents` | `test_documents_api.py`, `test_processing_api.py`, `test_file_validation.py` |
| 2 | Structured extraction | Structured records with provenance | Extractor registry (PyMuPDF/python-docx/openpyxl/xlrd/Pillow) + RapidOCR; verbatim `value_raw` + safe normalization | `/documents` (content viewer), `/data-explorer` | `test_extractors.py`, `test_structuring.py` |
| 3 | Validation | Deterministic rule engine | 7 rule families; PASS/WARNING/ERROR/REVIEW_REQUIRED; `original_value` vs `expected_value` | `/validation` | `test_validation_rules.py`, `test_validation_api.py` |
| 4 | Traceability | Provenance chain + audit metadata | document → page → record → validation → index → evidence → report; `audit_logs` (metadata-only) | `/validation`, `/report-generator`, `/dashboard` (activity) | `test_workflow_hardening.py`, `test_report_generation.py` |
| 5 | Retrieval | Knowledge search (lexical/semantic/hybrid) | tsvector + GIN index; fastembed 384-d JSONB embeddings; explicit hybrid scoring | `/knowledge` | `test_knowledge.py`, `test_search_api.py`, `test_semantic_search.py` |
| 6 | AI query-response | Evidence-grounded AI Query | Bounded evidence pack, strict JSON contract, citation filtering; `insufficient_evidence` / `llm_unavailable` honesty | `/ai-query` | `test_ai_query.py`, `test_workflow_hardening.py` |
| 7 | Topic intelligence | Keywords, topics, word cloud | Deterministic TF-IDF + co-occurrence clustering; explained scores; rebuildable | `/topic-intelligence` | `test_intelligence.py`, `test_intelligence_api.py` |
| 8 | Automated report generation | Provenance-grounded DOCX | Typed bounded spec; read-only data engine; conflict disclosure; byte-stable output | `/report-generator` | `test_report_generation.py`, `test_reports_api.py` |
| 9 | Analytics | KPI / trend / comparison / distribution | Deterministic engines over validated records; conflict-aware exclusions; descriptive insights | `/data-explorer` | `test_report_analytics.py`, `test_report_analytics_api.py` |
| 10 | Auditability | Audit trail + honest statuses | Metadata-only `audit_logs` across actions; dashboard recent activity; `/api/health` honesty | `/dashboard` (activity, health tiles) | `test_dashboard.py`, `test_deployment_static.py` |

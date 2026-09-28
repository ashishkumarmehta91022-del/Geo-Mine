# Final Requirements Traceability

Chain per requirement: **SIH problem → objective → implementation → API/UI
→ test → documentation.** Every IMPLEMENTED claim carries evidence.
Test files live in `backend/tests/`.

## R1 — Ingest scanned PDFs / digital documents / spreadsheets / images

- **Objective:** accept the real document formats the business uses.
- **Implementation:** extractor registry (PyMuPDF, python-docx, openpyxl,
  xlrd, Pillow) + RapidOCR pipeline; defense-in-depth upload validation.
- **API/UI:** `POST /api/documents/upload`, `POST /api/documents/{id}/process`,
  `GET /api/documents/{id}/content` · `/documents` page.
- **Test:** `test_documents_api.py`, `test_file_validation.py`,
  `test_processing_api.py`, `test_extractors.py`, `test_ocr_engine.py`.
- **Documentation:** `ARCHITECTURE.md` §processing; `SIH_PS_ALIGNMENT.md` R1–R5.

## R2 — Convert unstructured content into structured data

- **Objective:** entities/metrics/units with provenance, verbatim originals.
- **Implementation:** `StructuredRecordBuilder`, safe normalization.
- **API/UI:** `GET /api/records` · `/data-explorer`.
- **Test:** `test_structuring.py`, `test_derived_pipeline.py`.
- **Documentation:** `SIH_OBJECTIVES_MATRIX.md` #2; `FINAL_FEATURE_INVENTORY.md` Data Quality.

## R3 — Validate data quality and consistency

- **Objective:** deterministic, explainable quality gates; no silent winners.
- **Implementation:** rule engine (PASS/WARNING/ERROR/REVIEW_REQUIRED),
  cross-document conflict groups, review workflow states.
- **API/UI:** `POST /api/validation/run/{id}`, `GET /api/validation/{id}`,
  `GET /api/validation/review-queue`, `PATCH /api/validation/{validation_id}` · `/validation`.
- **Test:** `test_validation_rules.py`, `test_validation_api.py`.
- **Documentation:** `SIH_FINAL_DEMO_SCRIPT.md` Step 4; `SIH_TECHNICAL_NOVELTY.md` #4.

## R4 — Preserve traceability/provenance end-to-end

- **Objective:** every number traceable to its source document location.
- **Implementation:** provenance chain document → page → record →
  validation → index → evidence → report; metadata-only audit trail.
- **API/UI:** provenance fields across all read APIs · content viewer,
  `/dashboard` activity.
- **Test:** `test_report_generation.py` (`test_report_provenance_reaches_the_docx`),
  `test_workflow_hardening.py`.
- **Documentation:** `SIH_TECHNICAL_NOVELTY.md` #5; `SIH_JUDGE_EVIDENCE_CHECKLIST.md`.

## R5 — Search historical and current data together

- **Objective:** one searchable knowledge base over all ingested documents.
- **Implementation:** rebuildable `knowledge_index` (tsvector + GIN),
  lexical/semantic/hybrid retrieval, conflict-aware results.
- **API/UI:** `GET /api/search`, `GET /api/search/stats`,
  `POST /api/search/embed/{id}` · `/knowledge`.
- **Test:** `test_knowledge.py`, `test_search_api.py`,
  `test_semantic_search.py`, `test_semantic_indexing.py`.
- **Documentation:** `SIH_OBJECTIVES_MATRIX.md` #5; `SIH_FINAL_STORY.md` §4.

## R6 — AI query-response grounded in the corpus

- **Objective:** answers with citations; refusal without evidence.
- **Implementation:** bounded evidence packs, strict JSON contract,
  `insufficient_evidence` / `llm_unavailable` / `llm_error` honesty,
  injection-neutralized untrusted text.
- **API/UI:** `POST /api/ai/query` · `/ai-query`.
- **Test:** `test_ai_query.py`, `test_workflow_hardening.py`.
- **Documentation:** `SIH_PS_ALIGNMENT.md`; `SIH_TECHNICAL_NOVELTY.md` #2/#3.

## R7 — Topic identification across the corpus

- **Objective:** recurring themes without a topic-modeling framework.
- **Implementation:** TF-IDF keywords/phrases, co-occurrence topics,
  word-cloud data, topic↔document relationships.
- **API/UI:** `GET /api/intelligence/documents/{id}(/keywords|/topics|/word-cloud)`,
  `POST /api/intelligence/corpus/analyze` · `/topic-intelligence`.
- **Test:** `test_intelligence.py`, `test_intelligence_api.py`.
- **Documentation:** `SIH_OBJECTIVES_MATRIX.md` #7.

## R8 — Automated reporting from validated data

- **Objective:** the report writes itself from validated records.
- **Implementation:** typed bounded spec, read-only data engine,
  deterministic byte-stable DOCX, conflict disclosure, missing-data markers.
- **API/UI:** `POST /api/reports/generate`, `POST /api/reports/analyze` · `/report-generator`.
- **Test:** `test_report_generation.py`, `test_reports_api.py`.
- **Documentation:** `SIH_OBJECTIVES_MATRIX.md` #8; `FINAL_FEATURE_INVENTORY.md` Reporting.

## R9 — Analytics over the structured record store

- **Objective:** KPI/trend/comparison with explicit data-gap handling.
- **Implementation:** deterministic engines, conflict-aware exclusions,
  descriptive-only insights.
- **API/UI:** `POST /api/reports/analyze` · `/data-explorer`.
- **Test:** `test_report_analytics.py`, `test_report_analytics_api.py`.
- **Documentation:** `SIH_OBJECTIVES_MATRIX.md` #9.

## R10 — Operational visibility and auditability

- **Objective:** honest platform status; traceable actions.
- **Implementation:** dashboard aggregation, honest statuses, health probe,
  metadata-only `audit_logs`.
- **API/UI:** `GET /api/dashboard/summary`, `GET /api/dashboard/statuses`,
  `GET /api/health` · `/dashboard`.
- **Test:** `test_dashboard.py`, `test_dashboard_api.py`, `test_health.py`,
  `test_deployment_static.py`.
- **Documentation:** `SIH_DEMO_RUNBOOK.md`; `FINAL_TEST_MATRIX.md`.

## R11 — Reproducible deployment

- **Objective:** environment-driven configuration, container topology.
- **Implementation:** typed bounded Settings, constraints-pinned install,
  compose topology (health-gated), non-root backend container.
- **API/UI:** n/a (configuration).
- **Test:** `test_deployment_readiness.py`, `test_deployment_static.py`.
- **Documentation:** `SIH_DEMO_RUNBOOK.md`; `SIH_IMPLEMENTED_VS_FUTURE.md`.

## R12 — Demo/evaluation readiness

- **Objective:** synthetic, reproducible demonstration data + judge package.
- **Implementation:** `scripts/seed_demo_data.py` (DEMO_-labels, scoped
  `--reset`); complete SIH documentation set.
- **API/UI:** all live routes per `FINAL_UI_INVENTORY.md`.
- **Test:** `test_sih_demo_docs.py`, `test_sih_submission_docs.py`.
- **Documentation:** the full `docs/SIH_*.md` package.

> Runtime caveat carried honestly: seed execution and the seeded E2E walk
> are NOT VERIFIED in the development environment (no PostgreSQL); all
> other rows are test-evidenced.

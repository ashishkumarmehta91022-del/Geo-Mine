# Final Feature Inventory

Statuses: **IMPLEMENTED** (evidence-backed in the codebase) ·
**PARTIALLY IMPLEMENTED** (core exists, named gaps remain) ·
**FUTURE** (not built — not claimable) ·
**NOT VERIFIED** (requires infrastructure absent in the development
environment). Nothing is classified from plans.

## Document Processing

| Capability | Status | Evidence / note |
| --- | --- | --- |
| Upload | IMPLEMENTED | `POST /api/documents/upload`; defense-in-depth validation (`test_file_validation.py`) |
| File validation | IMPLEMENTED | Allowlist, MIME policy, magic-byte/OOXML signature checks, streaming size limit |
| Storage | IMPLEMENTED | `DocumentStorage` interface + `LocalFileStorage`; traversal-safe paths; swappable (object storage FUTURE) |
| PDF extraction | IMPLEMENTED | PyMuPDF 1.28.2, page-by-page provenance (`test_extractors.py`) |
| DOCX extraction | IMPLEMENTED | python-docx 1.2.0, paragraphs/headings/tables |
| XLS/XLSX extraction | IMPLEMENTED | openpyxl 3.1.5 (types preserved) + xlrd 2.0.2 (legacy .xls) |
| Image handling | IMPLEMENTED | Pillow 12.3.0 loader/validation feeding the OCR path |
| OCR | IMPLEMENTED | RapidOCR 1.2.3 on ONNX Runtime 1.30.0; bounding boxes + confidence; per-page native-vs-OCR dispatch; low confidence → review flag |

## Data Quality

| Capability | Status | Evidence / note |
| --- | --- | --- |
| Structured records | IMPLEMENTED | `StructuredRecordBuilder`; verbatim `value_raw` + normalized values; per-record provenance (`test_structuring.py`) |
| Normalization | IMPLEMENTED | Safe parsing/normalization alongside verbatim originals — originals never modified |
| Validation rules | IMPLEMENTED | Deterministic rule families; PASS/WARNING/ERROR/REVIEW_REQUIRED (`test_validation_rules.py`) |
| Duplicate detection | IMPLEMENTED | Duplicate-equality rule family within the validation engine |
| Cross-document conflicts | IMPLEMENTED | Conflict groups keep BOTH values + sources; no auto-winner (Step 6/15 tests) |
| Review queue | IMPLEMENTED | `GET /api/validation/review-queue` + `PATCH` workflow states (pending → in_review → reviewed); embedded in Validation UI |

## Knowledge

| Capability | Status | Evidence / note |
| --- | --- | --- |
| Knowledge index | IMPLEMENTED | Idempotent tsvector + GIN over pages/records/validations; rebuildable (`test_knowledge.py`) |
| Lexical search | IMPLEMENTED | Deterministic keyword/phrase ranking, documented (`test_search_api.py`) |
| Semantic search | IMPLEMENTED | fastembed `BAAI/bge-small-en-v1.5` 384-d, JSONB storage (`test_semantic_search.py`); model cache RUNTIME VERIFIED |
| Hybrid search | IMPLEMENTED | Explicit hybrid scoring; `mode=lexical\|semantic\|hybrid`; honest degradation |
| Provenance | IMPLEMENTED | Every search result carries document/page/record references; conflict-aware |

## AI

| Capability | Status | Evidence / note |
| --- | --- | --- |
| Evidence construction | IMPLEMENTED | Bounded, provenance-complete evidence packs from the knowledge index |
| RAG | IMPLEMENTED | Validation-aware, strict JSON contract, citation filtering to real IDs (`test_ai_query.py`) |
| AI Query | IMPLEMENTED | `POST /api/ai/query`; UI `/ai-query` |
| LLM provider abstraction | IMPLEMENTED | OpenAI-compatible / labeled mock; configuration-driven (`app/llm/`) |
| Unavailable/error states | IMPLEMENTED | `insufficient_evidence` (LLM never invoked), `llm_unavailable` (evidence still returned), `llm_error` |
| Prompt-injection protection | IMPLEMENTED | Document text untrusted: delimiters neutralized, system rules unreachable (Step 15 tests) |

## Reporting

| Capability | Status | Evidence / note |
| --- | --- | --- |
| Report specification | IMPLEMENTED | Typed bounded specification (`app/reports/spec.py`) |
| Validated data selection | IMPLEMENTED | Read-only data engine over structured records (`test_report_generation.py`) |
| Conflict handling | IMPLEMENTED | Conflict groups disclosed (REVIEW REQUIRED) — never resolved away |
| DOCX generation | IMPLEMENTED | Byte-stable output, explicit missing-data markers; DOCX-only (PDF FUTURE/not attempted) |
| Provenance/evidence | IMPLEMENTED | Per-figure sources reach the document (`test_report_provenance_reaches_the_docx`) |

## Analytics

| Capability | Status | Evidence / note |
| --- | --- | --- |
| KPI | IMPLEMENTED | Deterministic KPI engine (`app/reports/analytics/`) |
| Trends | IMPLEMENTED | Trend/comparison engines with explicit period handling |
| Comparisons | IMPLEMENTED | Cross-entity/period comparisons, descriptive only |
| Data gaps | IMPLEMENTED | Explicit missing-data markers — gaps visible, not interpolated |
| Conflict exclusion | IMPLEMENTED | Conflict groups excluded with an explicit indicator (`test_report_analytics.py`) |

## Intelligence

| Capability | Status | Evidence / note |
| --- | --- | --- |
| Keywords | IMPLEMENTED | Deterministic TF-IDF with explained `score_reason` (`test_intelligence.py`) |
| Topics | IMPLEMENTED | Co-occurrence clustering (Jaccard ≥ 0.3), derived labels — explicitly not official CMPDI/CIL topic definitions |
| Word cloud | IMPLEMENTED | Normalized 0..1 weights as DATA; frontend renders |
| Document relationships | IMPLEMENTED | Topic ↔ document scores with supporting terms/sources |
| Summaries | IMPLEMENTED | Deterministic summary always authoritative; optional LLM summary labeled AI-GENERATED — VERIFY |

## Operations

| Capability | Status | Evidence / note |
| --- | --- | --- |
| Dashboard | IMPLEMENTED | `GET /api/dashboard/summary` + `/statuses`; honest offline state, never fake zeroes |
| Health | IMPLEMENTED | `/api/health` with real `SELECT 1` probe; HTTP 200 under outage |
| Deployment configuration | IMPLEMENTED (statically verified) | Compose topology, Dockerfiles, nginx, `.dockerignore` — runtime NOT VERIFIED (Docker absent) |
| Audit metadata | IMPLEMENTED | `audit_logs` across actions; metadata-only (counts/actions/ids) |
| Demo tooling | IMPLEMENTED (execution NOT VERIFIED) | `scripts/seed_demo_data.py` + `--reset`; DEMO_-labelled; safety test-enforced |

---
Cross-references: [`FINAL_API_INVENTORY.md`](FINAL_API_INVENTORY.md) ·
[`FINAL_UI_INVENTORY.md`](FINAL_UI_INVENTORY.md) ·
[`FINAL_TEST_MATRIX.md`](FINAL_TEST_MATRIX.md) ·
[`FINAL_KNOWN_LIMITATIONS.md`](FINAL_KNOWN_LIMITATIONS.md)

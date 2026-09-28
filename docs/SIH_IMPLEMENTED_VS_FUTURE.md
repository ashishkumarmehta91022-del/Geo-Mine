# SIH — Implemented vs Future

Statuses only as supported by the actual codebase (Steps 1–17).
**FUTURE rows are not implemented and must not be claimed in the demo.**

| Capability | Status | Evidence |
| --- | --- | --- |
| Document upload | Implemented | `POST /api/documents/upload` — defense-in-depth validation, swappable storage (`app/api/routes/documents.py`, `app/services/document_storage.py`) |
| OCR | Implemented | RapidOCR/ONNX pipeline with confidence + review flagging (`app/processing/ocr/`) |
| Validation | Implemented | Deterministic rule engine, PASS/WARNING/ERROR/REVIEW_REQUIRED (`app/validation/`) |
| Review queue | Implemented | `GET /api/validation/review-queue` + workflow states; embedded in the Validation page |
| Knowledge search | Implemented | `GET /api/search` — lexical over tsvector+GIN (`app/api/routes/search.py`) |
| Semantic search | Implemented | fastembed ONNX, `BAAI/bge-small-en-v1.5` 384-d, JSONB on `knowledge_index` (`app/embeddings/`) |
| Hybrid search | Implemented | Explicit hybrid scoring, `mode=lexical\|semantic\|hybrid` (`app/services/knowledge_service.py`) |
| Evidence-grounded AI | Implemented | `POST /api/ai/query` — bounded evidence, strict JSON contract, honest states (`app/ai/`) |
| Automated DOCX report | Implemented | `POST /api/reports/generate` — deterministic, provenance-per-figure (`app/reports/`) |
| Analytics | Implemented | Deterministic KPI/trend/comparison/distribution engines, conflict-aware (`app/reports/analytics/`) |
| Topic intelligence | Implemented | TF-IDF keywords/phrases, co-occurrence topics, word-cloud data (`app/intelligence/`) |
| Dashboard | Implemented | `GET /api/dashboard/summary` + `/statuses`, honest offline state (`app/dashboard/`) |
| Audit metadata | Implemented | `audit_logs` writes across pipeline actions; metadata-only payloads |
| Health/monitoring (honest statuses) | Implemented | `/api/health` + status mapping, DB-outage honesty (Step 17 tests) |
| Demo seed / reset safety | Implemented | `scripts/seed_demo_data.py` with `DEMO_` labels and scoped `--reset` |
| Container deployment config | Implemented (statically verified) | `docker-compose.yml`, Dockerfiles, nginx.conf — runtime NOT VERIFIED without Docker |
| Authentication / RBAC | Future | not implemented — unauthenticated prototype; documented limitation |
| Enterprise SSO / identity | Future | not implemented |
| Production vector ANN (pgvector) | Future | planned; JSONB embeddings exist today |
| Background processing workers | Future | not implemented — processing is synchronous |
| Object storage (S3-compatible) | Future | not implemented — local FS storage behind an interface |
| Full production monitoring | Future | not implemented — honest health/status endpoints only |
| Horizontal API scaling | Future | not exercised — single-process uvicorn configuration |
| Report artifact persistence / download history | Future | not implemented — in-memory DOCX generation |

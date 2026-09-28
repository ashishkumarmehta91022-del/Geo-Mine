# SIH Technical Cheat Sheet

Actual versions only — verified pins from `backend/constraints.txt` /
`backend/requirements.txt` / `frontend/package.json`.

## Stack

| Layer | Technology | Version (verified) |
| --- | --- | --- |
| Backend framework | FastAPI | 0.141.1 |
| ASGI server | uvicorn | 0.54.0 |
| Configuration / validation | pydantic / pydantic-settings | 2.13.5 / 2.15.0 |
| Database ORM / migrations | SQLAlchemy / Alembic | 2.1.1 / 1.20.0 |
| Database | PostgreSQL (source of truth) | 16 (compose image `postgres:16-alpine`) |
| PDF extraction | PyMuPDF | 1.28.2 |
| DOCX extraction | python-docx | 1.2.0 |
| XLSX extraction | openpyxl | 3.1.5 |
| Legacy XLS extraction | xlrd | 2.0.2 |
| Image handling | Pillow | 12.3.0 |
| OCR | rapidocr-onnxruntime (PaddleOCR models on ONNX Runtime CPU) | 1.2.3 / onnxruntime 1.30.0 |
| Embeddings | fastembed (local ONNX, `BAAI/bge-small-en-v1.5`, 384-dim) | 0.8.1 |
| Report generation | python-docx (deterministic DOCX) | 1.2.0 |
| Frontend | React + TypeScript + Vite | 18.3 / 5.6 / 5.4.21 |
| Routing / styling | react-router-dom + tailwindcss | 6.26 / 3.4 |
| Tests | pytest (+ httpx TestClient) | 8.4.2 |
| Deployment | Docker / docker compose / nginx | Dockerfiles + compose validated statically |

## Key subsystems (one-liners)

- **Frontend stack:** React 18 + TypeScript + Vite + Tailwind; SPA with
  same-origin `/api` (Vite dev proxy; nginx reverse proxy in production).
- **Backend stack:** FastAPI, layered `api/routes → services → models`;
  typed bounded Settings from `.env`; central error handling.
- **Database:** PostgreSQL source of truth; Alembic migrations 0001–0006
  (`alembic upgrade head`); tables: documents, document_pages,
  extracted_records, validation_results, knowledge_index, audit_logs.
- **OCR:** RapidOCR/ONNX for scans/images with bounding boxes +
  confidence; per-page native-vs-OCR dispatch; low confidence →
  `review_required` (never silently accepted).
- **Document extraction:** extractor registry (PyMuPDF / python-docx /
  openpyxl / xlrd / Pillow); deterministic, no AI; provenance +
  source references per page/section/sheet.
- **Embeddings:** fastembed local ONNX; `BAAI/bge-small-en-v1.5`, 384-dim;
  cached at first use (offline after cache); stored as JSONB on
  `knowledge_index`; bounded inputs.
- **Retrieval:** knowledge index (tsvector + GIN); `mode=lexical|semantic|
  hybrid` with explicit hybrid scoring; provenance and conflict
  preservation in results.
- **RAG:** bounded provenance-complete evidence pack → strict JSON
  contract; citation filtering to real IDs; `insufficient_evidence` (no
  LLM call), `llm_unavailable` (evidence still returned); document text
  untrusted (delimiters neutralized, system rules unreachable).
- **Validation:** deterministic rule families; PASS/WARNING/ERROR/
  REVIEW_REQUIRED; `original_value` vs `expected_value`;
  cross-document conflict groups with both sides preserved.
- **Analytics:** deterministic KPI/trend/comparison/distribution engines;
  conflict-aware exclusions; descriptive insights only.
- **Reporting:** `POST /api/reports/generate` → byte-stable DOCX from
  validated records; per-figure provenance; explicit missing-data
  markers; no LLM in the data path.
- **Deployment:** compose topology postgres→backend→frontend
  (health-gated, persistent volumes, non-root backend); migrations at
  container start; runtime NOT VERIFIED without Docker in our environment.
- **Security:** env-based secrets (none in Git), upload allowlist +
  magic-byte signatures + size limits, path-traversal-safe storage,
  non-root container, bounded prompts + injection neutralization,
  metadata-only audit, human review gate.

## Limitations (honest)

- No authentication/RBAC — unauthenticated prototype; do not expose publicly.
- Docker/PostgreSQL runtime validation NOT VERIFIED in the development
  environment (statically verified only; commands documented in the runbook).
- DOCX only (no PDF output — never attempted).
- LLM optional: honest unavailable state without credentials; AI outputs
  always labeled.
- Processing is synchronous; no background workers yet (FUTURE).
- Report artifacts are generated in-memory (no persistence/history — FUTURE).

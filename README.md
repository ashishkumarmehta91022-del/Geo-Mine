# CMPDI AI Reporting Platform

**Smart India Hackathon 2026 — Problem Statement SIH26023**
*AI-Powered Geological, Mining and other Reporting Solution for CMPDI / CIL subsidiaries.*

## Project Objective

Central Mine Planning & Design Institute (CMPDI) and Coal India Limited (CIL)
subsidiaries produce large volumes of geological and mining reports (exploration
reports, borehole logs, mine plans, compliance documents — often scanned PDFs
and Excel sheets). Today, extracting, validating, cross-referencing and
reporting on that data is slow and manual.

This platform will let users ingest those documents, automatically extract and
validate the data inside them, query the knowledge base in natural language,
and generate standardised technical reports — with full traceability and audit
logs.

> **Current status: Step 1 — Project Foundation.** This repository currently
> provides the application shell only (see *Current Implementation Status*
> below). No document processing, OCR, AI, RAG or report generation is
> implemented yet.

## Technology Stack

| Layer     | Technology                                   |
| --------- | -------------------------------------------- |
| Frontend  | React 18 + TypeScript + Vite + Tailwind CSS  |
| Backend   | Python 3.11+ · FastAPI · SQLAlchemy 2        |
| Database  | PostgreSQL (connection architecture only)    |
| Testing   | pytest (backend) · `tsc` + `vite build` (frontend) |

## Folder Structure

```
.
├── frontend/          # React + TypeScript + Tailwind app shell
│   └── src/
│       ├── components/   # layout (sidebar/header) + reusable UI
│       ├── hooks/        # data-fetching hooks
│       ├── lib/          # API client, env helpers
│       ├── pages/        # routed pages (dashboard + placeholders)
│       └── types/        # shared TypeScript types
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── api/routes/   # HTTP routers (health)
│   │   ├── core/         # (reserved: security, constants)
│   │   ├── models/       # ORM models (added in a later step)
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── services/     # business logic (added in later steps)
│   │   └── utils/        # shared helpers
│   └── tests/            # pytest suite
├── data/              # local sample documents (not committed)
├── docs/              # architecture & future module docs
├── scripts/           # helper scripts (database setup, seeds — later)
├── .env.example       # all environment variables, no secrets
└── README.md
```

## Frontend Setup

Requires Node.js 18+.

```bash
cd frontend
npm install
npm run dev          # dev server on http://localhost:5173
```

Production build & typecheck:

```bash
npm run build        # runs tsc -b && vite build, outputs to frontend/dist
npm run preview      # serve the production build locally
```

## Backend Setup

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
copy ..\.env.example .env         # Windows  (macOS/Linux: cp ..\.env.example .env)
```

Run the API:

```bash
uvicorn app.main:app --reload     # http://localhost:8000, docs at /docs
```

Run tests:

```bash
pytest
```

## Database Setup (PostgreSQL)

**PostgreSQL 14+ is required for database features.** The API itself still
starts without it — `/api/health` then reports the database as offline.

1. Install PostgreSQL and create the development database:
   ```sql
   CREATE DATABASE cmpdi_reporting;
   CREATE USER cmpdi_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE cmpdi_reporting TO cmpdi_user;
   ```
2. Configure credentials in `backend/.env` (or the root `.env`) — either a
   single `DATABASE_URL` or the discrete `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`
   variables (see *Environment Variables*). Never commit real credentials.
3. Apply migrations (the schema's source of truth):
   ```bash
   cd backend
   alembic upgrade head        # creates the 5 foundation tables
   alembic downgrade base      # undo, if needed
   ```
4. Optional DEMO data (generic sample values, clearly labelled — **not** real
   CMPDI/CIL figures):
   ```bash
   python ../scripts/seed_demo_data.py          # from backend/ with venv active
   python ../scripts/seed_demo_data.py --reset  # remove the DEMO rows
   ```
5. Verify: `curl http://localhost:8000/api/health` → `"database": {"connected": true, ...}`

Integration tests that need a live database run only when you opt in:

```bash
CMPDI_TEST_DATABASE_URL=postgresql://cmpdi_user:...@localhost:5432/cmpdi_reporting pytest -m db
```

## Environment Variables

Copy `.env.example` to `.env` (root and/or `backend/`) and fill in real values.
**Never commit `.env` files.**

| Variable        | Used by   | Required to start? | Purpose                                   |
| --------------- | --------- | ------------------ | ----------------------------------------- |
| `DATABASE_URL`  | backend   | No                 | PostgreSQL connection string (wins over `DB_*` when set) |
| `DB_HOST` / `DB_PORT` | backend | No             | Discrete DB connection variables (used when `DATABASE_URL` empty) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | backend | No | Discrete DB connection variables                    |
| `LLM_PROVIDER`  | backend   | No                 | AI provider name (unused until later steps) |
| `LLM_API_KEY`   | backend   | No                 | AI provider key (unused until later steps) |
| `ENVIRONMENT`   | backend   | No                 | `development` / `production`              |
| `DEBUG`         | backend   | No                 | Verbose logging when `true`               |
| `CORS_ORIGINS`  | backend   | No                 | Comma-separated allowed origins           |
| `DOCUMENT_STORAGE_PATH` | backend | No             | Local storage dir for uploads (default `./storage/documents`) |
| `MAX_UPLOAD_SIZE_MB` | backend   | No                 | Upload size limit (default `25`)          |
| `VITE_API_BASE_URL` | frontend | No              | Override API origin (empty = same origin via dev proxy) |

The application **must and does start without any AI credentials**.

## How to Run the Application

Two terminals:

```bash
# Terminal 1 — backend (first time: apply migrations with `alembic upgrade head`)
cd backend && uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open <http://localhost:5173>. The header shows a live **API online/offline**
indicator; the Dashboard shows backend/database status. Verify the API
directly at <http://localhost:8000/api/health>.

## Document Upload & Storage (Step 3)

The platform accepts original report files and registers them for later
processing pipelines (OCR/extraction are **not** part of this step).

**Supported file types (enforced allowlist):** PDF, DOCX, XLSX, XLS, PNG, JPG, JPEG
— validated by extension **and** content signature (magic bytes for PDF/PNG/JPEG,
ZIP-container + required OOXML entries for DOCX/XLSX), plus a MIME-type policy.

**Upload size limit:** `MAX_UPLOAD_SIZE_MB` (default **25 MB**), enforced while
streaming — files are never fully buffered in memory.

**Local storage (development):** `DOCUMENT_STORAGE_PATH` (default `./storage/documents`).
Files are stored under generated UUID keys (never the client filename); the
original filename is kept as metadata only. The storage layer is an interface —
swappable for S3/Azure/MinIO later without touching routes or services.

**API endpoints:**

| Method | Path                    | Purpose                                  |
| ------ | ----------------------- | ---------------------------------------- |
| POST   | `/api/documents/upload` | Multipart upload (`upload` field) → 201  |
| GET    | `/api/documents`        | Paginated list (`page`, `page_size` ≤ 100) |
| GET    | `/api/documents/{id}`   | Metadata only (404 if missing)           |
| GET    | `/api/documents/{id}/download` | Streams the original file          |
| DELETE | `/api/documents/{id}`   | Removes record + stored file             |

**Security limitations (by design at this stage):**

- **No authentication / authorization yet** — upload and deletion are
  unrestricted until the auth step; do not expose the API publicly.
- Uploaded files are stored, never executed or rendered.
- Path-traversal, null-byte and absolute-path filenames are sanitized;
  stored names are always server-generated.

## OCR & Scanned Document Processing (Step 5)

**Step 5 adds deterministic OCR — still no LLM/RAG/AI of any kind.**

**Selected engine:** `rapidocr-onnxruntime` 1.2.3 (ONNX Runtime 1.30.0, CPU).
PaddleOCR's model stack executed on ONNX Runtime — chosen because PaddleOCR
itself has no distribution for this environment (Python 3.14 on Windows),
while RapidOCR runs with **no system dependencies** (models ship inside the
wheel) and is fully deterministic. Per-word bounding boxes and confidence
scores are preserved.

**Workflow:** image bytes → Pillow validation (integrity, dimension guardrails,
decompression-bomb cap) → OCR engine (wall-clock timeout) → verbatim text +
boxes + confidences → `review_required` flag for boxes under
`OCR_CONFIDENCE_THRESHOLD` (default 0.70) → stored in `document_pages.structured_metadata["ocr"]`.

**Native vs scanned PDFs — decided per page, never per document:**

| Page kind | Detection | Path |
| --------- | --------- | ---- |
| Native text | ≥ 8 extracted chars (PyMuPDF) | Step 4 path, no OCR |
| Scanned / image-only | < 8 chars | rendered at `PDF_OCR_ZOOM` (≈144 dpi) → OCR → `ocr_extracted` |

A mixed PDF (native, scan, native, scan…) processes each page independently;
scan pages never reclassify the document.

**Faithfulness rule:** OCR text is stored **verbatim**. A low-confidence `1O5`
is never silently "corrected" to `105` — it is flagged `review_required: true`
with its confidence and bounding box, and left for human review.

**Statuses per page/image:** `extracted` (native) · `ocr_extracted` · `no_text`
· `failed` (engine error isolated to that page) · `ocr_required` (engine
unavailable). Document-level aggregate includes `mixed`.

**OCR configuration:** `OCR_CONFIDENCE_THRESHOLD=0.70`, `OCR_TIMEOUT_SECONDS=120`,
`OCR_MAX_IMAGE_PIXELS=40000000`, `PDF_OCR_ZOOM=2.0` (see `.env.example`).

**Known limitations:** Latin-script models bundled (other languages need
extra model files); scanned pages OCR at ~1–3 s/page on CPU; handwriting and
very low-quality scans may yield low confidence (flagged, not guessed);
pages whose scans contain no text honestly report `no_text`.

## Validation & Data Quality Engine (Step 6)

**Deterministic rule-based validation over extracted/OCR data — no LLM, no
randomness, no automatic corrections.** Given the same data and configuration,
validation always produces identical results.

**Statuses:** `pass` (satisfies the rule) · `warning` (unusual, not necessarily
invalid) · `error` (violates a configured rule) · `review_required` (the system
cannot safely decide — a human must inspect the source). Uncertain data is
never silently promoted to valid.

**Severity:** `info` · `warning` · `error` · `critical` (only when a rule
declares it). Ordinary data-quality issues are not inflated.

**Rules (each independently testable, registered in `DEFAULT_RULES`):**

| Rule | Codes | Notes |
| ---- | ----- | ----- |
| Required field | `REQUIRED_FIELD_MISSING` | missing values generate results, never defaults |
| Numeric | `NUMERIC_FORMAT`, `NUMERIC_NEGATIVE`, `NUMERIC_INTEGER_EXPECTED` | parseable/positive/integer checks per field config |
| Range | `RANGE_OUT_OF_BOUNDS` | configurable min/max, inclusive/exclusive, error-vs-warning |
| Date | `DATE_INVALID`, `DATE_FUTURE` | documented formats only; future dates when configured |
| OCR confidence | `OCR_LOW_CONFIDENCE`, `OCR_REVIEW_FLAGGED` | Step 5 `review_required`/confidence → `review_required` |
| Duplicates | `DUPLICATE_DETECTED` | configured key → WARNING; flagged, never deleted |
| Cross-document | `CROSS_DOCUMENT_CONFLICT` | same key, different values → both sides preserved, **no winner selected** |

**Data-integrity guarantee:** validation NEVER modifies extracted values. A
detected `1O5` stays `1O5` — flagged for review, not "corrected" to `105`.

**APIs:** `POST /api/validation/run/{document_id}` · `GET /api/validation/{document_id}`
· `GET /api/validation/review-queue` (open items with provenance) ·
`PATCH /api/validation/{id}` (review decision: `open` / `in_review` / `resolved` /
`rejected` + notes — affects review state only).

**Frontend:** Validation page with summary cards (total / passed / warnings /
errors / review required), result list (rule, status, severity, source, value,
expected) and the human review queue — including an explicit **Source A vs
Source B** display for conflicts.

> ⚠️ **Demonstration rules:** the shipped thresholds/ranges/keys (e.g. the
> `entity_name + reporting_period` duplicate key and the 0–10,000,000 range)
> are **demo defaults for development only — not authoritative CMPDI/CIL
> rules**. Authoritative limits must come from project requirements and be
> supplied via `ValidationConfig` without code changes.

## Document Processing Pipeline (Step 4)

**Step 4 does NOT perform OCR, does NOT use AI, and does NOT generate reports.**
It builds the deterministic extraction foundation those future layers consume.

```
Upload → Validation → Storage → Processing → Extractor Selection
      → Text/Table/Metadata Extraction → Normalization → Traceable Extraction Result
      → (future: AI/RAG layer)
```

**Trigger:** `POST /api/documents/{id}/process` (synchronous prototype — the
service is async-ready by design). Lifecycle: `uploaded → processing → processed`
or `processing → failed` with the real error preserved in `error_message`.
Re-processing replaces previous page rows — never duplicates.

**Extractors (registered in a registry — no if/elif pipelines):**

| Type            | Library (version recorded per extraction) |
| --------------- | ----------------------------------------- |
| PDF (`.pdf`)    | PyMuPDF — page-by-page text + page metadata |
| DOCX (`.docx`)  | python-docx — paragraphs + tables in reading order |
| XLSX (`.xlsx`)  | openpyxl — sheets, typed cells (int/float/str/date/bool/null), formulas never evaluated |
| XLS (`.xls`)    | xlrd — same contract as XLSX |
| Images          | Pillow — metadata only; text marked `ocr_required` |

**Honest text status per page/sheet/image:** `extracted` · `no_text` (scanned
PDF — future OCR) · `ocr_required` (images) · `failed`. Scanned PDFs are never
pretended to have text.

**New endpoints:**

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/documents/{id}/process` | Run extraction (409 if already processing) |
| GET | `/api/documents/{id}/processing-status` | Status, extractor info, statistics, errors |
| GET | `/api/documents/{id}/content` | Normalized content: pages/sheets/image metadata with source references |

Normalization is deliberately light (line endings, null chars, space runs,
blank lines) — source content stays traceable: PDF → page, DOCX → section/table,
XLSX/XLS → sheet → row/cell, image → image.

**Security:** uploaded files are treated as untrusted — no formula evaluation,
no macro/script execution, no archive extraction to disk; libraries are used
in safe read-only modes.

## Current Implementation Status

**Done (Step 1 — Foundation):**

- ✅ Repository layout: `frontend/`, `backend/`, `data/`, `docs/`, `scripts/`
- ✅ FastAPI backend with modular structure, `GET /api/health`, CORS, central error handling
- ✅ PostgreSQL foundation: SQLAlchemy engine + sessions, ORM models for the 5 foundation tables, Alembic migration `0001_initial_schema`, DEMO seed script
- ✅ Document ingestion: upload API with defense-in-depth validation (allowlist, MIME policy, magic bytes/OOXML checks, streaming size limit), swappable storage layer (local FS for dev), list/detail/download/delete APIs, functional Documents page UI
- ✅ Deterministic processing pipeline: extractor registry (PyMuPDF / python-docx / openpyxl / xlrd / Pillow), typed extraction with provenance + source references, transactional persistence with idempotent re-processing, processing/status/content APIs, Documents page process button + extracted-content viewer
- ✅ OCR pipeline (RapidOCR/ONNX): scanned-PDF and image OCR with bounding boxes + confidence, per-page native-vs-OCR dispatch for mixed PDFs, low-confidence review flagging, verbatim-text guarantee
- ✅ Validation & data-quality engine: 7 deterministic rule families, PASS/WARNING/ERROR/REVIEW_REQUIRED model, human review queue with workflow states, cross-document conflict detection (both sides preserved, no auto-winner), original values never modified
- ✅ Environment configuration via `.env` / `.env.example` — no secrets in code
- ✅ React + TypeScript + Tailwind app shell: sidebar, header, content area
- ✅ Sidebar navigation for all 10 modules (Dashboard implemented; others placeholders)
- ✅ Reusable UI components + loading / empty / error states
- ✅ Backend tests (config, health, no-hang guarantee, schema integrity) + opt-in PostgreSQL integration suite; frontend typecheck + production build

**Not yet implemented (later steps):**

- ⬜ Document processing (parsing PDF/Excel/DOCX content — upload/storage already done)
- ⬜ Reviewer workflow refinements (richer UI, review metrics)
- ⬜ Validation engine
- ⬜ Knowledge base (vector store — the base relational schema already exists)
- ⬜ RAG pipeline
- ⬜ AI Query (natural-language Q&A)
- ⬜ Report generation
- ⬜ Topic Intelligence (word clouds, topic modelling)
- ⬜ Authentication / RBAC

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the target architecture.

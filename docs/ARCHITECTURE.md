# Architecture

CMPDI AI Reporting Platform — SIH 2026 (SIH26023).
Status: **Step 1 — Foundation.** Everything below marked *future* is planned,
not built yet.

## 1. High-level flow (current)

```markdown
        User (browser)
              ↓
   Frontend — React + TypeScript + Tailwind
   (sidebar / header / content shell, Vite dev server on :5173)
              ↓  HTTP (JSON) — /api/* via Vite proxy in development
   Backend API — FastAPI (uvicorn on :8000)
   (routers → services → models; central error handling)
              ↓  SQLAlchemy (lazy connections)
   Database — PostgreSQL
```

In production the frontend is a static bundle (`frontend/dist`) served by any
web server, calling the backend via `VITE_API_BASE_URL`.

## 1b. Document ingestion flow (Step 3)

```markdown
        Client (Documents page)
              ↓  multipart/form-data
   Upload API  POST /api/documents/upload
              ↓
   Validation (allowlist → MIME policy → magic bytes/OOXML → size limit)
              ↓  streamed chunks (never fully buffered)
   Document Storage (DocumentStorage interface; LocalFileStorage in dev —
   atomic write, UUID key, swap for S3/Azure/MinIO later)
              ↓  storage key only
   documents table (original filename kept as metadata)
              ↓
   Future Processing Pipeline (OCR → extraction → validation — later steps)
```

Service-layer guarantees: rejected uploads never touch disk; if database
registration fails after storage, the stored file is deleted (no orphans);
deletion removes the record first, then the file (DB-first, no dangling
records). `GET .../download` streams the original through the same
abstraction — storage paths never leave the backend.

**Step 3 stores and registers documents only — OCR/content extraction is NOT
part of this step.**

## 1c. Document processing pipeline (Step 4)

```markdown
   Uploaded Document (from Step 3 storage)
         ↓
   Document Type Detection (extension/type via registry)
         ↓
   Processing Job (POST /api/documents/{id}/process — synchronous prototype,
                   service shaped so async workers can replace the route later)
         ↓
   Content Extraction (DocumentExtractor.extract: PDF/DOCX/XLSX/XLS/Image)
         ↓
   Page/Sheet/Section Normalization (light, traceability-preserving)
         ↓
   document_pages rows (one per unit: page | sheet | image) + extractor
   provenance (name, version, extracted_at) + typed structured_metadata
         ↓
   Processing Status (documents.status: uploaded → processing → processed | failed)
         ↓
   Future AI/RAG layer (never inside the extraction layer)
```

Guarantees: honest text statuses (`extracted` / `no_text` / `ocr_required` /
`failed` — scanned PDFs are never faked); source traceability (PDF → page,
DOCX → section/table, sheets → row/cell, image → image); idempotent
re-processing (rows replaced in one transaction with the `processed`
transition); failures committed with the real error message, never swallowed.

**Step 4 creates the deterministic extraction foundation only — no OCR, no AI,
no report generation.**

## 2. Backend layering

```
app/
├── main.py        # app factory, middleware (CORS), router registration
├── config.py      # typed Settings from environment variables (.env)
├── db.py          # SQLAlchemy engine + session factory + health probe
├── exceptions.py  # AppError + consistent JSON error responses
├── api/routes/    # thin HTTP routers (currently: health)
├── schemas/       # Pydantic request/response models
├── services/      # business logic — independent of HTTP        (future)
├── models/        # SQLAlchemy models: documents, document_pages,
│                  #   extracted_records, validation_results, audit_logs
├── alembic/       # schema migrations — the source of truth for the DB schema
├── services/      # document_service (upload/list/detail/delete),
│                  #   document_storage (DocumentStorage interface + LocalFileStorage),
│                  #   processing_service (transactional extraction pipeline)
├── processing/    # extractor base + registry + normalization (no AI/OCR ever)
│   └── extractors/   # pymupdf | python-docx | openpyxl | xlrd | pillow
└── utils/         # file_validation (allowlist, MIME policy, signatures)
```

Request flow: `router → service → model/session`, with responses serialised
through Pydantic schemas. Routers never touch the database directly.

## 3. Frontend structure

```
src/
├── components/layout/  # AppLayout, Sidebar, Header, navigation config
├── components/ui/      # StateBlock (loading/empty/error), PageHeader, Icon
├── hooks/              # useHealth — data fetching with loading/error/refetch
├── lib/                # api client (typed fetch), env helpers
├── pages/              # DashboardPage (live) + PlaceholderPage (modules)
└── types/              # shared TS types
```

All ten navigation modules exist as routes; only **Dashboard** renders live
data in Step 1 — the rest show a consistent placeholder with the
loading/empty/error states reused throughout.

## 4. Configuration & secrets

- Backend: `backend/app/config.py` (pydantic-settings) reads `.env` files and
  process environment variables. Defaults allow booting without a database or
  AI credentials.
- Frontend: only `VITE_*` variables are bundled (`src/lib/env.ts`); no secrets
  belong in the frontend.
- `.env` files are git-ignored; `.env.example` documents every variable.

## 5. Future modules (roadmap)

Each module will be added as a vertical slice (route + service + schema +
tests) without changing the foundation:

| Module               | Purpose                                                      |
| -------------------- | ------------------------------------------------------------ |
| Document Processing  | Upload, store and parse geological/mining reports (PDF, scans, Excel) |
| OCR                  | Text extraction from scanned documents                       |
| Data Extraction      | Structure raw text into geological/mining entities           |
| Validation           | Rule-based checks and anomaly detection on extracted data    |
| Knowledge Base       | Vector store on top of the existing PostgreSQL schema        |
| RAG                  | Retrieval-augmented answering over the knowledge base        |
| AI Query             | Natural-language Q&A over reports and data                   |
| Report Generation    | Standardised technical reports from validated data           |
| Topic Intelligence   | Word clouds and topic modelling across the report corpus     |
| Review Queue         | Human-in-the-loop review workflow                            |
| Audit Logs           | Immutable traceability of all platform actions               |
| Auth & RBAC          | Authentication and role-based access control                 |

Nothing in the current foundation hardcodes AI providers — `LLM_PROVIDER` /
`LLM_API_KEY` are reserved configuration, and the platform starts and runs
without them.

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
pip install -r requirements.txt -c constraints.txt
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

## Docker (optional, Step 16)

A minimal reproducible container setup is provided and statically validated
(YAML parse, service topology, secret-safety) — **not runtime-verified in
this environment (Docker unavailable locally)**:

```bash
# 1. configure: copy .env.example to .env and set DB_PASSWORD (+ optional LLM_*).
# 2. build & run postgres + backend (migrations run at startup) + frontend:
docker compose up --build
docker compose down              # data persists in the postgres_data volume
```

Services: `postgres` (16-alpine, healthcheck), `backend` (non-root, runs
`alembic upgrade head` before uvicorn), `frontend` (nginx serving the built
SPA with a same-origin `/api` proxy). No Redis/queues — the app does not use
them. Secrets arrive ONLY via the git-ignored `.env` (compose
interpolation); nothing is baked into images. The `.dockerignore` keeps
`.env`, `.git`, venvs, `node_modules` and uploaded storage out of build
contexts.

## Production Deployment Validation & SIH Demo Environment (Step 17)

Step 17 validates the Step 16 deployment configuration and packages the SIH
demo, using an explicit verification vocabulary applied everywhere
(README, runbook, tests):

- **RUNTIME VERIFIED** — actually executed in this environment.
- **STATICALLY VERIFIED** — enforced by `backend/tests/test_deployment_static.py` (20 DB-free tests), not executed as a container/DB runtime.
- **NOT AVAILABLE IN CURRENT ENVIRONMENT** — requires Docker/PostgreSQL; exact commands are documented, nothing is faked.

**Runtime availability matrix:** Docker, Docker Compose and PostgreSQL
(`psql`, `pg_isready`) are **NOT AVAILABLE**; Python 3.14 (project venv),
Node 24/npm, and the locally cached FastEmbed model `BAAI/bge-small-en-v1.5`
(384-dim; timed embed ~1.06 s) are **RUNTIME VERIFIED — AVAILABLE**, so
semantic search is offline-capable after the one-time model cache.

**Statically verified (new tests):** backend Dockerfile shape (slim base,
constraint-pinned install, code-only COPY, non-root `appuser`,
`alembic upgrade head` before uvicorn, no secrets/`.env` in instructions);
frontend two-stage lockfile build; `.dockerignore` excluding env/venv/
storage/caches; nginx SPA fallback + same-origin `/api` proxy with a 30 MB
upload ceiling; compose topology (backend gated on a *healthy* postgres,
persistent named volumes, minimal documented port surface, no Redis/queues,
secrets via interpolation only); frontend browser-safe env usage
(`VITE_API_BASE_URL` same-origin default) and real demo-flow routes; demo
seed/reset safety (DEMO_-labelled data only, reset scoped to demo rows);
migration-chain + DDL-parity regression.

**Runtime-verified (DB-free):** `/api/health` and `/api/dashboard/statuses`
stay honest under a database outage — HTTP 200 with `connected:false` /
`UNAVAILABLE` / `data_available:false`, never fake health or fabricated
zeroes — across LLM/embedding/retrieval availability states. Docker image
builds, `alembic upgrade head` on live PostgreSQL, demo seed execution and
the seeded end-to-end walkthrough are **NOT VERIFIED** here; the exact
commands are in the runbook.

**📘 Demo runbook: [`docs/SIH_DEMO_RUNBOOK.md`](docs/SIH_DEMO_RUNBOOK.md)** —
prerequisites, seeding, the 10-screen demo flow, "what to say" (USP), and
honest failure recovery.

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
| `LLM_PROVIDER`  | backend   | No                 | `openai-compatible` enables AI Query / AI narrative / AI summary (empty = honest unavailable states) |
| `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` / `LLM_TIMEOUT_SECONDS` | backend | No | Provider credentials/config — set in your local `.env` only, never committed |
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

## Semantic Search & Embeddings (Step 9)

Step 9 adds a **semantic retrieval foundation** on top of Step 8's lexical
search — it does **NOT** generate AI answers, has **no LLM, no RAG, no
chatbot**, and introduces **no cloud calls and no API keys**. The Step 8
retrieval layer stays untouched in behavior; semantic retrieval only extends it.

**Embedding provider (pluggable):** `app/embeddings/` defines an
`EmbeddingProvider` interface (`embed_batch`, `is_available`, name/model/
dimensions metadata) with a local, offline **fastembed (ONNX)** implementation
running **BAAI/bge-small-en-v1.5** (384 dimensions, unit-normalized) entirely
in-process. Providers are swappable without touching search/business logic;
the provider is injected in tests. Nothing is ever downloaded at request time,
and **no random or fake vectors are ever produced** — if the model is
unavailable, rows are marked explicitly `unavailable`/`failed` with the reason.

**Vector storage:** embeddings live on the existing `knowledge_index` rows
(migration `0006_semantic_embeddings`, fully reversible) as **JSONB float
arrays** — `embedding`, `embedding_provider`, `embedding_model`,
`embedding_dimensions`, `embedding_status` (none/pending/embedded/failed/
unavailable, indexed), `embedding_error`, `embedded_at`. No duplicate source
tables; provenance columns are reused as-is. PostgreSQL + **pgvector** is an
optional future optimization — the schema is designed to migrate cleanly when
it is available (pgvector was **not** installed or runtime-verified in this
environment).

**What gets embedded:** only useful retrieval units — pages (OCR text stays
verbatim; confidence is never altered) and structured records whose input is
contextualized (`entity | metric | value unit | period | validation status` —
never a bare number like `1200`), plus validation/conflict messages. `value_raw`
and all source data remain untouched; embeddings are derived, non-authoritative
additions.

**Search modes:** `GET /api/search?q=...&mode=lexical|semantic|hybrid`.
Omitted mode = exact Step 8 lexical behavior (backward compatible). Unsupported
mode → 422; semantic/hybrid without `q` → 422; semantic without a working
provider → **503 `semantic_unavailable`** (honest, no fake results). Hybrid:
lexical ∪ semantic candidates (semantic window capped at 100), merged
deterministically with a **fully explicit formula** —
`relevance = 0.6 · min-max-normalized lexical + 0.4 · ((1 + cosine) / 2)` —
with lexical and semantic scores still exposed separately. Scores are
**retrieval/relevance metrics, never truth/correctness/trust**; the API states
this in `retrieval_note`. Conflicts keep both sides visible in every mode.

**Lifecycle & safeguards:** processing runs `embed_document` **after** the
authoritative commit — best-effort, never fails document processing; lexical
data is always preserved. Reprocessing replaces rows (stale embeddings reset
to `none`, re-embed is idempotent); deletion cascades. `POST
/api/search/embed/{document_id}` re-embeds on demand. Guardrails: max input
4,000 chars, batch ≤ 32, ≤ 500 units/document, per-batch timeout (120 s),
bounded pagination.

**Frontend:** Knowledge Search gains a **Lexical / Semantic / Hybrid** mode
selector and score chips explicitly labeled *retrieval metrics, not trust*;
semantic unavailability is surfaced honestly (with the lexical fallback reason
in hybrid mode).

## End-to-End Workflow & Demo Readiness (Step 15)

Step 15 hardens the canonical platform workflow and verifies the modules connect: **upload → processing → extraction/OCR → structured records → validation → knowledge index → search (lexical/semantic/hybrid) → AI Query with evidence → topic intelligence → analytics → report generation → audit trail.** Lifecycle honesty is enforced end-to-end: a document never reads as processed when extraction failed, validated when validation did not run, or searchable when indexing failed — failures surface in status, validation rollups and the dashboard.

**Provenance chain** (verified across layers): report/AI answer → structured record (`record_id`, `value_raw` verbatim, `normalized_value`) → page/section/sheet (`page_id`, `source_reference`, extraction method, OCR confidence) → original document (`document_id`). Conflicts preserve both sources everywhere — never a winner.

**AI Query states** (all verified): valid evidence → cited answer; no evidence → `insufficient_evidence` (LLM never invoked); conflicting evidence → both sources preserved + REVIEW REQUIRED; LLM unavailable/error/malformed → honest status with evidence still returned; document text is untrusted (delimiters neutralized, system rules unreachable).

**Demo fixtures:** `python scripts/seed_demo_data.py` seeds a small, clearly-labeled DEMO dataset (all identifiers/values `DEMO_`-prefixed, `source="demo_seed"`, isolated `demo/` storage reference, `--reset` to remove). **Demo data is NOT real CMPDI/CIL data and must never be presented as such.** The fixture is aligned with the current schema (including Step 6 validation fields and Step 8 indexing so seeded documents are searchable).

**Known limitations (unchanged):** PostgreSQL not installed in this environment — DB-dependent E2E tests skip honestly (`backend/tests/test_e2e_workflow.py` verifies the full workflow when a database is configured via `CMPDI_TEST_DATABASE_URL`); no authentication/RBAC; DOCX only (no PDF output — never attempted); LLM optional (platform fully functional without one; AI outputs always labeled).

## Production Dashboard (Step 14)

Step 14 replaces the Step 1 placeholder with an **operations dashboard**: a read-only entry point that composes the whole platform — it implements nothing new, it links everywhere.

**`GET /api/dashboard/summary`** aggregates live source-of-truth counts only: documents by lifecycle status, structured records by validation status, validation results (PASS/WARNING/ERROR/REVIEW REQUIRED), knowledge-index units with embedding coverage, recent documents (metadata only — no paths/contents), recent audit activity, and Step 13 intelligence availability (topic count + top terms from the existing deterministic engine). `GET /api/dashboard/statuses` offers a lightweight status-only poll. Statuses are honest — `CONNECTED` / `OPERATIONAL` / `DEGRADED` / `NOT CONFIGURED` / `UNAVAILABLE` — an unavailable dependency is never shown healthy. **When PostgreSQL is unreachable the summary is still HTTP 200 with `data_available=false` and metric sections absent: the UI shows "Database unavailable — no live data", never fabricated zeroes** (true "0 documents" and "cannot query" are explicitly distinguishable). One `dashboard.summary` audit row with counts only.

**Frontend:** the Dashboard page renders system-health tiles, key metric tiles (linked to their modules), documents/processing, validation & review (with a clear path to the review queue and the no-winner conflict note), knowledge & intelligence (with top topics), reports & analytics entry points (Report Generator/Analytics, Knowledge Search, AI Query, Topic Intelligence, Validation, Documents, Data Explorer), recent documents table and recent activity. Dashboard remains the landing page; no new UI framework; authentication is still NOT implemented — documented as a limitation, not simulated.

## Document & Topic Intelligence (Step 13)

Step 13 adds deterministic document/topic intelligence derived from the EXISTING knowledge index — no new source of truth, no re-reading of binary files, no topic-modeling framework. Everything is rebuildable and every term traces back to document/page/source references.

**`app/intelligence/`** builds a bounded corpus from indexed content (documented limits: ≤ 50 documents, ≤ 120 units/document, ≤ 4,000 chars/unit, ≤ 600 units / 240k chars per corpus; truncation is flagged, never silent), then: **keywords & phrases** — safe tokenization, configurable stopwords, bare numbers excluded, content-only 2–3-gram phrases, deterministic TF-IDF ranking with an explained `score_reason` ("frequency N × smoothed idf(D of T docs)"); **topics** — co-occurrence clustering of ranked terms (Jaccard unit overlap ≥ 0.3), labels derived from the underlying terms ("Production / Output") and explicitly NOT official CMPDI/CIL topic definitions; **word-cloud DATA** (normalized 0..1 weights, frontend renders — no backend images); **topic ↔ document relationships** with scores, supporting terms and sources; **deterministic document summaries** (metadata, page/record counts, validation/review counts, key terms, top topics, key metrics via the Step 11 data engine).

**APIs:** `GET /api/intelligence/documents/{id}` (+ `/keywords`, `/topics`, `/word-cloud`), `POST /api/intelligence/corpus/analyze`, `POST /api/intelligence/documents/{id}/summarize`. Honest errors: 404 `document_not_found` / `no_indexed_content`, 503 `database_unavailable`. The **optional AI prose summary** (`include_ai_summary`) uses the Step 10 provider with a closed, delimiter-neutralized evidence context and strict JSON contract — states `ok` (labeled AI-GENERATED — VERIFY) / `unavailable` / `failed` / `insufficient_evidence`; the deterministic summary is always present and authoritative.

**Frontend:** the Topic Intelligence page (scope selector, summary panel, word cloud, topic cards, relationships, keyword table) with one-click "search this term" deep-links into the EXISTING Knowledge Search (`/knowledge?q=…`) — no second search engine. Audit rows (`intelligence.analyze`, `intelligence.summarize`) carry counts only.

## Report Intelligence & Visualization (Step 12)

Step 12 extends the Step 11 report foundation with a deterministic analytical layer — KPIs, trends, comparisons, distributions, insights and frontend-friendly **chart DATA specifications** — plus an optional, strictly-grounded AI narrative. The deterministic engine remains authoritative; nothing replaces Step 11 and no new source of truth is introduced.

**`POST /api/reports/analyze`** returns the full analytical payload for a report selection. **Deterministic / verified:** KPIs are computed per (metric, unit, period) — never summed across periods — from validated, non-conflicting normalized values only. Excluded values (conflicts, validation flags, non-numeric normalized values, disagreeing duplicates) keep their raw form with an explicit reason; unsafe conversion never happens silently. Trends report ordered periods, absolute/percentage change (omitted for zero bases) and explicit `missing_periods` gaps — never interpolated. Comparisons state numerical differences within one unit only, with no "better/worse" labels. **Conflicts propagate:** conflicted keys produce `REVIEW_REQUIRED` — no fake averages, no winners, no definitive trends; conflicted entities appear as visible `null` gaps in comparisons and charts.

**Insights are descriptive only** ("production increased from X to Y between P1 and P2") — no causal claims, no speculation. **Chart specifications** (`line` / `bar` / `comparison`) carry type, axes, unit, series, source record ids and validation/conflict status; the backend renders no images (no visualization dependency was added) — the frontend Report Generator page draws inline SVG with explicit gap rendering and VERIFIED / REVIEW REQUIRED badges.

**Optional AI narrative (labeled):** with `include_narrative` (or `include_narrative: true`), the Step 10 LLM abstraction may draft a narrative from the deterministic analytical payload only — closed context, no retrieval, forbidden from inventing numbers/dates/causes, strict JSON contract. States: `ok` (labeled AI-GENERATED — VERIFY), `unavailable` / `failed` (reason preserved) — always falling back to the deterministic template narrative. Report generation never fails because the LLM is absent. Audit rows (`report.generate`, `report.analyze`) stay metadata-only.

## Automated Report Generation (Step 11)

Step 11 adds the deterministic, provenance-grounded report foundation: `POST /api/reports/generate` produces a **DOCX** report from validated structured records already stored by the platform. **No LLM is involved anywhere** in the pipeline and there is no code path that can invent a value — every figure originates from `extracted_records` (Step 7) and is rendered with its full provenance.

**Pipeline (`app/reports/`):** typed, bounded `ReportSpecification` (title, report type, period, document/entity/metric selections, requested sections, filters, output format — fingerprinted, extensible) → read-only data engine over the Step 7 source-of-truth tables (deterministic ordering, ≤ 500 records, document/entity/metric/period/status/method filters) → deterministic conflict detection (same entity/metric/period/unit with different raw values ⇒ `REVIEW REQUIRED`, **both values kept with their sources, never a winner**) → deterministic sections (Executive Summary template, Key Figures table, Detailed Data, Validation/Review Notes, Sources/Evidence) → DOCX rendering via python-docx (clean headings/tables, byte-deterministic via canonical zip timestamps).

**Data integrity guarantees:** raw values pass through verbatim (never "corrected"); missing values render an explicit `DATA MISSING` marker — never estimated; conflicting values are never silently resolved; source documents and structured records are never modified; oversized selections are truncated honestly and marked partial.

**API:** `POST /api/reports/generate` returns the `.docx` as a download attachment (metadata in `X-Report-*` headers) or JSON metadata with `output_format: "json"`. Audit row `report.generate` stores metadata only (counts, status, fingerprint) — never values or document contents.

**Current limitations:** artifacts are generated in-memory and **not persisted** (no report storage model yet — regenerate to reproduce; the fingerprint identifies the content); DOCX is the only output format (no verified PDF mechanism exists — none is attempted); no charts yet; no authentication. **Prototype/demo output — not an official CMPDI/CIL report and carries no certification.**

## AI Query — Retrieval-Grounded Q&A (Step 10)

Step 10 adds the first AI answer layer: `POST /api/ai/query` answers natural-language questions **only** from evidence retrieved out of the Step 8/9 knowledge index. The LLM never searches the database, never answers without evidence, and never resolves conflicts.

**Pluggable LLM provider (`app/llm/`):** `LLMProvider` interface with an OpenAI-compatible HTTP implementation (urllib, bearer key from the environment only — never logged, errors sanitized) and a clearly-labeled deterministic `[MOCK LLM]` provider for tests/demos. Configured via `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS` (see `.env.example`). No provider configured ⇒ honest `503 llm_unavailable`; the platform runs fully without one.

**Grounding pipeline (`app/ai/`):** question validation (≤ 500 chars) → retrieval-first (hybrid default; semantic-only mode rejected for AI queries) → bounded evidence (≤ 12 units, ≤ 8,000 chars) with full provenance (document/page/record ids, source reference, extraction method, validation status, OCR confidence) → strict structured prompt (fixed code-owned system rules; untrusted question/evidence confined to delimited user-message blocks with delimiter-neutralization, so prompt injection cannot forge block boundaries) → one bounded completion → strict JSON response contract (`answer`/`evidence_ids`/`conflict_detected`/`insufficient_evidence`/`limitations`) with invalid citations dropped.

**Conflicts:** deterministic application-level detection (same entity/metric/period, different raw values) always surfaces — the model can never hide conflicts and never picks a winner. No evidence ⇒ `insufficient_evidence` with the LLM never invoked. Audit logging (`ai.query`) stores metadata only (status, mode, evidence count, provider/model, latency).

**Prototype/demo notice:** Step 10 is an evaluation foundation, not an official reporting authority — every answer carries grounding/verification caveats and cites its evidence ids.

## Knowledge Base & Retrieval (Step 8)

**The Knowledge Base is the retrieval/index layer — it is NOT a source of
truth, NOT RAG, and contains no LLM.** Source tables (documents,
document_pages, extracted_records, validation_results) remain authoritative;
every index entry points back to them.

**Retrieval units:** document pages (incl. OCR pages with confidence) ·
structured records (raw + normalized value, entity, metric, period,
validation status) · validation results (incl. conflicts — both sides stay
searchable, no winner is ever selected).

**Search:** `GET /api/search?q=...` — keyword search, `"exact phrase"` search,
plus exact filters (document, entity, metric, reporting period, extraction
method, validation status) with `limit`/`offset` pagination (max 100).
`GET /api/search/stats` exposes factual index statistics (documents/pages/
records/validations indexed, last update).

**PostgreSQL-native:** entries carry a `tsvector` (`search_vector`, GIN-indexed,
built with `to_tsvector('english', …)`) maintained by the indexing service.
Deterministic ranking = documented arithmetic (phrase match > all keywords >
entity/metric prefix > title hits > unit-type tie-break) — a higher score
means *likely relevant*, never *factually correct*.

**Index lifecycle (idempotent):** processing refreshes the document's entries
in the same transaction as records/validation (delete-replace); document
deletion cascades to the index (no orphaned search entries); explicit
`index_document` / `remove_document` / `reindex_all` operations in
`knowledge_service`.

**Frontend:** new **Knowledge Search** page — search box, filters, factual
index statistics, and provenance-rich results (document, page, source
reference, raw→normalized values, validation status, OCR confidence, score).
The Data Explorer links to it.

> ⚠️ No LLM, no embeddings, no vector database, no answer generation —
> those are future steps that will consume this retrieval foundation.

## Structured Data Layer & Automatic Validation (Step 7)

Processing now runs the complete derived-data workflow in one transaction:

```
Upload → Process/Extract → OCR when required → Structured records
       → Automatic validation → Validated / Warning / Failed / Review Required
```

**Raw ≠ derived — both are always kept.** `document_pages` holds the raw
extracted/OCR text; `extracted_records` holds the structured layer with
verbatim `value_raw` alongside a `normalized_value` that exists **only when
the normalization is unambiguous**. `"1O5"` is stored as `"1O5"` with
`normalized_value = NULL` — never silently converted to `105`.

**Safe normalization (deterministic only):** whitespace/Unicode NFC, canonical
number forms ("1,200" → "1200"), unambiguous dates → ISO-8601, verbatim
financial-year labels ("2025-26"). No semantic guessing, no fuzzy matching,
no OCR auto-correction, no inferred values.

**Provenance per record:** document, page, source reference, extraction
method (`native_text | ocr | table | spreadsheet | docx`), confidence,
review flag, extractor/metadata JSONB.

**Automatic validation:** after structured records are created, the Step 6
engine runs automatically (same engine — no second implementation). The
outcome is written to `documents.validation_status` (`pass | warning | error |
review_required`) so problems stay visible on the document itself — e.g.
processing succeeds while low OCR confidence keeps `validation_status =
review_required`.

**Idempotent re-processing:** pages, records and validation results are each
replaced atomically on every run — 10 records stay 10 records however many
times you reprocess. Original uploaded files are never modified or deleted.

**APIs:** `POST /api/documents/{id}/process` now returns the combined state
(records count + validation summary). New: `GET /api/records` — cross-document
structured records with exact-match filters (entity, metric, reporting period,
extraction method, validation status), the foundation for future knowledge-base
and reporting layers (exact matching only; no fuzzy entity resolution).

**Frontend:** new **Data Explorer** page (raw vs normalized value side by side,
filterable); Documents processing status now shows record count + validation
summary; Dashboard roadmap updated.

> ⚠️ **Demonstration schema:** the field mappings (DEMO_COAL_PRODUCTION etc.),
> column aliases and guardrails in `app/structuring/config.py` are **demo
> defaults — not official CMPDI/CIL field definitions**. Authoritative schemas
> replace them via configuration without engine changes.

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

## SIH Submission & Demo Documentation

Complete SIH26023 submission package (all relative links):

- [`docs/SIH_PS_ALIGNMENT.md`](docs/SIH_PS_ALIGNMENT.md) — implementation mapped against the problem statement (IMPLEMENTED / PARTIALLY / FUTURE / NOT VERIFIED)
- [`docs/SIH_OBJECTIVES_MATRIX.md`](docs/SIH_OBJECTIVES_MATRIX.md) — objectives → features → implementation → demo screen → tests
- [`docs/SIH_FINAL_PRESENTATION_OUTLINE.md`](docs/SIH_FINAL_PRESENTATION_OUTLINE.md) — 12-slide, 10–12 minute presentation structure
- [`docs/SIH_FINAL_DEMO_SCRIPT.md`](docs/SIH_FINAL_DEMO_SCRIPT.md) — 5-minute judge walkthrough + 20-question Q&A
- [`docs/SIH_DEMO_SCREEN_MAP.md`](docs/SIH_DEMO_SCREEN_MAP.md) — timed screen-by-screen demo map (live routes only)
- [`docs/SIH_JUDGE_EVIDENCE_CHECKLIST.md`](docs/SIH_JUDGE_EVIDENCE_CHECKLIST.md) — what can be proven live, and where
- [`docs/SIH_DEMO_FAILURE_CHECKLIST.md`](docs/SIH_DEMO_FAILURE_CHECKLIST.md) — mid-demo recovery playbook
- [`docs/SIH_TECHNICAL_CHEAT_SHEET.md`](docs/SIH_TECHNICAL_CHEAT_SHEET.md) — verified stack versions + subsystem one-liners
- [`docs/SIH_IMPLEMENTED_VS_FUTURE.md`](docs/SIH_IMPLEMENTED_VS_FUTURE.md) — capability matrix with code evidence
- [`docs/SIH_90_SECOND_PITCH.md`](docs/SIH_90_SECOND_PITCH.md) — 90-second pitch + 30-second elevator version
- [`docs/SIH_VALUE_PROPOSITION.md`](docs/SIH_VALUE_PROPOSITION.md) — problem → solution → user impact
- [`docs/SIH_TECHNICAL_NOVELTY.md`](docs/SIH_TECHNICAL_NOVELTY.md) — system-level differentiators (libraries ≠ innovation)
- [`docs/SIH_FINAL_STORY.md`](docs/SIH_FINAL_STORY.md) — the complete narrative, presentation-ready
- [`docs/SIH_DEMO_RUNBOOK.md`](docs/SIH_DEMO_RUNBOOK.md) — environment setup, seeding, health checks
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — target architecture and layering

## Current Implementation Status

**Done (Step 1 — Foundation):**

- ✅ Repository layout: `frontend/`, `backend/`, `data/`, `docs/`, `scripts/`
- ✅ FastAPI backend with modular structure, `GET /api/health`, CORS, central error handling
- ✅ PostgreSQL foundation: SQLAlchemy engine + sessions, ORM models for the 5 foundation tables, Alembic migration `0001_initial_schema`, DEMO seed script
- ✅ Document ingestion: upload API with defense-in-depth validation (allowlist, MIME policy, magic bytes/OOXML checks, streaming size limit), swappable storage layer (local FS for dev), list/detail/download/delete APIs, functional Documents page UI
- ✅ Deterministic processing pipeline: extractor registry (PyMuPDF / python-docx / openpyxl / xlrd / Pillow), typed extraction with provenance + source references, transactional persistence with idempotent re-processing, processing/status/content APIs, Documents page process button + extracted-content viewer
- ✅ OCR pipeline (RapidOCR/ONNX): scanned-PDF and image OCR with bounding boxes + confidence, per-page native-vs-OCR dispatch for mixed PDFs, low-confidence review flagging, verbatim-text guarantee
- ✅ Validation & data-quality engine: 7 deterministic rule families, PASS/WARNING/ERROR/REVIEW_REQUIRED model, human review queue with workflow states, cross-document conflict detection (both sides preserved, no auto-winner), original values never modified
- ✅ Structured data layer + automatic validation: processing → records → validation in one idempotent transaction, verbatim raw values alongside safe normalizations, per-record extraction method/provenance, Data Explorer over cross-document records
- ✅ Knowledge base & retrieval: idempotent `knowledge_index` (tsvector + GIN) over pages/records/validations, deterministic keyword/phrase search with full provenance and documented ranking, conflict-aware results, auto-refresh on processing, cascade cleanup on deletion, Knowledge Search page
- ✅ Semantic search & embedding foundation: pluggable local embedding provider (fastembed ONNX, BAAI/bge-small-en-v1.5, 384-d), JSONB embeddings on `knowledge_index` (migration `0006`), `mode=lexical|semantic|hybrid` retrieval with explicit hybrid scoring, provenance and conflict preservation, best-effort post-commit embedding lifecycle, bounded-input safeguards, honest unavailable/failed states (no fake vectors; pgvector optional later)
- ✅ End-to-end workflow & demo readiness (Step 15): canonical workflow verified upload→…→audit trail, provenance chain continuity, AI state honesty (insufficient/unavailable/error/injection-safe), demo fixture aligned with current schema, AI Query page grounding the last placeholder route, DB-free hardening tests + DB-dependent E2E test
- ✅ Production deployment validation & SIH demo environment (Step 17): static Docker/compose/nginx/frontend validation as executable tests, runtime-verified health/status honesty under outages, demo seed/reset safety checks, runtime availability matrix (Docker/PostgreSQL NOT AVAILABLE — documented, never faked), and the SIH demo runbook (`docs/SIH_DEMO_RUNBOOK.md`)
- ✅ Production dashboard (Step 14): read-only `GET /api/dashboard/summary` + `/statuses` — honest health statuses (CONNECTED/OPERATIONAL/DEGRADED/NOT CONFIGURED/UNAVAILABLE), live source-of-truth metrics, metadata-only recents, intelligence availability, module entry points, offline state that never fabricates zeroes
- ✅ Document & topic intelligence foundation (Step 13): bounded knowledge-index corpus, deterministic TF-IDF keywords/phrases, co-occurrence topics with derived labels, word-cloud data, topic↔document relationships, deterministic summaries + optional labeled AI summary, intelligence APIs and Topic Intelligence page with search deep-links
- ✅ Report intelligence & visualization foundation (Step 12): deterministic KPI/trend/comparison/distribution engines with conflict-aware exclusions, descriptive-only insights, frontend-friendly chart DATA specs, Report Generator page (KPI cards, SVG charts, conflict indicators), optional labeled AI narrative with deterministic fallback, `POST /api/reports/analyze`
- ✅ Automated report generation foundation (Step 11): deterministic provenance-grounded DOCX via `POST /api/reports/generate` — typed bounded specification, read-only data engine over structured records, conflict groups with both sides preserved (REVIEW REQUIRED, no winner), explicit missing-data markers, deterministic sections + byte-stable artifact, metadata-only audit; no LLM, no fabrication
- ✅ AI query foundation (Step 10): retrieval-grounded Q&A `POST /api/ai/query` — pluggable LLM provider (OpenAI-compatible / labeled mock), bounded provenance-complete evidence, strict JSON contract, deterministic conflict surfacing, honest insufficient-evidence/unavailable states, prompt-injection resistance, metadata-only audit
- ✅ Environment configuration via `.env` / `.env.example` — no secrets in code
- ✅ React + TypeScript + Tailwind app shell: sidebar, header, content area
- ✅ Sidebar navigation for all 10 modules (Dashboard implemented; others placeholders)
- ✅ Reusable UI components + loading / empty / error states
- ✅ Backend tests (config, health, no-hang guarantee, schema integrity) + opt-in PostgreSQL integration suite; frontend typecheck + production build

**Not yet implemented (later steps):**

- ⬜ Document processing (parsing PDF/Excel/DOCX content — upload/storage already done)
- ⬜ Reviewer workflow refinements (richer UI, review metrics)
- ⬜ Authoritative field schema (demo structuring config is in place and swappable)
- ⬜ Vector store optimization (pgvector) — JSONB embeddings on `knowledge_index` already exist as of Step 9
- ⬜ Richer RAG (conversation memory, re-ranking, page-level chunking) — retrieval-grounded Q&A already exists as of Step 10
- ⬜ Report artifact persistence + download history — in-memory DOCX generation already exists as of Step 11
- ⬜ DOCX-embedded chart images and CMPDI/CIL template pack — chart DATA specs + frontend SVG visualization exist as of Step 12
- ⬜ Topic modelling upgrades (LDA-style, embedding-based clustering) — deterministic keyword/phrase/topic foundation exists as of Step 13
- ⬜ Authentication / RBAC (still open — dashboard and APIs are unauthenticated prototype code; do not expose publicly)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the target architecture
and [`docs/SIH_DEMO_RUNBOOK.md`](docs/SIH_DEMO_RUNBOOK.md) for the SIH demo
environment guide.

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

## 1d. OCR layer (Step 5)

```markdown
   PDF page (scanned, < 8 native chars) or image document
         ↓
   Pillow validation (integrity, dimension + pixel-count guardrails)
         ↓
   OcrEngine.extract(bytes)          ← interface; RapidOcrEngine today,
         ↓                             (rapidocr-onnxruntime 1.2.3 / ONNX 1.30,
         ↓                              lazy singleton, wall-clock timeout)
   OcrResult (verbatim text, mean confidence, bounding boxes,
              review_required = any box < OCR_CONFIDENCE_THRESHOLD)
         ↓
   ExtractedSection (status ocr_extracted / no_text / failed,
                     structured_metadata["ocr"] = engine + boxes + confidences)
         ↓
   document_pages row (document_id → page_number → source reference kept)
```

Native-text PDF pages bypass OCR entirely; mixed PDFs decide **per page**.
OCR text is never auto-corrected — uncertain detections keep their exact
characters and are flagged for human review. Engine failures isolate to the
single page (`failed`) instead of poisoning the document.

## 1e. Validation & data-quality layer (Step 6)

```markdown
   Extracted data (extracted_records) + OCR pages (document_pages)
         ↓
   ValueCandidate (verbatim value + provenance, DB-free dataclass)
         ↓
   Validation Engine (fixed rule order ⇒ deterministic outcomes)
   ├─ RequiredFieldRule      REQUIRED_FIELD_MISSING
   ├─ NumericRule            NUMERIC_FORMAT / _NEGATIVE / _INTEGER_EXPECTED
   ├─ RangeRule              RANGE_OUT_OF_BOUNDS (config status)
   ├─ DateRule               DATE_INVALID / DATE_FUTURE
   ├─ OCRConfidenceRule      OCR_LOW_CONFIDENCE / OCR_REVIEW_FLAGGED (Step 5 input)
   ├─ DuplicateRule          DUPLICATE_DETECTED (configured key → WARNING)
   └─ CrossDocumentConsistencyRule  CROSS_DOCUMENT_CONFLICT (both sides kept)
         ↓
   ValidationResult rows (rule_code, status, severity, original_value,
                           expected, details JSONB, review_status)
         ↓
   Human Review Queue (open → in_review → resolved | rejected)
```

Invariants: extracted values are never modified; every result carries
provenance (document, page, record, source reference); conflicts preserve
both sources and never pick a winner; runs are idempotent per document
(results replaced atomically); same input + config ⇒ same results.

## 1f. Structured data + automatic validation (Step 7)

```markdown
   ExtractionResult (pages/sheets/OCR — raw layer, preserved intact)
         ↓
   StructuredRecordBuilder (app/structuring — demo-labeled config)
   ├─ spreadsheet sheets → typed rows (Mine/Value/Unit/Period aliases)
   ├─ DOCX tables       → headers + rows
   ├─ images            → one verbatim OCR record (never numerically interpreted)
   └─ text blocks       → bounded verbatim records
         ↓
   RecordDraft (value_raw verbatim + normalized_value only when unambiguous,
                method, confidence, source reference, metadata)
         ↓
   ONE transaction: replace pages → replace extracted_records →
   load_validation_scope → compute_outcomes → write_outcomes
   (Step 6 engine reused; no commit until everything succeeds)
         ↓
   documents.status = processed AND documents.validation_status =
   pass | warning | error | review_required  (problems stay visible)
```

Raw source ≠ derived structured data: raw text lives in `document_pages`,
structured values in `extracted_records` with `value_raw` verbatim and
`normalized_value` NULL whenever normalization would be a guess. Validation
never modifies source values. Re-processing replaces derived layers
idempotently; original files are never touched.

## 1g. Knowledge base / retrieval layer (Step 8)

```markdown
   SOURCE OF TRUTH (authoritative)
   documents · document_pages · extracted_records · validation_results
         ↓  (index_document — delete-replace, idempotent, same tx as processing)
   RETRIEVAL LAYER
   knowledge_index (unit_type: page | record | validation; tsvector + GIN)
         ↓  (GET /api/search — keyword, "exact phrase", exact filters, pagination)
   Deterministic ranking (phrase > keywords > prefix > unit-type — arithmetic,
   no LLM, no trust score; higher rank ≠ factually correct)
         ↓
   FUTURE: RAG / AI Query consume results WITH provenance (never answers
   without a source)
```

Invariants: the retrieval layer is never authoritative; every result carries
document/page/record/source-reference provenance; conflicting values remain
searchable with both sides visible; reprocessing and deletion leave zero stale
or orphaned entries.

## 1h. Semantic search & embedding layer (Step 9)

```markdown
   SOURCE OF TRUTH (authoritative — unchanged)
   documents · document_pages · extracted_records · validation_results
         ↓  (Step 8: index_document — delete-replace, idempotent)
   knowledge_index  (tsvector + GIN, provenance columns)
         ↓  (Step 9: embed_document — best-effort, strictly AFTER the
              authoritative processing commit; per-row embedding_status:
              none → pending → embedded | failed | unavailable)
   knowledge_index.embedding  (JSONB float array — BAAI/bge-small-en-v1.5,
   384 dims, unit-normalized; provider/model/dimensions stored per row)
         ↓  (GET /api/search?mode=lexical|semantic|hybrid)
   combined retrieval candidates:
     lexical  — Step 8 arithmetic ranking (unchanged)
     semantic — brute cosine similarity over EMBEDDED rows, window ≤ 100
     hybrid   — relevance = 0.6 · min-max(lexical) + 0.4 · ((1+cos)/2)
                (explicit, deterministic; raw scores stay exposed)
```

**Embedding provider abstraction** (`app/embeddings/`): `EmbeddingProvider`
interface (`embed_batch`, `is_available`, name/model/dimensions metadata) with
an offline **fastembed (ONNX)** implementation — no cloud, no API keys, no
downloads at request time. Providers are swapped via `set_embedding_provider`
(tests inject deterministic fakes) without touching search/business logic.
Embedding inputs are deterministic and contextualized (records embed as
`entity | metric | value unit | period | validation status`; pages embed their
verbatim text with OCR confidence preserved separately; validation rows embed
their conflict message). `value_raw` and all source data are never modified.

**Failure behavior is honest by construction:** unavailable provider ⇒ rows
marked `unavailable` with the reason (semantic mode returns **503**,
hybrid falls back to lexical with `semantic_error` attached); provider errors
and timeouts ⇒ `failed`. **No random or fake vectors are ever produced**, and
processing never fails because embeddings are unavailable — lexical data is
always preserved first.

**Provenance invariants (unchanged from Step 8, extended):** every semantic
result keeps document/page/record/validation/source-reference, extraction
method, validation status and OCR confidence; `semantic_similarity` and
`relevance` are labeled retrieval/relevance metrics — never truth, correctness
or trust — and the API says so explicitly (`retrieval_note`). Conflicting
records both remain visible in every mode; similarity never overrides
validation state.

**Performance safeguards:** input ≤ 4,000 chars, batch ≤ 32, ≤ 500 units per
document, per-batch wall-clock timeout (120 s), semantic candidate window ≤
100, bounded pagination (limit ≤ 100). **Vector storage** is JSONB on
`knowledge_index` (migration `0006`, reversible); **pgvector** is an optional
future optimization — PostgreSQL is not installed in the current environment,
so migration `0006` was validated statically (offline SQL generation) and the
PostgreSQL-required integration tests skip honestly.

**Step 9 does NOT generate AI answers** — no RAG, no LLM, no chatbot. The
combined candidate list is the input the future answer layer will consume
*with* provenance.

## 1i. AI query layer (Step 10)

```
   question (≤ 500 chars, untrusted)
         ↓  app/ai/service.py — run_ai_query (fixed order)
   1. validation                → 422 empty/too_long; semantic-only mode → 422
   2. retrieval-first           → knowledge_service (hybrid default;
   │                              LLM never searches anything)
   3. bounded evidence          → app/ai/evidence.py (≤ 12 units, ≤ 8,000 chars,
   │                              full provenance, evidence_id = list position)
   4. deterministic conflicts   → group by (entity, metric, period); BOTH
   │                              sides stay; no winner, ever
   5. structured prompt         → app/llm/prompts.py (code-owned system rules;
   │                              untrusted content only in delimited user blocks,
   │                              delimiter-neutralized)
   6. one bounded completion    → app/llm/service.py (pluggable provider,
   │                              thread-pool timeout, secret-free errors)
   7. strict JSON contract      → parse_llm_response (exact key set, types;
   │                              citations filtered to real evidence ids)
         ↓
   AIQueryResponse (answer + evidence + conflicts + honest status)
```

**Honesty guarantees:** no evidence ⇒ `insufficient_evidence` (LLM never
invoked); no provider/failed provider ⇒ `llm_unavailable` / `llm_error`
(HTTP 503 for unavailability) with the evidence still returned; malformed
responses ⇒ `llm_error` with the reason — **never a fabricated answer**.
Application-level conflict detection always ORs over the model's self-report.
**Security:** API keys stay in configuration (never logged, never returned);
evidence text cannot elevate itself to instructions (delimiters are
neutralized inside untrusted content); audit rows (`ai.query`) carry metadata
only. The mock provider output is permanently labeled `[MOCK LLM]`.

## 1j. Automated report generation layer (Step 11)

```
   validated structured data (extracted_records — source of truth, untouched)
         ↓  POST /api/reports/generate
   ReportSpecification  (typed, bounded, fingerprinted — app/reports/spec.py)
         ↓  app/reports/engine.py — collect_report_data (READ-ONLY)
   filtered selection (documents/entities/metrics/period/status/method,
   deterministic order, ≤ 500 records) + provenance context (docs, pages)
         ↓  _detect_conflicts (deterministic, no winner)
   ConflictItems: (entity, metric, period, unit) with disagreeing raw values
   → BOTH values + sources kept, status REVIEW REQUIRED
         ↓  app/reports/sections.py (deterministic templates, no LLM)
   Executive Summary · Key Figures · Detailed Data ·
   Validation/Review Notes · Sources/Evidence
         ↓  app/reports/docx.py (python-docx, canonical zip = byte-stable)
   DOCX artifact (in-memory) + audit row report.generate (metadata only)
```

**Integrity guarantees (enforced by construction):** values only come from
stored records (`value_raw` verbatim, `normalized_value` alongside);
missing data renders `DATA MISSING` — never estimated; conflicts are never
silently resolved; source documents/records are never modified; oversized
selections truncate deterministically and are marked partial; units are part
of the conflict key (no cross-unit conversion guessing).

**Limitations:** no artifact persistence (regenerate to reproduce — the
fingerprint identifies content); DOCX only (no verified PDF mechanism, none
attempted); no charts; no auth. Prototype/demo output — not an official
CMPDI/CIL report.

## 1k. Report intelligence & visualization layer (Step 12)

```
   ReportData (Step 11 engine — structured records, conflicts, summary)
         ↓  app/reports/analytics/ (deterministic, no LLM)
   KPIs (per metric+unit+period; validated values only)
   Trends (ordered points, absolute/percent change, explicit missing_periods)
   Comparisons (per-entity difference within one unit; no winner labels)
   Distributions (histograms) · Insights (descriptive only)
   ChartSpecs (line | bar | comparison — DATA only, frontend renders)
         ↓  conflicts propagate: conflicted keys ⇒ REVIEW_REQUIRED,
   │     no aggregates, entities appear as null gaps
   excluded_values: every record kept out of arithmetic, with reason + raw
         ↓  POST /api/reports/analyze          POST /api/reports/generate
   JSON analytical payload                 DOCX (+ optional analytical
   (+ optional labeled AI narrative)       sections & narrative appendix)
```

**Arithmetic rules (enforced by construction):** normalized values only,
finite plain decimals only, validated statuses only (pass/valid), conflicts
excluded with reason, per-cell disagreement excluded (never averaged),
KPIs never summed across periods, percentage change omitted for zero bases,
units never cross-compared. `collect_exclusions` is the single authoritative
derivation of every excluded record.

**AI narrative (optional, Step 10 provider):** closed context (deterministic
payload only), descriptive-only system rules, strict JSON contract
(`narrative`/`summary_points`/`limitations`), states ok/unavailable/failed,
deterministic template fallback — generation never fails because the LLM is
absent; AI output is always labeled and never authoritative.

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
├── processing/    # extractor base + registry + normalization (no AI ever)
│   ├── ocr/          # OcrEngine interface, OcrResult models, RapidOCR engine,
│   │                 #   availability service, OCR pipeline helper
│   └── extractors/   # pymupdf+ocr | python-docx | openpyxl | xlrd | pillow+ocr
├── validation/    # deterministic rule engine (DB-free): config, rules, parsing
│   │                 #   — demo rules labeled, authoritative rules via config
├── structuring/   # StructuredRecordBuilder + safe normalization (Step 7)
│   │                 #   — demo field schema, raw ≠ derived
├── knowledge/     # retrieval units, query parser, deterministic ranking (Step 8)
├── services/      # …, validation_service (runs, review queue, PATCH)
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

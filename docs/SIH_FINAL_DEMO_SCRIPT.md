# SIH Final Demo Script — CMPDI/CIL AI-Powered Geological, Mining & Reporting Solution

**USP:** *"From Unstructured Documents to Verified, Traceable Intelligence."*

> **Synthetic-data notice (read aloud at the start):** "All values shown in
> this demonstration are synthetic demonstration data and do not represent
> official CMPDI/CIL figures."

**Verification vocabulary:** RUNTIME VERIFIED = executed in our environment;
STATICALLY VERIFIED = enforced by tests (`backend/tests/test_deployment_static.py`,
`backend/tests/test_sih_demo_docs.py`); NOT AVAILABLE IN CURRENT ENVIRONMENT =
requires Docker/PostgreSQL here — exact commands are in
[`docs/SIH_DEMO_RUNBOOK.md`](SIH_DEMO_RUNBOOK.md).

---

## The 5-Minute Storyline (deterministic, value-chain order)

```
UNSTRUCTURED DATA → DOCUMENT INGESTION → OCR / EXTRACTION → STRUCTURED DATA
→ VALIDATION → KNOWLEDGE SEARCH → AI QUERY + EVIDENCE → ANALYTICS
→ AUTOMATED REPORT → AUDIT / TRACEABILITY
```

One storyline, ten steps, every transition using the same source of truth.
Do not click randomly: each screen feeds the next.

**Preparation (before judges arrive)** — see the runbook: start PostgreSQL
( demo machine), `alembic upgrade head`, start backend + frontend, run
`python scripts/seed_demo_data.py`, verify `/api/health` shows
`database.connected = true`, and keep the demo document ready for upload.
The seeding itself is NOT AVAILABLE IN CURRENT ENVIRONMENT (needs live
PostgreSQL); its safety is STATICALLY VERIFIED.

---

## Opening — 20 seconds

**Problem:** CMPDI/CIL reporting requires information from scanned PDFs,
documents, spreadsheets, images and historical records. Manual compilation
creates delays, dependency on individual expertise, and higher risk of
errors — and nobody can easily prove where a reported number came from.

**Solution:** *"From Unstructured Documents to Verified, Traceable
Intelligence."* One platform that ingests the documents, extracts the data,
validates it, answers questions **only from that evidence**, and generates
the report — with full provenance.

---

## Step 1 — Dashboard (`/dashboard`) — ~40 seconds

**Show:** document counts by status, record validation rollups, review
items, knowledge-index units with embedding coverage, recent activity
(audit metadata), system-health tiles (database / retrieval / embeddings /
LLM states).

**Say:** "The dashboard gives a single operational view of the reporting
pipeline — every tile is a live count from the source-of-truth tables, and
every status is honest: a dependency that is down is shown as down, never
masked."

## Step 2 — Document (`/documents`) — ~30 seconds

**Show:** upload (or open the seeded) `DEMO_borehole_log.pdf`; processing
and extraction statuses; provenance fields.

**Say:** "Documents are ingested with defense-in-depth validation — type
allowlist, signature checks, size limits — and every downstream value keeps
a link back to this document."

## Step 3 — Extraction (Documents → content viewer) — ~40 seconds

**Show:** native text where available, OCR for scans, page/section
references, extraction method per record, OCR confidence; low-confidence
content flagged `review_required` instead of silently accepted.

**Say:** "Original values are preserved verbatim — normalization happens
alongside, never instead. The system knows *how* and *where* every value
was obtained."

## Step 4 — Validation (`/validation`, includes the Review Queue) — ~50 seconds

**Show:** one valid record, one warning, and the planted conflict between
`DEMO_MINE_A` and `DEMO_MINE_B` values for `DEMO_COAL_PRODUCTION`
(`DEMO_2026-26`): both sides preserved, REVIEW REQUIRED, review workflow
states (pending → in_review → reviewed).

**Say:** "The system does not silently choose between conflicting values.
It flags the conflict, keeps both sources visible, and routes it to a human
reviewer with the full evidence."

## Step 5 — Knowledge Search (`/knowledge`) — ~30 seconds

**Search:** a meaningful term such as `coal production` (mode: hybrid when
embeddings exist; lexical otherwise).

**Show:** ranked results with source reference (document/page/record),
relevance, provenance; conflict-aware presentation.

**Say:** "Everything extracted is indexed — keyword, semantic and hybrid
retrieval over the same knowledge index, always with provenance attached."

## Step 6 — AI Query (`/ai-query`) — ~40 seconds

**Ask:** "What was the reported production value for DEMO_MINE_A during
DEMO_2026-26?" — grounded in the seed data.

**Show:** the answer with evidence unit IDs, source document/page/record
references and validation status; state honesty if no LLM is configured
(`llm_unavailable` with evidence still returned) or evidence is missing
(`insufficient_evidence` — the LLM is never invoked without evidence).

**Say:** "The AI answers from retrieved evidence rather than acting as a
general chatbot. Document text is untrusted input; answers carry their
citations; without evidence it says so."

## Step 7 — Topic Intelligence (`/topic-intelligence`) — ~30 seconds

**Show:** deterministic keywords and phrases (TF-IDF with explained
scores), co-occurrence topics, word-cloud data, topic ↔ document
relationships.

**Say:** "This helps identify recurring subjects across the document
corpus — fully deterministic and rebuildable, every term traceable back to
its sources."

## Step 8 — Analytics (`/data-explorer`) — ~30 seconds

**Show:** KPIs, trends, comparisons and distributions over structured
records; the conflict group excluded from calculations with an explicit
indicator.

**Say:** "Conflicted or invalid values are not silently included in
calculations — exclusions are explicit and visible."

## Step 9 — Report (`/report-generator`) — ~40 seconds

**Generate:** the DOCX report (title, reporting period, tables, sources/
evidence per figure, conflict/review-required section).

**Say:** "The numerical content comes from validated structured records —
the same records you saw validated. Provenance reaches the document, and
conflicts are disclosed rather than resolved away."

## Step 10 — Audit (Dashboard → Recent platform activity) — ~30 seconds

**Show:** the audit trail — upload, processing, validation, search, AI
query, report generation events with timestamps and entity references.

**Say:** "Important actions leave metadata for traceability without storing
sensitive question/answer content — enough to audit the platform, never a
leak surface."

---

## Expected Judge Questions

1. **What is the main innovation?** The closed loop from unstructured
   mining documents to a generated report where *every* number carries
   provenance and passes rule-based validation — evidence-grounded AI plus
   conflict preservation plus automated DOCX reporting in one flow.
2. **Why is AI required?** Semantic retrieval (local embeddings) finds
   relevant content regardless of exact wording, and the LLM composes an
   answer from retrieved evidence with citations. The deterministic
   pipeline (extraction, validation, analytics, reporting) does not need a
   cloud AI.
3. **Why not just use OCR?** OCR produces raw text, not validated data.
   We add structure (entities/metrics/units with provenance), validation
   rules, an indexed knowledge base, and review workflows on top.
4. **How do you handle incorrect OCR?** Every OCR result carries
   confidence; low-confidence content is flagged `review_required` and
   routed to the Review Queue; original values are preserved verbatim for
   human verification.
5. **How do you handle conflicting documents?** Conflicts are detected by
   the rule engine, both values and their sources are preserved, the group
   is marked REVIEW REQUIRED, excluded from analytics with an explicit
   indicator, and disclosed in reports. There is no automatic winner.
6. **Can the AI hallucinate?** It answers only from retrieved evidence with
   a strict JSON contract; without sufficient evidence it returns
   `insufficient_evidence` and the LLM is never invoked; ungrounded
   answers are labeled AI-GENERATED — VERIFY where AI prose is optional
   (reports/summaries). We claim reduced, surfaced risk — not zero risk.
7. **How do you prove where a number came from?** Full provenance chain:
   document → page/section → extracted record (verbatim `value_raw` +
   normalization) → validation results → knowledge-index unit → search
   result/AI evidence → report figure, plus audit metadata for actions.
8. **How is validation performed?** Deterministic rule families (range,
   required-field, format, consistency, cross-record/cross-document
   conflict checks, …) with PASS/WARNING/ERROR/REVIEW_REQUIRED outcomes,
   `original_value` vs `expected_value`, and `source_reference`.
9. **How are historical documents handled?** They are ingested like any
   document (scan or text), extracted, validated, indexed, and made
   searchable — including cross-document conflict detection against newer
   records.
10. **Can this scale to CIL subsidiaries?** The architecture is standard
    and horizontal: PostgreSQL source of truth, rebuildable knowledge
    index, pluggable providers, containerized services. Multi-subsidiary
    tenancy is a future step (see the implemented-vs-future matrix).
11. **Why PostgreSQL?** It is the transactional source of truth with a
    mature migration path (Alembic), full-text search (tsvector + GIN),
    JSONB for embeddings, and an upgrade path to pgvector.
12. **Why hybrid search?** Lexical search is precise for codes/ids;
    semantic search finds paraphrases; hybrid combines both with an
    explicit scoring formula — each mode is selectable and honest about
    unavailability.
13. **Why local embeddings?** Data stays on-premise (no cloud API, no API
    keys), the model (`BAAI/bge-small-en-v1.5`, 384-dim) is cached locally
    and works offline, and the provider is pluggable for future upgrades.
14. **What happens when the LLM is unavailable?** The query returns an
    honest `llm_unavailable` status **with the evidence still included**;
    every deterministic feature (extraction, validation, search,
    analytics, reports) is unaffected. The LLM is optional by design.
15. **What happens when PostgreSQL is unavailable?** `/api/health` reports
    `connected:false`; the dashboard shows `data_available:false` with "no
    demo values are shown" — never fabricated zeroes; statuses map to
    UNAVAILABLE honestly. (Verified in our environment without a DB.)
16. **How is security handled?** Environment-based secrets (none in Git),
    upload allowlist + signature checks + size limits, path-traversal-safe
    storage, non-root backend container, bounded prompts with
    delimiter-neutralized untrusted text, metadata-only audit logs, and
    human review as the final gate. No auth yet — documented limitation,
    not hidden.
17. **How does human review work?** Low-confidence OCR and validation
    flags flow into a Review Queue with workflow states (pending →
    in_review → reviewed), the full evidence attached, and actions
    audited.
18. **How are reports generated?** Deterministically from validated
    structured records via `POST /api/reports/generate` — no LLM in the
    data path, explicit missing-data markers, conflict disclosure,
    byte-stable DOCX with per-figure provenance.
19. **How can this integrate with existing CMPDI/CIL systems?** Standard
    REST APIs, PostgreSQL, document upload/download endpoints, and
    swappable storage/provider layers make integration a configuration
    and adapter exercise rather than a rewrite.
20. **What would be the next production step?** Authentication/RBAC on
    the existing API surface, then a provisioned PostgreSQL deployment
    (migrations already run at container start), pgvector/ANN retrieval,
    background workers, and monitoring — all labeled FUTURE in the matrix.

---

## Architecture Explanation (for judges — one breath per stage)

```
Sources → Ingestion → Extraction/OCR → Normalization → Structured Records
→ Validation → Knowledge Index → Semantic/Hybrid Retrieval
→ Evidence-Grounded AI → Analytics/Intelligence → Reports → Audit
```

| Stage | INPUT | PROCESS | OUTPUT |
| --- | --- | --- | --- |
| Sources | Scanned PDFs, DOCX, XLSX/XLS, images | — | raw files |
| Ingestion | raw files | allowlist + signature + size checks, storage | `documents` rows + storage references |
| Extraction/OCR | documents | PyMuPDF / python-docx / openpyxl / xlrd / Pillow; RapidOCR for scans | `document_pages` (text, method, confidence) |
| Normalization | page text/tables | deterministic parsing, verbatim + normalized values | candidate values |
| Structured Records | candidate values | entity/metric/unit mapping with provenance | `extracted_records` |
| Validation | records | deterministic rule engine | `validation_results` (+ review flags) |
| Knowledge Index | pages, records, validations | tsvector + GIN indexing, optional embeddings | `knowledge_index` units |
| Retrieval | user query | lexical / semantic / hybrid scoring | ranked units with provenance |
| Evidence-Grounded AI | ranked evidence + question | bounded context, strict JSON contract, citation filtering | cited answer or honest status |
| Analytics/Intelligence | validated records, index corpus | KPI/trend/comparison engines, TF-IDF topics | insights (conflicts excluded explicitly) |
| Reports | validated records + spec | deterministic DOCX composition | report artifact with provenance |
| Audit | platform actions | metadata-only logging | `audit_logs` |

---

## USP Validation — four differentiators, real evidence

1. **Unstructured → Structured** — extractor registry (PyMuPDF,
   python-docx, openpyxl, xlrd, Pillow) + RapidOCR pipeline; verbatim
   `value_raw` with safe normalization; per-record extraction method and
   page/section provenance. *Evidence: `app/processing/`, Step 4/7 tests.*
2. **Structured → Validated** — deterministic rule families with
   PASS/WARNING/ERROR/REVIEW_REQUIRED; conflicts keep both sides; Review
   Queue workflow states. *Evidence: `app/validation/`, Step 6 tests.*
3. **Validated → Intelligent** — hybrid retrieval over the knowledge
   index; evidence-grounded AI Query with `insufficient_evidence` /
   `llm_unavailable` honesty; deterministic topic intelligence and
   analytics. *Evidence: `app/services/knowledge_service.py`, `app/ai/`,
   Steps 8–10, 13 tests.*
4. **Intelligent → Traceable** — provenance chain into search results, AI
   citations and report figures; metadata-only audit trail; report
   provenance test. *Evidence: Step 11/15 tests
   (`test_report_provenance_reaches_the_docx`), audit layer.*

No invented metrics — value claims describe the mechanism, not measured
percentages.

---

## Problem → Solution → Impact

| Problem | Solution (implemented) |
| --- | --- |
| Manual document processing | Automated ingestion + extraction/OCR pipeline |
| Manual validation | Rule-based validation engine + Review Queue |
| Slow information retrieval | Lexical + semantic + hybrid retrieval with provenance |
| AI hallucination risk | Evidence-grounded RAG; no evidence → no LLM call |
| Conflicting historical values | Conflict preservation + human review (no auto-winner) |
| Manual report preparation | Validated structured data → automated DOCX report |
| Limited visibility | Dashboard + analytics + topic intelligence |

---

## Failure Demonstration (safe, rehearsed)

Planted conflict: **Source A → 1200** vs **Source B → 1350** for
`DEMO_COAL_PRODUCTION` at `DEMO_MINE_A`/`DEMO_MINE_B` (`DEMO_2026-26`).

Expected behaviour (all deterministic, verified by the Step 6/15 test
suites): both values preserved with their sources → conflict detected by
the cross-document rule → group marked REVIEW REQUIRED → no automatic
winner → AI Query presents both sides with citations (or
`insufficient_evidence` if asked to pick) → analytics excludes the group
with an explicit indicator → report carries the disclosure. Never present
fabricated official figures — the demo values are `DEMO_`-prefixed
synthetic data.

---

## Security Story (for non-security judges)

- **Secrets** live in a git-ignored `.env`; the committed template holds
  placeholders only (test-enforced). No credentials in Git.
- **Uploads** pass an allowlist, file-signature (magic bytes) checks and a
  streaming size limit; storage paths are traversal-safe; uploads live in
  an isolated directory, never in source trees.
- **Containers** run the backend as a non-root user; images are built from
  code-only contexts (`.dockerignore` excludes `.env`, venvs, storage).
- **AI safety** uses bounded prompts/context and neutralizes document
  delimiters so untrusted text cannot impersonate system rules; audit
  logs store metadata (counts, actions, ids) — never document contents or
  Q&A payloads.
- **Human review** is the final gate: flagged content reaches a person
  before it is trusted.

## Scalability Story

**Implemented now:** PostgreSQL as source of truth; rebuildable knowledge
index (tsvector + GIN + JSONB embeddings); pluggable embedding provider;
pluggable LLM provider; FastAPI backend; React frontend; container
deployment with compose topology (health-gated dependencies, persistent
volumes).

**FUTURE — not implemented (labeled, do not claim in the demo):**
PostgreSQL/pgvector with ANN vector retrieval; object storage;
background processing workers; authentication/RBAC; enterprise identity
(SSO) integration; production monitoring/alerting; horizontal scaling of
API workers. See `docs/SIH_IMPLEMENTED_VS_FUTURE.md`.

---

## UI Route Map (demo path — no placeholders in the flow)

| Demo step | Route | Status |
| --- | --- | --- |
| Dashboard / audit activity | `/dashboard` | Live |
| Documents + extraction viewer | `/documents` | Live |
| Validation + Review Queue | `/validation` | Live (review queue embedded) |
| Knowledge Search | `/knowledge` | Live |
| AI Query | `/ai-query` | Live |
| Topic Intelligence | `/topic-intelligence` | Live |
| Analytics / Data Explorer | `/data-explorer` | Live |
| Report Generator | `/report-generator` | Live |
| Audit Logs nav entry | `/audit-logs` | Placeholder — use Dashboard recent activity (do **not** click in the demo) |
| Review Queue nav entry | `/review-queue` | Placeholder — use Validation page |
| Settings | `/settings` | Placeholder — do not click |

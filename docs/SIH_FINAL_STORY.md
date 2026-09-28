# SIH — Final Story

> All examples use synthetic `DEMO_`-labelled data. Nothing here represents
> official CMPDI/CIL figures.

## 1. The Problem

Reporting at CMPDI/CIL means compiling geological, production and
exploration information that lives in scanned PDFs, digital documents,
spreadsheets, images and years of historical records. The output must be
trustworthy: validated, consistent, and traceable to its sources.

## 2. Why Existing Workflow Is Difficult

Compilation is manual — re-typing values, cross-checking from memory,
reconciling documents by opening them side by side. Expertise is locked in
individuals, conflicts surface late (or never), and answering "where did
this number come from?" takes an archaeology project.

## 3. Our Solution

One platform: **"From Unstructured Documents to Verified, Traceable
Intelligence."** Documents go in; a validated, searchable, auditable
knowledge base comes out; the DOCX report is generated from the validated
records — not retyped.

## 4. How the Pipeline Works

Documents → ingestion (signature/size-validated) → extraction/OCR
(per-page native-vs-OCR dispatch) → normalization (verbatim originals +
safe normalized values) → structured records → deterministic validation →
knowledge index → hybrid retrieval → evidence-grounded AI → analytics →
report → audit metadata at every step. One source of truth feeds all of it.

## 5. Where AI Is Used

Three places, deliberately narrow: (1) **semantic retrieval** — local
embeddings (`BAAI/bge-small-en-v1.5`, 384-d, offline-capable) power
semantic and hybrid search; (2) **evidence-grounded answering** — an
optional LLM composes answers from retrieved, validation-aware evidence
with citations; (3) **optional labeled summaries** in reports — always
marked AI-GENERATED — VERIFY. Everything else is deterministic by design.

## 6. How We Prevent Unverified Answers

No evidence → `insufficient_evidence` and the LLM is never invoked.
Unconfigured provider → honest `llm_unavailable` with the evidence still
returned. Document text is untrusted input (delimiters neutralized,
system rules unreachable). Citations are filtered to real knowledge-index
IDs — a model cannot cite what it was not given. AI prose is always
labeled.

## 7. How Conflicts Are Handled

The rule engine detects cross-document conflicts and preserves **both
values and their sources** — REVIEW REQUIRED, never an automatic winner.
Humans resolve through the Review Queue (pending → in_review → reviewed)
with full evidence attached; analytics excludes conflicted groups with an
explicit indicator; reports disclose them.

## 8. How Reports Are Generated

`POST /api/reports/generate` composes the DOCX deterministically from
validated structured records — typed bounded specification, read-only data
engine, per-figure provenance, explicit missing-data markers, byte-stable
output. No LLM in the data path; conflicts are disclosed in the document.

## 9. Why the Solution Can Scale

Standard components with unusual guarantees: PostgreSQL source of truth
(tsvector+GIN, JSONB embeddings, Alembic migrations), FastAPI layered
backend, React frontend, container topology with health-gated services,
rebuildable knowledge index, pluggable providers. Growth levers —
pgvector/ANN retrieval, background workers, auth/RBAC, monitoring — are
architected-for but honestly labeled FUTURE.

## 10. Current Limitations

No authentication (unauthenticated prototype — do not expose publicly);
Docker/PostgreSQL runtime not verifiable in the development environment
(statically verified; commands documented); DOCX-only report output;
synchronous processing; no measured production baseline — quantitative
improvement is not claimed because production baseline measurements are
not yet available.

## 11. Final USP

**"From Unstructured Documents to Verified, Traceable Intelligence."**

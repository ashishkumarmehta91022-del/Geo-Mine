# SIH — Value Proposition

> **Synthetic-data notice:** all examples reference synthetic `DEMO_`-labelled
> data; nothing here represents official CMPDI/CIL figures.

## Current Problem

CMPDI/CIL reporting depends on information locked in scanned PDFs, digital
documents, spreadsheets, images and historical records. Compilation is
manual: values are re-typed, cross-checked by memory, and conflicts between
documents surface late — or never. Nobody can cheaply prove where a
reported number came from.

## Proposed Solution

One platform: **"From Unstructured Documents to Verified, Traceable
Intelligence."** Documents are ingested, extracted (OCR included), turned
into structured records with the original values preserved, validated by
deterministic rules, indexed for search, answered by an evidence-grounded
AI, and compiled into a DOCX report — with every figure traceable.

## What Changes for the User

- **One entry point** instead of folder diving: upload once, everything
  downstream (validation, search, AI, analytics, report) builds on it.
- **Review replaces re-reading:** the Review Queue surfaces only flagged
  items with their evidence, instead of re-checking every page manually.
- **Ask the corpus, not a colleague:** knowledge search and AI Query
  retrieve the relevant passage/record with citations.
- **The report writes itself** from validated records — conflicts are
  disclosed in the document rather than discovered after circulation.

## Why AI Helps

- **Semantic retrieval** (local embeddings) finds relevant content even
  when wording differs — lexical search alone misses paraphrases.
- **Evidence-grounded answers:** the LLM composes an answer *only* from
  retrieved, validated evidence with citations; it is never a free-form
  chatbot over the corpus.
- **Optional by design:** every deterministic feature works without any
  LLM; the AI is an accelerator, not a dependency.

## Why Validation Matters

Extraction alone produces *text*; reporting needs *defensible numbers*.
Deterministic rules check every value, low-confidence OCR is routed to
human review, and original values are preserved verbatim — so quality is
enforced by process, not by hope.

## Why Traceability Matters

Auditors, reviewers and decision-makers must be able to answer "where did
this number come from?" in one step. The provenance chain (document → page
→ record → validation → evidence → report figure) plus metadata-only audit
logs make the entire flow inspectable — this is what turns output into
evidence.

## Why This Architecture Can Scale

Standard, boring, proven components: PostgreSQL source of truth with
Alembic migrations, FastAPI backend, React frontend, container deployment,
pluggable embedding/LLM/storage providers, a rebuildable knowledge index.
Growth levers (pgvector/ANN, workers, auth/RBAC, monitoring) are labeled
FUTURE in [`SIH_IMPLEMENTED_VS_FUTURE.md`](SIH_IMPLEMENTED_VS_FUTURE.md) —
architecture ready, components not yet built.

## Current Limitations

- No authentication/RBAC — unauthenticated prototype; do not expose publicly.
- Docker/PostgreSQL runtime validation NOT VERIFIED in the development
  environment (statically verified; commands in the runbook).
- DOCX-only report output (no PDF — never attempted).
- LLM optional; without credentials the AI Query shows an honest
  unavailable state (deterministic features unaffected).
- Synchronous processing; no background workers (FUTURE).
- **Quantitative improvement is not claimed because production baseline
  measurements are not yet available.**

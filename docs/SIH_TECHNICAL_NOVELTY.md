# SIH — Technical Novelty Audit

**Framing:** the individual libraries (OCR engine, embedding model, DOCX
writer) are off-the-shelf and are **not** claimed as innovations. What is
ours is the **system-level combination and workflow**: every stage feeds
the next from one source of truth, and every output carries its evidence.
The differentiators below are characteristics of *this* implementation —
each points to real code and tests, none to a marketing claim.

## 1. Deterministic extraction before AI

Extraction/normalization is rule-based by design (extractor registry,
verbatim `value_raw` + safe normalization) — no generative model ever
touches the data path before validation. AI is used for retrieval and
answer composition only, on already-structured evidence.
*Evidence:* `app/processing/`, `app/structuring/`; Step 4/7 tests.

## 2. Validation-aware RAG

The evidence pack fed to the LLM is composed from knowledge-index units
that carry validation state — answers can cite whether their evidence
passed validation, and conflicting evidence surfaces REVIEW REQUIRED
instead of a blended answer. *Evidence:* `app/ai/service.py`,
`app/services/knowledge_service.py`; Step 10/15 tests.

## 3. Evidence objects with filtered citations

The AI returns a strict JSON contract whose citations are filtered against
real knowledge-index IDs — a model cannot cite units it was not given.
*Evidence:* `app/schemas/ai_query.py`, `app/ai/service.py` tests.

## 4. Conflict preservation end-to-end

Cross-document conflicts keep both values and sources at every layer
(validation → review queue → search results → AI answer → analytics
exclusion indicator → report disclosure). No layer picks a winner.
*Evidence:* `app/validation/`, analytics/report conflict handling; Step 6/11/15 tests.

## 5. Provenance continuity

One unbroken chain — document → page/section → record → validation →
index unit → evidence → report figure — verified by a dedicated test
(`test_report_provenance_reaches_the_docx`), not asserted in slides.

## 6. Explicit hybrid retrieval

Lexical (tsvector + GIN), semantic (local 384-d embeddings), and hybrid
scoring with a documented, deterministic formula — mode is selectable and
unavailability is reported honestly rather than silently degraded.
*Evidence:* `app/services/knowledge_service.py`; Step 9 tests.

## 7. Local embeddings, no cloud

`BAAI/bge-small-en-v1.5` (384-d) via fastembed ONNX, cached locally,
offline-capable after first use — semantic search with zero data egress,
no API keys. *Evidence:* `app/embeddings/`; runtime EMBED_OK check (Step 17).

## 8. Structured-data-first reporting

The DOCX report is generated from validated structured records through a
read-only data engine — no LLM in the report path, byte-stable output,
explicit missing-data markers. *Evidence:* `app/reports/`; Step 11 tests.

## 9. Human review as a workflow, not a checkbox

Flagged content flows into a review queue with real workflow states
(pending → in_review → reviewed), full evidence attached, audited actions.
*Evidence:* `/api/validation/review-queue`; Step 6 tests.

## 10. Rebuildable knowledge index

The index is derivable state (pages/records/validations → tsvector/GIN +
embeddings), rebuilt idempotently on processing — no second source of
truth to drift. *Evidence:* `app/services/knowledge_service.py`; Step 8 tests.

## 11. Modular provider architecture

Storage, embedding and LLM providers sit behind interfaces with
configuration-driven selection; the platform runs fully without an LLM.
Swapping providers is configuration, not surgery. *Evidence:*
`app/services/document_storage.py`, `app/embeddings/`, `app/llm/`.

---

**Honest scope:** these are engineering differentiators of the workflow
and guarantees — not research novelty claims, and not benchmarks.

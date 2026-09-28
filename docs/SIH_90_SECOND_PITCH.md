# SIH 90-Second Pitch

**(1) Problem.** Mining and geological reporting at CMPDI/CIL depends on
information locked in scanned PDFs, spreadsheets, images and decades of
historical records. Compiling one report means manual reading, manual
cross-checking — and no easy way to prove where any number came from.

**(2) Current limitation.** Today this work depends on individual
expertise: it is slow, error-prone, and conflicts between documents are
resolved silently, if they are noticed at all.

**(3) Solution.** Our platform turns that unstructured pile into verified,
traceable intelligence — automatically. Documents are ingested with strict
validation, text and tables are extracted (OCR included), and structured
records are built with the original values preserved.

**(4) AI components.** Local embeddings power semantic and hybrid search
over a knowledge index — no cloud, no data leaving the premises. An
optional LLM answers questions **only from retrieved evidence**, with
citations; without evidence it refuses rather than guesses.

**(5) Validation.** Deterministic rules check every extracted value.
Conflicts keep both sources visible and go to a human review queue — the
system never silently picks a winner.

**(6) Traceability.** Every number can be traced: document → page → record
→ validation → evidence → report figure — with an audit trail of actions.

**(7) Business/administrative value.** Faster compilation, consistent
validation, defensible reports — the report is generated directly from
validated records, with conflicts disclosed rather than hidden. (We claim
the mechanism, not invented percentages.)

**(8) Scalability.** Standard architecture — PostgreSQL, FastAPI, React,
containers, pluggable AI providers — ready to grow from one demo dataset
to subsidiary-scale deployments.

**(9) USP.** *"From Unstructured Documents to Verified, Traceable
Intelligence."*

---

## 30-Second Elevator Version (~95 words)

> "Mining reports are buried in scanned PDFs and spreadsheets. We built a
> platform that ingests them, extracts the data with OCR, validates every
> value with deterministic rules, and flags conflicts for human review
> instead of silently choosing a winner. Semantic search runs locally — no
> cloud — and the AI answers questions only from retrieved evidence, with
> citations, and refuses without it. The final DOCX report is generated
> from validated records with full provenance, end to end audited.
> In short: from unstructured documents to verified, traceable
> intelligence."

*(Practise to ~30 seconds; trim the OCR and audit clauses if over time.)*

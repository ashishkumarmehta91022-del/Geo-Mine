# SIH — Final Presentation Outline (10–12 minutes, 12 slides)

Pacing: ~50–60 seconds per slide. Slides carry keywords, not paragraphs.
The live demo (≈5 min, [`SIH_DEMO_SCREEN_MAP.md`](SIH_DEMO_SCREEN_MAP.md))
runs after slide 10 or replaces slides 6–10 live. Every claim maps to the
implemented-vs-future matrix — nothing here claims unbuilt capability.

---

### Slide 1 — Title
- **Title:** From Unstructured Documents to Verified, Traceable Intelligence
- Subtitle: AI-Powered Geological, Mining & Reporting Solution — SIH26023 (CMPDI/CIL)
- Team/PS id footer
- **Visual:** one blurred scanned page morphing into a clean data table
- **Say:** one sentence — the USP — then your names.

### Slide 2 — Problem Statement
- Reporting data is scattered across scanned PDFs, DOCX, spreadsheets, images
- Historical records must combine with current data
- Reports must be defensible: validated, consistent, traceable
- **Visual:** the problem-statement keywords as a compact diagram
- **Say:** read the PS essence in your own words — data formats in, trustworthy reporting out.

### Slide 3 — Existing Challenges
- Manual re-typing and cross-checking; expertise locked in individuals
- Conflicts between documents found late (or never)
- No provenance: "where did this number come from?" is hard to answer
- **Visual:** messy-folder → spreadsheet → error icons
- **Say:** anchor with the synthetic 1200-vs-1350 conflict example.

### Slide 4 — Proposed Solution
- One pipeline: ingestion → extraction/OCR → structured records → validation
- Then: knowledge index → grounded AI → analytics → automated DOCX report
- Audit metadata at every step; conflicts surfaced to humans
- **Visual:** the 12-stage data-flow diagram (see ARCHITECTURE.md / novelty doc)
- **Say:** name the USP again — this slide is the map of it.

### Slide 5 — System Architecture
- PostgreSQL source of truth; Alembic migrations 0001–0006
- FastAPI layered backend; React SPA; nginx same-origin proxy
- Pluggable storage / embedding / LLM providers; container topology
- **Visual:** compose topology diagram (postgres → backend → frontend)
- **Say:** "standard components, unusual guarantees" — boring tech, defensible output.

### Slide 6 — Document Processing + OCR
- Extractors: PyMuPDF / python-docx / openpyxl / xlrd / Pillow
- RapidOCR (ONNX, CPU) for scans/images with confidence scores
- Per-page native-vs-OCR dispatch; verbatim originals preserved
- **Visual:** a page split into native-text vs OCR regions with confidence bar
- **Say:** low confidence never silently passes — it goes to review.

### Slide 7 — Validation + Provenance
- Deterministic rule families → PASS / WARNING / ERROR / REVIEW REQUIRED
- Cross-document conflicts: both values + sources preserved, no winner
- Provenance chain: document → page → record → validation → report figure
- **Visual:** the chain as an arrow diagram ending on a DOCX figure callout
- **Say:** this chain is test-verified, not aspirational.

### Slide 8 — AI Query + Knowledge Retrieval
- Knowledge index (tsvector + GIN) + local 384-d embeddings — offline, no cloud
- Hybrid search with explicit scoring; results carry provenance
- LLM answers only from retrieved evidence; refuses without it; no LLM → honest unavailable
- **Visual:** query → evidence cards with citations → answer
- **Say:** "evidence-backed AI, not a chatbot" — plus untrusted-document-text neutralization.

### Slide 9 — Analytics + Automated Reporting
- KPI / trend / comparison / distribution engines over validated records
- Conflict groups excluded explicitly — never silently averaged away
- `POST /api/reports/generate`: byte-stable DOCX, per-figure sources
- **Visual:** mini KPI cards + the DOCX with a source-annotated table
- **Say:** the report is composed from the same records judges saw validated.

### Slide 10 — Dashboard + Demo Workflow
- Honest health tiles; live metrics; recent audit activity
- Demo flow: upload → validate → search → ask → report (≈5 minutes)
- All demo data is synthetic and labelled `DEMO_`
- **Visual:** dashboard screenshot + the 10-step demo strip
- **Say:** hand over to the live demo here (or run the screen map).

### Slide 11 — Scalability / Security / Future
- Scales on standard components; pgvector/ANN, workers, RBAC: FUTURE (labeled)
- Security: env-based secrets, upload signature checks, bounded prompts, metadata-only audit
- Honest limitation: no authentication yet — prototype, not production
- **Visual:** implemented-vs-future two-column panel
- **Say:** naming our limits is part of the engineering credibility.

### Slide 12 — Impact + Closing
- Verifiable today: extraction, validation, grounded AI, automated reporting, audit trail
- Measured quantitative impact: **not yet claimed** — production baselines not available
- *"From Unstructured Documents to Verified, Traceable Intelligence."*
- **Visual:** USP as the single large line; repo QR
- **Say:** thank the judges; invite them to the failure-recovery matrix if they probe reliability.

---

**Timing check:** 12 slides ≈ 10–12 minutes; the demo adds ≈5 minutes
(see the screen map). Slides 6–9 compress to 20 s each if the live demo
follows immediately.

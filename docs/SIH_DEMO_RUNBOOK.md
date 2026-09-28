# SIH Demo Runbook — CMPDI/CIL AI-Powered Geological, Mining & Reporting Solution

**USP:** *"From Unstructured Documents to Verified, Traceable Intelligence."*

> Companion docs: [`SIH_FINAL_DEMO_SCRIPT.md`](SIH_FINAL_DEMO_SCRIPT.md)
> (5-minute judge walkthrough + Q&A), [`SIH_90_SECOND_PITCH.md`](SIH_90_SECOND_PITCH.md),
> [`SIH_TECHNICAL_CHEAT_SHEET.md`](SIH_TECHNICAL_CHEAT_SHEET.md),
> [`SIH_IMPLEMENTED_VS_FUTURE.md`](SIH_IMPLEMENTED_VS_FUTURE.md).

This runbook is the single script for setting up, seeding, demonstrating, and
recovering the SIH demo environment. Every item is labelled with a
verification status:

| Marker | Meaning |
| --- | --- |
| **RUNTIME VERIFIED** | Actually executed in the current environment. |
| **STATICALLY VERIFIED** | Configuration/code inspected and enforced by tests (`backend/tests/test_deployment_static.py`, `backend/tests/test_deployment_readiness.py`), but not executed as a container/DB runtime. |
| **NOT AVAILABLE IN CURRENT ENVIRONMENT** | Requires Docker/PostgreSQL, which are not installed here. Commands are documented exactly; nothing is faked. |

## Environment status (Step 17, Phase 2)

| Component | Status |
| --- | --- |
| Python 3.14.2 (project venv) | **RUNTIME VERIFIED — AVAILABLE** |
| Node v24.19.0 / npm 11.17.0 | **RUNTIME VERIFIED — AVAILABLE** |
| FastEmbed model `BAAI/bge-small-en-v1.5` (384-dim) | **RUNTIME VERIFIED — cached locally; embeddings work offline** (`EMBED_OK dims=384` in 1.058 s) |
| Docker | **NOT AVAILABLE IN CURRENT ENVIRONMENT** |
| Docker Compose | **NOT AVAILABLE IN CURRENT ENVIRONMENT** |
| PostgreSQL server / `psql` / `pg_isready` | **NOT AVAILABLE IN CURRENT ENVIRONMENT** |

Because PostgreSQL and Docker are absent here, migration runtime, demo seeding,
and the live end-to-end demo flow are **NOT VERIFIED** in this environment.
All commands below are the exact ones to run on a demo machine that has the
infrastructure. The backend, meanwhile, *starts without a database* and
reports honest, degraded statuses (never fake zeroes) — that behaviour is
**RUNTIME VERIFIED**.

---

## 1. Before Demo

### Prerequisites (STATICALLY VERIFIED — files/templates checked by tests)

* Python 3.12+ venv at repo root (`.venv/`) — **RUNTIME VERIFIED**
* Node 24 + npm with `frontend/package-lock.json` committed — **RUNTIME VERIFIED**
* PostgreSQL 16 reachable (native service **or** the `postgres:16-alpine`
  compose service) — **NOT AVAILABLE IN CURRENT ENVIRONMENT**
* No API keys committed anywhere; the LLM is optional — **STATICALLY VERIFIED**

### Option A — Docker (single command, when Docker exists) — NOT VERIFIED here

```bash
# from repo root; .env must define DB_PASSWORD (compose refuses without it)
docker compose up --build
# backend container runs `alembic upgrade head` before serving on :8000
# frontend nginx serves on :80 and proxies /api -> backend:8000
```

### Option B — Native processes (used in this environment except PostgreSQL)

```bash
# 1) PostgreSQL (demo machine): create an EMPTY demo database
#    Windows service or: initdb + pg_ctl start, then:
createdb -U postgres cmpdi_reporting_demo      # demo DB name of your choice

# 2) Configure environment (never commit .env — it is git-ignored, verified)
cp .env.example .env
#   edit .env: DATABASE_URL=postgresql://<user>:<password>@localhost:5432/cmpdi_reporting_demo
#   optional:  LLM_PROVIDER=openai-compatible  LLM_API_KEY=...  LLM_MODEL=...  LLM_BASE_URL=...

# 3) Backend (from backend/, using the project venv)
../.venv/Scripts/python.exe -m pip install -r requirements.txt -c constraints.txt
alembic upgrade head            # applies 0001..0006 — NEVER create_all()
../.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# 4) Frontend (from frontend/)
npm ci
npm run dev                     # http://localhost:5173, /api proxied to :8000
```

### Health check before every demo — RUNTIME VERIFIED (endpoint + honest DB probe)

```bash
curl http://localhost:8000/api/health
# {"status":"ok","service":"cmpdi-ai-reporting-platform",
#  "database":{"connected":true,"detail":"connected"}}
```

`connected: true` only when PostgreSQL actually answered `SELECT 1`. If it
shows `"detail":"unavailable"` the API is still up — see Failure Recovery.

---

## 2. Seed Demo

Requires the live database above — **NOT AVAILABLE IN CURRENT ENVIRONMENT**
(command verified statically; seed script tested for safety by
`test_seed_script_inserts_demo_labelled_data_only` and
`test_seed_reset_is_scoped_to_demo_data_never_source_code_or_schema`).

```bash
# from backend/
../.venv/Scripts/python.exe ../scripts/seed_demo_data.py          # insert DEMO data
../.venv/Scripts/python.exe ../scripts/seed_demo_data.py --reset  # delete previous DEMO rows only
```

Verification checklist after seeding:

* Document `DEMO_borehole_log.pdf` exists; `source="demo_seed"` provenance.
* Entities/metrics are `DEMO_MINE_A/B`, `DEMO_COAL_PRODUCTION`, `DEMO_BOREHOLE_01`, `DEMO_DEPTH` — generic sample values, **never real CMPDI/CIL figures**.
* Knowledge index populated (`indexed_units` printed) → dashboard intelligence, search, and reports work.
* One audit row `seed.demo_data_loaded` appears in Dashboard recent activity.
* `--reset` deletes only the previous DEMO document (cascades to its pages/records/validation rows); it never touches source code, migrations, `.env`, or other data.

---

## 3. Demo Flow (10 minutes)

Routes below are the real client routes — **STATICALLY VERIFIED** to exist
(`test_frontend_routes_required_for_demo_exist`); the end-to-end walk requires
the database (**NOT AVAILABLE IN CURRENT ENVIRONMENT** here; Step 15 covered
the same workflow with DB-free/hardened tests).

1. **Dashboard** (`/dashboard`) — system health tiles, document/record/validation metrics, recent activity (audit trail).
2. **Documents** (`/documents`) — upload a supported demo document (PDF/DOCX/TXT/CSV/images); storage is local + bounded by `MAX_UPLOAD_SIZE_MB` (nginx cap 30 MB).
3. **Process / OCR** — pipeline extracts pages and text; low-confidence OCR is flagged `review_required` instead of silently accepted.
4. **Validation** (`/validation`) — rule engine results with `source_reference`, `original_value` vs `expected_value`; conflicts stay visible.
5. **Search** (`/knowledge`) — keyword search over the knowledge index; semantic/hybrid ranking when embeddings exist (model cached — offline OK).
6. **AI Query** (`/ai-query`) — evidence-grounded answers with citations; with no LLM configured it reports an honest unavailable state; with an LLM it refuses to answer without sufficient evidence.
7. **Topic Intelligence** (`/topic-intelligence`) — deterministic topics, keywords, word cloud.
8. **Analytics** (`/data-explorer`) — structured records, distributions, validation breakdown.
9. **Report** (`/report-generator`) — generate the DOCX report from validated records with provenance per figure.
10. **Audit** — every pipeline action is an `audit_logs` row; show recent activity on the Dashboard.

Each screen reads the same source of truth (PostgreSQL tables + storage) —
no separate demo state exists.

---

## 4. What to Say

* **USP:** *"From Unstructured Documents to Verified, Traceable Intelligence."*
* Mining reports arrive as messy PDFs/scans; the platform **extracts** structured records automatically, **validates** them with explicit rules, and keeps the **original page/section reference** for every value.
* The AI assistant is **evidence-backed**: answers cite knowledge-index units; without evidence it says so. Conflicts are **shown with both sources** — the system never silently picks a winner.
* **Analytics** and the **auto-generated DOCX report** are composed from validated records only, each figure traceable to its document.
* **Provenance & auditability** end-to-end: extraction → validation → index → search → AI evidence → report, all audited.
* Honest limits (say these proactively): prototype without authentication — do not expose publicly; LLM features need a configured provider and otherwise show a truthful "unavailable"; OCR quality gates low-confidence text for human review.
* Demo data is generic sample data (`DEMO_` prefixed) — not real CMPDI/CIL figures.

---

## 5. Failure Recovery

| Failure | What the user sees (honest behaviour — RUNTIME VERIFIED mapping) | Recovery |
| --- | --- | --- |
| **Database unavailable** | `/api/health` → `connected:false, detail:"unavailable"`; Dashboard shows `data_available:false` with "No demo values are shown"; statuses `UNAVAILABLE`/`NOT CONFIGURED` — never fake zeroes. | Start PostgreSQL (`pg_ctl start` or `docker compose up -d postgres`), then `alembic upgrade head`, re-check health. |
| **LLM unavailable / not configured** | AI Query shows a truthful unavailable/configured-off state; extraction, validation, search, topics, reports all work (deterministic). | Set `LLM_PROVIDER`/`LLM_API_KEY`/`LLM_MODEL`/`LLM_BASE_URL` in `.env`, restart backend; demo with deterministic features meanwhile. |
| **Embedding unavailable** | Semantic ranking degrades to lexical search; dashboard `embeddings` shows `NOT CONFIGURED`/`DEGRADED`. | Embeddings are best-effort: model `BAAI/bge-small-en-v1.5` is cached locally (offline OK). If missing, first processing run downloads it once (needs network) or continue lexical-only. |
| **OCR unavailable / poor scan** | Pages flagged `review_required`; Review Queue surfaces them; nothing silently dropped. | Re-upload a cleaner scan or raise `OCR_CONFIDENCE_THRESHOLD` tolerance discussion; process text-native PDFs instead. |
| **Report generation failure** | Error surfaced on `/report-generator` with cause (missing records/validation). | Ensure the target documents are processed + validated; check `extracted_records`/`validation_results` in Data Explorer; retry. |
| **Demo data messed up** | — | `python scripts/seed_demo_data.py --reset` then re-seed; or drop/recreate the **demo** database only and `alembic upgrade head`. |

**Backup / reset safety (STATICALLY VERIFIED):** reset procedures only touch
the DEMO-labelled document/rows and the demo database named in `.env`.
Source code, `alembic/` migrations, and configuration are never deleted.
Backup before demo if desired:

```bash
pg_dump -U <user> cmpdi_reporting_demo > demo_backup_$(date +%F).sql
```

There is no destructive production-reset command anywhere in the repo.

---

## 6. Verification matrix (Step 17 summary)

| Area | Status |
| --- | --- |
| Backend/frontend Dockerfiles, `.dockerignore`, nginx config | **STATICALLY VERIFIED** (tests) |
| Compose topology (health-gated backend, named volumes, minimal ports, no extra services) | **STATICALLY VERIFIED** (tests) |
| Image builds / container startup / nginx proxying live | **NOT AVAILABLE IN CURRENT ENVIRONMENT** (Docker) |
| `alembic upgrade head` on real PostgreSQL | **NOT AVAILABLE IN CURRENT ENVIRONMENT**; chain + DDL parity statically verified |
| Demo seed + `--reset` execution | **NOT AVAILABLE IN CURRENT ENVIRONMENT**; label/reset safety statically verified |
| Health/status honesty incl. DB outage | **RUNTIME VERIFIED** (TestClient, no DB) |
| Embeddings (`BAAI/bge-small-en-v1.5`, 384-dim) cached & offline-capable | **RUNTIME VERIFIED** |
| Frontend production build (`tsc -b && vite build`) | **RUNTIME VERIFIED** (Step 16/17 builds) |
| Security scan (secrets/paths/dynamic SQL) | **RUNTIME VERIFIED** (clean) |

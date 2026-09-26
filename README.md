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
pip install -r requirements.txt
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
| `LLM_PROVIDER`  | backend   | No                 | AI provider name (unused until later steps) |
| `LLM_API_KEY`   | backend   | No                 | AI provider key (unused until later steps) |
| `ENVIRONMENT`   | backend   | No                 | `development` / `production`              |
| `DEBUG`         | backend   | No                 | Verbose logging when `true`               |
| `CORS_ORIGINS`  | backend   | No                 | Comma-separated allowed origins           |
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

## Current Implementation Status

**Done (Step 1 — Foundation):**

- ✅ Repository layout: `frontend/`, `backend/`, `data/`, `docs/`, `scripts/`
- ✅ FastAPI backend with modular structure, `GET /api/health`, CORS, central error handling
- ✅ PostgreSQL foundation: SQLAlchemy engine + sessions, ORM models for the 5 foundation tables, Alembic migration `0001_initial_schema`, DEMO seed script
- ✅ Environment configuration via `.env` / `.env.example` — no secrets in code
- ✅ React + TypeScript + Tailwind app shell: sidebar, header, content area
- ✅ Sidebar navigation for all 10 modules (Dashboard implemented; others placeholders)
- ✅ Reusable UI components + loading / empty / error states
- ✅ Backend tests (config, health, no-hang guarantee, schema integrity) + opt-in PostgreSQL integration suite; frontend typecheck + production build

**Not yet implemented (later steps):**

- ⬜ Document processing (upload, PDF/Excel parsing)
- ⬜ OCR for scanned reports
- ⬜ Data extraction and structuring
- ⬜ Validation engine
- ⬜ Knowledge base (vector store — the base relational schema already exists)
- ⬜ RAG pipeline
- ⬜ AI Query (natural-language Q&A)
- ⬜ Report generation
- ⬜ Topic Intelligence (word clouds, topic modelling)
- ⬜ Authentication / RBAC

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the target architecture.

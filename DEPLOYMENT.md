# Deployment Guide — Vercel (frontend) + Railway (backend)

The app splits into two deployable units:

| Unit | Platform | What it serves |
|---|---|---|
| `frontend/` | Vercel (static SPA, Vite build) | React dashboard |
| `backend/` | Railway (FastAPI + PostgreSQL) | `/api/*` JSON API |

The frontend is a **static build** — in production there is no Vite dev proxy,
so the browser calls the API origin directly. Two settings connect the halves;
**both are required**, or the dashboard shows
"Cannot reach the backend API / Cannot reach the API server."

---

## 1. Railway — backend service

Import the repo and point the API service at the `backend/` directory.

**Build / start (Nixpacks, no Dockerfile):**

- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt -c constraints.txt`
- Start Command:

  ```bash
  alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```

  `$PORT` is mandatory — Railway routes traffic to the port it injects.
  Binding a hard-coded 8000 gives a 502 from the public domain.

**Alternative — Docker:** Railway auto-detects `backend/Dockerfile` when the
root directory is `backend/`. The Dockerfile already runs
`alembic upgrade head` before uvicorn and listens on 8000 (Railway maps its
proxy to the exposed container port). Use this if a Nixpacks pip build fails
on a wheel (the OCR/embedding stack ships native wheels: `onnxruntime`,
`rapidocr-onnxruntime`, `psycopg[binary]`, `fastembed`).

**Database:** In the project, *New → Database → PostgreSQL*. Then on the API
service add a reference variable:

```
DATABASE_URL = ${{Postgres.DATABASE_URL}}
```

Migrations (`alembic upgrade head`) run automatically on every start with the
command above. Without `DATABASE_URL` the API still boots honestly
(`/api/health` shows `database: UNAVAILABLE`) but every data endpoint
returns 503 `database_error`.

**Public domain:** Service → Settings → Networking → *Generate Domain* →
you get `https://<service>.up.railway.app`. This is the value for step 2.

**Backend environment variables:**

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | reference to the Railway Postgres |
| `CORS_ORIGINS` | `https://<app>.vercel.app` | **exact** scheme+host of the Vercel app, no trailing slash, no path. Comma-separate extras (e.g. preview URLs). A wildcard `*` does **not** work — the backend sets `allow_credentials=True`, which forbids wildcard origins. |
| `ENVIRONMENT` | `production` | optional; reduces log verbosity |
| `DEBUG` | `false` | optional |

Variable names are case-insensitive (`CORS_ORIGINS` → the `cors_origins`
setting). Values are read from the service environment; no `.env` file is
needed on Railway.

**Verify the backend alone before touching Vercel:**

```bash
curl https://<service>.up.railway.app/api/health
```

Expected: HTTP 200 JSON with component statuses. If this fails, fix Railway
first — the frontend cannot work until this responds.

### LLM on Railway (AI Query)

The local Ollama server (`http://127.0.0.1:11434`) does not exist on Railway.
Two honest options:

1. **Leave LLM variables unset (default).** Everything except AI answers
   works; `POST /api/ai/query` returns `503 llm_unavailable` and the UI shows
   "LLM NOT CONFIGURED" — by design, never fabricated answers.
2. **Point at any OpenAI-compatible endpoint** (Groq, OpenRouter, OpenAI, a
   hosted Ollama, vLLM…):

   ```
   LLM_PROVIDER=openai-compatible
   LLM_API_KEY=<key>
   LLM_MODEL=<model id>
   LLM_BASE_URL=https://<endpoint>/v1
   ```

### Known limitation: ephemeral storage

Uploaded originals (`DOCUMENT_STORAGE_PATH=./storage/documents`) and the
embedding model cache live on the container's ephemeral filesystem — they are
lost on redeploy. Attach a Railway volume for `DOCUMENT_STORAGE_PATH` if
uploads must survive deploys.

---

## 2. Vercel — frontend

Import the repo with Root Directory `frontend` (Vercel detects Vite; build
`npm run build`, output `dist`).

**Environment variable (Project → Settings → Environment Variables):**

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://<service>.up.railway.app` |

Rules:

- **No trailing slash and no `/api` suffix** — the client appends `/api/...`
  itself.
- Must be **https** (the page is https; an http target is blocked as mixed
  content).
- Vite bakes `VITE_*` variables in at **build time** — after adding the
  variable you must **redeploy** (Deployments → ⋯ → Redeploy). Existing
  deployments do not pick it up.
- Enable it for Production (and Preview if you want PR previews wired too).
- Never put secrets in `VITE_*` variables — they are compiled into the public
  JS bundle.

---

## 3. How the pieces connect

```
Browser (https://<app>.vercel.app)
   │  fetch("https://<service>.up.railway.app/api/health")   ← VITE_API_BASE_URL
   ▼
Railway FastAPI
   │  CORS check: Origin https://<app>.vercel.app            ← CORS_ORIGINS
   ▼
Railway PostgreSQL (DATABASE_URL)
```

If either setting is missing, `fetch` fails at the network/CORS layer and the
UI shows its diagnostic message, which now includes **the exact URL it tried**
so you can tell which half is misconfigured:

| Error text contains | Meaning | Fix |
|---|---|---|
| `Tried https://<vercel-app>.vercel.app/api (same origin — no VITE_API_BASE_URL set)` | Frontend has no API origin | Set `VITE_API_BASE_URL` in Vercel, **redeploy** |
| `Tried https://<service>.up.railway.app/api` and the browser console shows a CORS error | Backend does not allow the frontend origin | Set `CORS_ORIGINS` in Railway (exact Vercel origin), redeploy backend |
| `Tried https://<service>.up.railway.app/api` and curl to `/api/health` also fails | Backend itself is down/misrouted | Fix Railway root dir / start command (`$PORT`!) / DATABASE_URL per §1 |

Note: dev (`npm run dev`) needs none of this — the Vite proxy handles `/api`
via `VITE_API_PROXY_TARGET` (default `http://localhost:8000`), and
`frontend/.env.local` is not committed.

---

## 3b. Populating the deployed instance (EMBEDDINGS tile)

A fresh Railway database is empty, so the dashboard honestly shows
`EMBEDDINGS — NOT CONFIGURED (No units embedded yet)` and `RETRIEVAL —
DEGRADED`. Two ways to fill it:

**Option A — exercise the real pipeline (recommended):** upload a demo file
on the deployed Documents page → Process. Extraction, validation, indexing
run server-side; the embedding model (bge-small-en-v1.5, ~130 MB) downloads
once on first use. Note the process call is synchronous — Railway's proxy
may return `502 Application failed to respond` on the first document while
the model downloads; the work completes anyway. Then make every unit
searchable (pages + records + validations) with the idempotent embed
endpoint per document:

```bash
curl -X POST https://<service>.up.railway.app/api/search/embed/<document_id>
```

Both steps are exactly what the UI pipeline does; after them
`/api/dashboard/summary` reports `embeddings: OPERATIONAL` with 100%
coverage (verified live on 2026-09-30).

**Option B — seed the DEMO dataset directly:** copy the **public** database
URL from Railway → Postgres service → Connect tab (keep credentials out of
chat/screenshots), then from the repo root:

```bash
DATABASE_URL="postgresql://<user>:<pass>@<host>:<port>/<db>" \
  .venv/Scripts/python.exe scripts/seed_demo_data.py
```

The script inserts one `DEMO_`-labelled document (2 pages, 3 records,
1 validation, 1 audit row) and indexes it. `--reset` deletes only previous
DEMO rows. It does **not** configure an LLM — see §LLM.

## 4. Post-deploy checklist

1. `curl https://<service>.up.railway.app/api/health` → 200.
2. Open `https://<app>.vercel.app` → dashboard health strip shows real
   component statuses (no error block).
3. Upload a document in the Documents page → process it → records, validation
   and knowledge index fill in (OCR/embedding run inside Railway; the
   embedding model downloads once on first use).
4. AI Query answers only if an external LLM was configured (§LLM) — otherwise
   the honest "LLM NOT CONFIGURED" state is correct behaviour.
5. A fresh database is empty — the demo banner ("synthetic data") refers to
   local seeding; the deployed instance starts with zero documents.

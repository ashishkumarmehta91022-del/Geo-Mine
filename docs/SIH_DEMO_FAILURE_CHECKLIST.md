# SIH — Demo Failure Checklist (mid-demo recovery)

Keep this open on a second monitor. Each recovery is ≤ 30 seconds of work;
"what to say" turns any failure into an honesty demonstration. Pre-demo
preparation: [`SIH_DEMO_RUNBOOK.md`](SIH_DEMO_RUNBOOK.md).

**Universal honesty anchor:** the platform never fakes health — if
something is down, the UI *says so*. That is a feature; say it proudly.

## 1. PostgreSQL unavailable
- **SYMPTOM:** `/api/health` shows `connected:false`; dashboard says "Database unavailable — no demo values are shown".
- **CHECK:** `pg_isready -U cmpdi_user -d cmpdi_reporting_demo` (or compose: `docker compose ps`).
- **RECOVERY:** start the service (`pg_ctl start` / `docker compose up -d postgres`), wait for healthy, re-run `alembic upgrade head` if the DB is fresh, re-check `/api/health`.
- **SAY:** "Note the dashboard refused to show fake zeroes — the statuses are honest even during an outage."

## 2. Backend unavailable
- **SYMPTOM:** frontend shows network/API errors; `curl http://localhost:8000/api/health` fails.
- **CHECK:** backend terminal for a traceback; port 8000 free?
- **RECOVERY:** restart uvicorn (`python -m uvicorn app.main:app --port 8000`); if the port is taken, find/stop the stale process, restart.
- **SAY:** "The API reports its own dependency state at /api/health — restarting it is a single command."

## 3. Frontend unavailable
- **SYMPTOM:** browser tab dead or blank on :5173.
- **CHECK:** is `npm run dev` still running? Any compile error in its terminal?
- **RECOVERY:** restart `npm run dev`; or fall back to `npm run build && npm run preview`; worst case, drive the API via `/docs` (Swagger UI) live.
- **SAY:** "Even from the raw API docs, every capability is demonstrable — the UI is a layer on documented endpoints."

## 4. OCR failure (scanned upload misbehaves)
- **SYMPTOM:** a page shows no text / failed extraction status.
- **CHECK:** document status in `/documents`; OCR confidence values on the page.
- **RECOVERY:** switch to the pre-seeded `DEMO_borehole_log.pdf` or a text-native PDF for the remainder of the demo; revisit the scanned file if time allows.
- **SAY:** "Extraction failures are surfaced in status, not hidden — and the review flag is exactly how poor scans get caught."

## 5. Embedding unavailable
- **SYMPTOM:** search falls back to lexical; dashboard embeddings tile shows NOT CONFIGURED/DEGRADED.
- **CHECK:** embeddings tile on `/dashboard`; logs for model-load errors.
- **RECOVERY:** continue with lexical mode (deterministic, always works); optionally restart backend to reload the cached model.
- **SAY:** "Semantic search degrades to lexical explicitly — never silently. The model runs locally and works offline once cached."

## 6. LLM unavailable
- **SYMPTOM:** AI Query answers with `llm_unavailable` — **evidence still attached**.
- **CHECK:** is that state honest? (No `LLM_API_KEY` in `.env` → expected.)
- **RECOVERY:** demo the evidence pack itself; or set credentials and restart if you genuinely have them.
- **SAY:** "Without a configured provider the system says so and still returns the evidence — retrieval-grounded design means the AI is optional."

## 7. Report generation failure
- **SYMPTOM:** `/report-generator` shows an error on generate.
- **CHECK:** do the target documents have processed + validated records (see `/data-explorer`)?
- **RECOVERY:** generate over the seeded DEMO documents; re-run validation first if needed.
- **SAY:** "The report refuses to invent numbers — with no validated records it fails loudly instead of fabricating content."

## 8. Validation conflict (planted demo moment)
- **SYMPTOM:** the 1200-vs-1350 conflict shows REVIEW REQUIRED. *(This is the plan, not a failure.)*
- **CHECK:** both sources visible with document/page references?
- **RECOVERY:** walk it: validation → review queue states → analytics exclusion → report disclosure.
- **SAY:** "The system does not pick a winner — a human does, with the evidence attached."

## 9. Empty search results
- **SYMPTOM:** search returns nothing.
- **CHECK:** was the knowledge index populated (seed/process step done)? Any typo in the term?
- **RECOVERY:** re-run `python scripts/seed_demo_data.py` or search "coal production"; confirm `indexed_units` on the dashboard.
- **SAY:** "Search only returns what was actually indexed — it cannot invent results."

## 10. Demo data unavailable
- **SYMPTOM:** dashboard zeroed, no `DEMO_` documents.
- **CHECK:** was seeding run on this database?
- **RECOVERY:** run `python scripts/seed_demo_data.py` (needs live PostgreSQL); verify `DEMO_borehole_log.pdf` in `/documents`.
- **SAY:** "All data is synthetic and DEMO_-labelled — reproducible from one command, never real CMPDI/CIL figures."

---

**Order of battle if time is short:** switch to seeded demo data → lexical
search → deterministic features (validation/report) → honest AI states.
The full recovery playbook (setup-time failures): [`SIH_DEMO_RUNBOOK.md`](SIH_DEMO_RUNBOOK.md).

# scripts/

Helper scripts (database setup, seed data, CI helpers) will live here as the
project grows. For now, use the commands below, documented in the root
[README](../README.md).

| Task                        | Command (from repo root)                          |
| --------------------------- | ------------------------------------------------- |
| Start backend API (dev)     | `cd backend && uvicorn app.main:app --reload`     |
| Run backend tests           | `cd backend && pytest`                            |
| Start frontend dev server   | `cd frontend && npm run dev`                      |
| Typecheck + build frontend  | `cd frontend && npm run build`                    |

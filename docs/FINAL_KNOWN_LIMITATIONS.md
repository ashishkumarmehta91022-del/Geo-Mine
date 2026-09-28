# Final Known Limitations

Genuine limitations only, in three categories.

## CURRENT ENVIRONMENT LIMITATIONS
*(properties of this development machine — the product is not at fault)*

1. **PostgreSQL runtime not available** — live `alembic upgrade head`,
   seed execution, and the seeded E2E walkthrough are NOT VERIFIED here;
   the DB-dependent test portion (113 tests) skips honestly. Exact
   commands: [`SIH_DEMO_RUNBOOK.md`](SIH_DEMO_RUNBOOK.md).
2. **Docker/Compose runtime not available** — image builds, container
   startup, and live nginx proxying are NOT VERIFIED; the configuration is
   statically validated by 20 tests.
3. **No live LLM provider test** — `LLM_*` credentials absent; the
   provider path is contract-tested with the labeled mock; live-provider
   behavior is NOT VERIFIED with a real key.

## PRODUCT LIMITATIONS
*(true of the current codebase)*

1. **No authentication/RBAC** — unauthenticated prototype; must never be
   exposed publicly; enterprise identity integration is FUTURE.
2. **LLM optional, not required** — deterministic features unaffected;
   AI Query honestly reports `llm_unavailable` without credentials.
3. **DOCX-only reporting** — no PDF output (never attempted).
4. **Synchronous processing** — no background workers; large documents
   process inline (workers are FUTURE).
5. **Semantic retrieval is brute-force over JSONB** — cosine ranking in
   the application tier; pgvector/ANN is FUTURE; fine at prototype scale,
   not yet at subsidiary-corpus scale.
6. **No measured production baseline** — quantitative improvement is not
   claimed because production baseline measurements are not yet available.
7. **Aggregates computed on request** — dashboard/reports do not persist
   precomputed rollups (fine at prototype scale).
8. **Review pages split across screens** — standalone `/review-queue` and
   `/audit-logs` pages are placeholders; functionality lives in
   `/validation` and the Dashboard activity feed.
9. **Intelligence derived labels** — topics are co-occurrence-derived,
   explicitly not official CMPDI/CIL topic definitions.

## FUTURE ENHANCEMENTS
*(architected-for, not built — never claim in the demo)*

1. Authentication/RBAC + enterprise identity (SSO) integration.
2. PostgreSQL/pgvector with ANN vector retrieval.
3. Background processing workers + job queue.
4. Object storage (S3-compatible) behind the existing storage interface.
5. Production monitoring/alerting and horizontal API scaling.
6. Report artifact persistence + download history.
7. DOCX-embedded chart images + CMPDI/CIL template pack.
8. Multi-subsidiary tenancy / Ministry workflow integration.

Cross-reference: [`FINAL_RELEASE_READINESS.md`](FINAL_RELEASE_READINESS.md) ·
[`SIH_IMPLEMENTED_VS_FUTURE.md`](SIH_IMPLEMENTED_VS_FUTURE.md)

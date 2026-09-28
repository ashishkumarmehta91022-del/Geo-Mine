"""Step 17 deployment static-validation tests — DB-free.

Phases 3/4/12/13/14/16 of Step 17, expressed as executable checks:

  - Docker build validation ........ STATICALLY VERIFIED (Docker NOT AVAILABLE
    in this environment — see docs/SIH_DEMO_RUNBOOK.md for the runtime matrix).
  - Compose topology ............... STATICALLY VERIFIED.
  - Frontend deployment config ..... STATICALLY VERIFIED.
  - Health/status honesty .......... RUNTIME VERIFIED (pure FastAPI, no DB).
  - Demo seed/reset safety ......... STATICALLY VERIFIED (script requires live
    PostgreSQL to execute — seed run itself is NOT VERIFIED here).

No test in this file pretends PostgreSQL, Docker, or Compose are running.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

SECRET_MARKERS = ("sk-", "BEGIN PRIVATE KEY", "AKIA", "xoxb-", "ghp_")


def _read(repo_relative: str) -> str:
    return (REPO_ROOT / repo_relative).read_text(encoding="utf-8")


# --- Phase 3: Docker build validation (static) -----------------------------------


def test_backend_dockerfile_build_and_runtime_shape():
    """Backend image: constrained install, code-only COPY, non-root, migration CMD."""
    text = _read("backend/Dockerfile")
    assert "FROM python:3.14-slim" in text
    # Deterministic, constraint-pinned dependency install:
    assert "COPY requirements.txt constraints.txt ./" in text
    assert "pip install --no-cache-dir -r requirements.txt -c constraints.txt" in text
    # Only application code is copied — no storage/, cache, venv, or dotfiles:
    assert "COPY alembic.ini ./" in text
    assert "COPY alembic ./alembic" in text
    assert "COPY app ./app" in text
    assert "COPY . ." not in text
    # Non-root runtime user, declared after creation:
    assert text.index("USER appuser") > text.index("useradd --create-home appuser")
    assert "EXPOSE 8000" in text
    # Migrations run before serving — never create_all():
    assert "alembic upgrade head" in text
    assert "uvicorn app.main:app" in text
    assert "create_all" not in text


def test_backend_dockerfile_has_no_secrets_or_env_files():
    text = _read("backend/Dockerfile")
    for marker in SECRET_MARKERS:
        assert marker not in text
    for directive in text.splitlines():
        # Comments may mention safety; instructions may not reference env files.
        if directive.strip().startswith("#"):
            continue
        assert ".env" not in directive, directive
        assert "PASSWORD" not in directive, directive
        assert "postgresql://" not in directive, directive


def test_dockerignore_excludes_storage_cache_and_venv_from_build_context():
    lines = {
        line.strip()
        for line in _read(".dockerignore").splitlines()
        if line.strip() and not line.startswith("#")
    }
    # Secrets:
    assert {".env", "backend/.env", ".git"} <= lines
    # Local artifacts / storage / caches / dependency trees:
    for entry in (".venv", "venv", "__pycache__", "node_modules",
                  "storage", "uploads", "demo_storage", "frontend/dist"):
        assert entry in lines, entry


def test_frontend_dockerfile_is_exactly_two_stage_lockfile_build():
    text = _read("frontend/Dockerfile")
    from_lines = [line for line in text.splitlines() if line.startswith("FROM ")]
    assert len(from_lines) == 2  # build stage + nginx runtime, nothing extra
    assert "FROM node:24-alpine AS build" in from_lines[0]
    assert "FROM nginx:alpine" in from_lines[1]
    # Reproducible install from the committed lockfile:
    assert "COPY package.json package-lock.json ./" in text
    assert "RUN npm ci" in text
    assert "RUN npm run build" in text
    assert "COPY --from=build /app/dist /usr/share/nginx/html" in text
    assert "COPY nginx.conf /etc/nginx/conf.d/default.conf" in text


def test_frontend_dockerfile_has_no_secrets_or_env_files():
    text = _read("frontend/Dockerfile")
    for marker in SECRET_MARKERS:
        assert marker not in text
    assert ".env" not in text
    assert "DATABASE_URL" not in text


# --- Phase 3/4: nginx + compose topology (static) ---------------------------------


def test_nginx_conf_same_origin_proxy_and_spa_fallback():
    text = _read("frontend/nginx.conf")
    assert "listen 80;" in text
    assert "root /usr/share/nginx/html;" in text
    assert "index index.html;" in text
    # SPA fallback: unknown client-side routes serve the app shell.
    assert "try_files $uri $uri/ /index.html;" in text
    # Same-origin API proxy to the compose service name:
    assert "location /api/" in text
    assert "proxy_pass http://backend:8000;" in text
    assert "proxy_set_header Host $host;" in text
    assert "X-Forwarded-For" in text
    # Upload ceiling matches the backend limit story (30 MB).
    assert "client_max_body_size 30m;" in text
    # No envsubst interpolation — plain static config:
    assert "${" not in text
    for marker in SECRET_MARKERS:
        assert marker not in text


def test_compose_topology_backend_gated_on_healthy_postgres():
    compose: dict[str, Any] = yaml.safe_load(_read("docker-compose.yml"))
    services = compose["services"]
    assert sorted(services) == ["backend", "frontend", "postgres"]
    # Backend starts only after PostgreSQL passes its healthcheck:
    depends = services["backend"]["depends_on"]
    assert depends["postgres"]["condition"] == "service_healthy"
    # Frontend sits behind the backend only:
    assert "backend" in services["frontend"]["depends_on"]
    # PostgreSQL healthcheck is meaningful (real readiness probe):
    pg_test = " ".join(services["postgres"]["healthcheck"]["test"])
    assert "pg_isready" in pg_test
    hc = services["postgres"]["healthcheck"]
    assert hc["interval"] and hc["timeout"] and hc["retries"]


def test_compose_persistent_volumes_port_surface_and_no_extra_services():
    compose: dict[str, Any] = yaml.safe_load(_read("docker-compose.yml"))
    services = compose["services"]
    volumes = compose["volumes"]
    # Data survives restarts: named volumes for DB and uploads.
    assert set(volumes) == {"postgres_data", "uploads"}
    assert "postgres_data:/var/lib/postgresql/data" in services["postgres"]["volumes"]
    assert "uploads:/data/documents" in services["backend"]["volumes"]
    # Documented, minimal port surface (PostgreSQL exposed for local dev only):
    assert services["postgres"]["ports"] == ["5432:5432"]
    assert services["backend"]["ports"] == ["8000:8000"]
    assert services["frontend"]["ports"] == ["80:80"]
    # No unnecessary services — the app uses no broker/cache/object store:
    for banned in ("redis", "rabbitmq", "kafka", "minio", "nginx-proxy"):
        assert banned not in services


def test_compose_build_contexts_exist_and_carry_no_secrets():
    compose: dict[str, Any] = yaml.safe_load(_read("docker-compose.yml"))
    assert compose["services"]["backend"]["build"] == "./backend"
    assert compose["services"]["frontend"]["build"] == "./frontend"
    assert (REPO_ROOT / "backend" / "Dockerfile").is_file()
    assert (REPO_ROOT / "frontend" / "Dockerfile").is_file()
    backend_env = compose["services"]["backend"]["environment"]
    # Secrets arrive via interpolation only — never literals:
    assert "${DB_PASSWORD" in backend_env["DATABASE_URL"]
    assert backend_env["LLM_API_KEY"] == "${LLM_API_KEY:-}"
    for value in backend_env.values():
        for marker in SECRET_MARKERS:
            assert marker not in str(value)
    assert backend_env["DEBUG"] is False or backend_env["DEBUG"] == "false"
    assert backend_env["ENVIRONMENT"] == "production"


# --- Phase 5–8/10: runtime prerequisites documented (NOT AVAILABLE here) ----------


def test_runtime_prerequisite_commands_are_documented_in_runbook():
    """Docker/PostgreSQL runtime phases stay honest: the runbook records the
    exact commands and NOT VERIFIED markers for this environment."""
    runbook = _read("docs/SIH_DEMO_RUNBOOK.md")
    assert "NOT AVAILABLE IN CURRENT ENVIRONMENT" in runbook
    assert "docker compose up --build" in runbook
    assert "alembic upgrade head" in runbook
    assert "scripts/seed_demo_data.py" in runbook


# --- Phase 12: frontend deployment configuration (static) -------------------------


def test_frontend_api_base_url_defaults_to_same_origin():
    text = _read("frontend/src/lib/env.ts")
    assert 'import.meta.env.VITE_API_BASE_URL ?? ""' in text
    assert "same origin" in text.lower()


def test_frontend_bundle_variables_are_browser_safe_only():
    """Only VITE_-prefixed (public) variables may be referenced in src; no
    secret-bearing env files are tracked for the frontend."""
    import re
    import subprocess

    src = ""
    for path in (REPO_ROOT / "frontend" / "src").rglob("*.ts*"):
        src += path.read_text(encoding="utf-8")
    assert sorted(set(re.findall(r"VITE_[A-Z_]+", src))) == ["VITE_API_BASE_URL"]
    tracked = subprocess.run(
        ["git", "ls-files", "frontend/.env", "frontend/.env.*"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    for name in tracked:
        assert "example" in name or "sample" in name, name  # placeholders only
        for marker in SECRET_MARKERS:
            assert marker not in (REPO_ROOT / name).read_text(encoding="utf-8")


def test_frontend_routes_required_for_demo_exist():
    """Demo-flow routes are real client routes (SPA fallback target exists)."""
    src_dir = REPO_ROOT / "frontend" / "src"
    page_blob = "\n".join(
        p.read_text(encoding="utf-8")
        for p in src_dir.rglob("*.tsx")
    )
    for route in ("/dashboard", "/documents", "/validation", "/knowledge",
                  "/ai-query", "/topic-intelligence", "/report-generator",
                  "/data-explorer"):
        assert f'path="{route}"' in page_blob, route


# --- Phase 13: health & monitoring honesty (RUNTIME VERIFIED, DB-free) ------------


@pytest.fixture()
def api_client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)  # no lifespan: no startup DB probe


def test_health_endpoint_reports_database_outage_honestly(api_client, monkeypatch):
    import app.api.routes.health as health_route

    monkeypatch.setattr(
        health_route, "probe_database", lambda: (False, "unavailable")
    )
    response = api_client.get("/api/health")
    assert response.status_code == 200  # liveness survives the outage
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is False
    assert body["database"]["detail"] == "unavailable"


def test_health_endpoint_reports_connected_database_honestly(api_client, monkeypatch):
    import app.api.routes.health as health_route

    monkeypatch.setattr(health_route, "probe_database", lambda: (True, "connected"))
    body = api_client.get("/api/health").json()
    assert body["database"] == {"connected": True, "detail": "connected"}


def test_dashboard_statuses_map_dependencies_truthfully():
    from app.dashboard.service import compute_statuses

    # PostgreSQL down → retrieval/embeddings degrade with it (never healthy).
    down = compute_statuses(
        db_connected=False, db_detail="unavailable", index_stats=None,
        llm_configured=False,
    )
    assert down["database"].status == "UNAVAILABLE"
    assert down["retrieval"].status == "UNAVAILABLE"
    assert down["embeddings"].status == "UNAVAILABLE"
    assert down["llm"].status == "NOT CONFIGURED"

    # Up but empty index → degraded retrieval, not a fake OPERATIONAL.
    empty = compute_statuses(
        db_connected=True, db_detail="connected", index_stats=None,
        llm_configured=False,
    )
    assert empty["database"].status == "CONNECTED"
    assert empty["retrieval"].status == "DEGRADED"
    assert empty["embeddings"].status == "NOT CONFIGURED"

    # Full coverage → operational; partial coverage → honest DEGRADED ratio.
    full = compute_statuses(
        db_connected=True, db_detail="connected",
        index_stats={"total_units": 10, "embedded_units": 10},
        llm_configured=False,
    )
    assert full["retrieval"].status == "OPERATIONAL"
    assert full["embeddings"].status == "OPERATIONAL"
    partial = compute_statuses(
        db_connected=True, db_detail="connected",
        index_stats={"total_units": 10, "embedded_units": 4},
        llm_configured=False,
    )
    assert partial["embeddings"].status == "DEGRADED"
    assert "4/10" in partial["embeddings"].detail

    # LLM configured flips only the llm row — nothing else pretends health.
    llm_up = compute_statuses(
        db_connected=True, db_detail="connected",
        index_stats={"total_units": 10, "embedded_units": 10},
        llm_configured=True,
    )
    assert llm_up["llm"].status == "OPERATIONAL"
    assert llm_up["retrieval"].status == "OPERATIONAL"


def test_statuses_endpoint_reflects_database_outage_honestly(
    api_client, monkeypatch,
):
    import app.api.routes.dashboard as dashboard_route

    monkeypatch.setattr(
        dashboard_route, "probe_database", lambda: (False, "unavailable")
    )
    body = api_client.get("/api/dashboard/statuses").json()
    assert body["data_available"] is False
    assert body["api"]["status"] == "OPERATIONAL"  # API itself is up
    assert body["database"]["status"] == "UNAVAILABLE"
    assert body["retrieval"]["status"] == "UNAVAILABLE"
    assert body["embeddings"]["status"] == "UNAVAILABLE"
    assert body["llm"]["status"] == "NOT CONFIGURED"  # no credentials here


# --- Phase 14: demo seed / reset safety (static — needs live DB to execute) -------


def test_seed_script_inserts_demo_labelled_data_only():
    src = _read("scripts/seed_demo_data.py")
    # Everything user-visible is DEMO_-prefixed:
    assert 'DEMO_FILENAME = "DEMO_borehole_log.pdf"' in src
    assert 'storage_reference="demo/DEMO_borehole_log.pdf"' in src
    assert 'source="demo_seed"' in src  # provenance: never real-source data
    import re

    for field, value in re.findall(
        r'(entity_name|metric_name|reporting_period|unit)\s*=\s*"([^"]*)"', src
    ):
        assert value.startswith("DEMO_"), (field, value)
    # Audit trail records the seeding event itself:
    assert 'action="seed.demo_data_loaded"' in src
    assert '"demo": True' in src
    assert "not real" in src.lower()


def test_seed_reset_is_scoped_to_demo_data_never_source_code_or_schema():
    src = _read("scripts/seed_demo_data.py")
    reset_src = src[src.index("def reset()"):]
    # Reset deletes exactly the previous DEMO document (cascades scoped to it):
    assert "previous_demo_document(session)" in reset_src
    assert "No DEMO data found" in reset_src
    # Never destructive beyond the DEMO rows:
    lowered = reset_src.lower()
    for banned in ("drop_all", "create_all", "truncate", "drop table",
                   "rm -rf", "rmtree", "unlink(", ".env", "alembic"):
        assert banned not in lowered, banned


# --- Phase 6: migration chain static validation (regression) ----------------------


def test_migration_chain_and_initial_ddl_checks_still_pass():
    """Alembic runtime upgrade (0001→0006) is NOT VERIFIED without PostgreSQL;
    the chain-order and DDL-parity checks remain executable statically."""
    from tests.test_models import (
        test_metadata_matches_initial_migration_ddl,
        test_migration_revisions_chain,
    )

    test_migration_revisions_chain()
    test_metadata_matches_initial_migration_ddl()

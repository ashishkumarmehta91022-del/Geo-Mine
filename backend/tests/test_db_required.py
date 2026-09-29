"""Database integration tests — REQUIRE PostgreSQL (see conftest.py for the
skip contract). Run with:

    CMPDI_TEST_DATABASE_URL=postgresql://... pytest -m db
"""

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.conftest import BACKEND_DIR, REPO_ROOT

pytestmark = pytest.mark.db


def test_alembic_upgrade_creates_all_foundation_tables(migrated_engine):
    inspector = inspect(migrated_engine)
    tables = set(inspector.get_table_names())
    assert {
        "documents",
        "document_pages",
        "extracted_records",
        "validation_results",
        "audit_logs",
    } <= tables
    with migrated_engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    # The stamped version must equal the chain head — computed from the
    # version files themselves (import-free: the local backend/alembic
    # migrations package intentionally shadows the alembic library here).
    import re

    versions_dir = BACKEND_DIR / "alembic" / "versions"
    revisions: set[str] = set()
    downs: set[str] = set()
    for path in versions_dir.glob("0*.py"):
        migration_src = path.read_text(encoding="utf-8")
        rev_match = re.search(r'^revision\s*=\s*"([^"]+)"', migration_src, re.M)
        down_match = re.search(r'^down_revision\s*=\s*"([^"]+)"', migration_src, re.M)
        if rev_match:
            revisions.add(rev_match.group(1))
            if down_match:
                downs.add(down_match.group(1))
    head = revisions - downs
    assert len(head) == 1, f"expected exactly one head, got {head}"
    assert version == head.pop()


def test_alembic_downgrade_and_upgrade_roundtrip(pg_url: str, migrated_engine):
    """downgrade to base then back to head — proves the migration is reproducible."""
    from tests.conftest import run_alembic

    os.environ["ALEMBIC_DATABASE_URL"] = pg_url
    run_alembic("downgrade", "base")
    inspector = inspect(migrated_engine)
    assert not {"documents", "extracted_records"} & set(inspector.get_table_names())

    run_alembic("upgrade", "head")
    inspector = inspect(migrated_engine)
    assert "extracted_records" in inspector.get_table_names()
    os.environ.pop("ALEMBIC_DATABASE_URL", None)


def test_seed_script_is_idempotent_and_resettable(pg_url: str, migrated_engine):
    env = os.environ.copy()
    env["DATABASE_URL"] = pg_url  # consumed by app.config inside the subprocess

    def run_seed(*args: str):
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "seed_demo_data.py"), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
            timeout=60,
        )

    first = run_seed()
    assert first.returncode == 0, first.stderr
    assert "DEMO data inserted" in first.stdout

    # Idempotent: a second run must not duplicate rows.
    second = run_seed()
    assert second.returncode == 0, second.stderr
    assert "already present" in second.stdout

    with migrated_engine.connect() as conn:
        documents = conn.execute(text("SELECT count(*) FROM documents")).scalar()
        records = conn.execute(text("SELECT count(*) FROM extracted_records")).scalar()
    assert documents == 1
    assert records == 3

    reset = run_seed("--reset")
    assert reset.returncode == 0, reset.stderr
    with migrated_engine.connect() as conn:
        documents = conn.execute(text("SELECT count(*) FROM documents")).scalar()
    assert documents == 0


def test_health_reports_connected_against_live_postgres(pg_url: str, migrated_engine, monkeypatch):
    """With PostgreSQL reachable, /api/health must report database.connected=true."""
    import app.db as app_db
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(app_db, "engine", create_engine(pg_url))
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    database = response.json()["database"]
    assert database["connected"] is True
    assert database["detail"] == "connected"


def test_get_db_dependency_yields_working_session(pg_url: str, migrated_engine):
    import app.db as app_db
    from sqlalchemy import text

    session_generator = app_db.get_db()
    session = next(session_generator)
    try:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        session_generator.close()

"""Database integration tests — REQUIRE a reachable PostgreSQL with migrations applied.

These tests are honestly separated: they SKIP (never fake-pass) when
CMPDI_TEST_DATABASE_URL is unset or the database is unreachable.

Run them with (after `alembic upgrade head` on a dev database):

    CMPDI_TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/cmpdi_reporting pytest -m db

The test database is cleaned and re-migrated by fixtures here.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

pytestmark = pytest.mark.db


def _test_database_url() -> str | None:
    return os.environ.get("CMPDI_TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def pg_url() -> str:
    """Skip the whole module unless PostgreSQL is explicitly provided AND reachable."""
    url = _test_database_url()
    if not url:
        pytest.skip("CMPDI_TEST_DATABASE_URL not set — PostgreSQL integration tests skipped", allow_module_level=False)
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL unreachable ({exc.__class__.__name__}) — integration tests skipped")
    finally:
        engine.dispose()
    return url


@pytest.fixture(scope="module")
def migrated_engine(pg_url: str):
    """Clean the test database, run Alembic migrations, yield a live engine."""
    from alembic import command
    from alembic.config import Config

    os.environ["ALEMBIC_DATABASE_URL"] = pg_url
    app_engine = create_engine(pg_url)

    # Start from a clean slate.
    from app.models import Base

    Base.metadata.drop_all(app_engine)
    with app_engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")

    yield app_engine

    app_engine.dispose()


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
    version = migrated_engine.connect().execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "0001_initial_schema"


def test_alembic_downgrade_and_upgrade_roundtrip(pg_url: str, migrated_engine):
    """downgrade to base then back to head — proves the migration is reproducible."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    command.downgrade(alembic_cfg, "base")
    inspector = inspect(migrated_engine)
    assert not {"documents", "extracted_records"} & set(inspector.get_table_names())

    command.upgrade(alembic_cfg, "head")
    inspector = inspect(migrated_engine)
    assert "extracted_records" in inspector.get_table_names()


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

    session_generator = app_db.get_db()
    session = next(session_generator)
    try:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        session_generator.close()

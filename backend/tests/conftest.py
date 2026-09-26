"""Shared fixtures for PostgreSQL-dependent integration tests.

Honest-skip contract: tests using these fixtures SKIP (never fake-pass) when
CMPDI_TEST_DATABASE_URL is unset or the database is unreachable.

The test database is used DESTRUCTIVELY (tables are dropped and re-migrated),
so point CMPDI_TEST_DATABASE_URL at a dedicated test database, e.g.:

    CMPDI_TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/cmpdi_reporting pytest -m db
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def _test_database_url() -> str | None:
    return os.environ.get("CMPDI_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def pg_url() -> str:
    """Skip unless PostgreSQL is explicitly provided AND reachable."""
    url = _test_database_url()
    if not url:
        pytest.skip("CMPDI_TEST_DATABASE_URL not set — PostgreSQL integration tests skipped")
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL unreachable ({exc.__class__.__name__}) — integration tests skipped")
    finally:
        engine.dispose()
    return url


@pytest.fixture(scope="session")
def migrated_engine(pg_url: str):
    """Clean the test database, run Alembic migrations, yield a live engine."""
    from alembic import command
    from alembic.config import Config

    from app.models import Base

    os.environ["ALEMBIC_DATABASE_URL"] = pg_url
    app_engine = create_engine(pg_url)

    # Start from a clean slate (only this project's tables + alembic bookkeeping).
    inspector = inspect(app_engine)
    existing = [t for t in inspector.get_table_names() if t in Base.metadata.tables or t == "alembic_version"]
    if existing:
        Base.metadata.drop_all(app_engine)
        with app_engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            conn.commit()

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")

    yield app_engine

    app_engine.dispose()


@pytest.fixture()
def client(migrated_engine, monkeypatch, tmp_path):
    """TestClient with isolated temp storage; truncates all tables per test."""
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    import app.api.routes.documents as documents_route
    import app.api.routes.processing as processing_route
    from app.config import settings
    from app.main import app
    from app.services.document_storage import LocalFileStorage

    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "documents"))
    monkeypatch.setattr(documents_route, "_storage", LocalFileStorage(str(tmp_path / "documents")))
    monkeypatch.setattr(processing_route, "_storage", LocalFileStorage(str(tmp_path / "documents")))

    with TestClient(app) as test_client:
        yield test_client

    with migrated_engine.connect() as conn:
        conn.execute(
            text(
                "TRUNCATE documents, document_pages, extracted_records, "
                "validation_results, audit_logs RESTART IDENTITY CASCADE"
            )
        )
        conn.commit()

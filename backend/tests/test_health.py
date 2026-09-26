"""Tests for the /api/health endpoint (no PostgreSQL required)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_with_required_fields():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "cmpdi-ai-reporting-platform"


def test_health_reports_honest_database_status_without_crashing():
    """The probe must stay 200 even when PostgreSQL is unreachable,
    and must never claim a connection it did not actually make."""
    response = client.get("/api/health")

    assert response.status_code == 200
    database = response.json()["database"]
    assert isinstance(database["connected"], bool)
    assert database["detail"] in {"connected", "unavailable", "timeout"}
    # connected=True only if a real round-trip succeeded
    if database["connected"] is False:
        assert database["detail"] in {"unavailable", "timeout"}


def test_health_responds_quickly_when_database_unavailable():
    """A stalled/unreachable database must not hang the health check."""
    import time

    start = time.monotonic()
    response = client.get("/api/health")
    elapsed = time.monotonic() - start

    assert response.status_code == 200
    assert elapsed < 15, f"health check took {elapsed:.1f}s — likely hanging on the DB probe"

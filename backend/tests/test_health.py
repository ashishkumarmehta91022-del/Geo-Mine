"""Tests for the /api/health endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_with_required_fields():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "cmpdi-ai-reporting-platform"


def test_health_reports_database_status_without_crashing():
    """The probe must stay 200 even when PostgreSQL is unreachable."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["database"] in {"up", "down"}

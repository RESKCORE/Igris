"""Smoke test for /health endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_health_check() -> None:
    """Verify that /health returns status ok and default simulation mode."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mode"] == "simulation"
    assert data["database"] == "connected"


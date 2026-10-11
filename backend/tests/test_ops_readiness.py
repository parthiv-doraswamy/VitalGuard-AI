from fastapi.testclient import TestClient
import pytest

from app.main import app
from auth_helpers import authenticate_test_client


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "readiness.sqlite3"))
    with TestClient(app) as test_client:
        authenticate_test_client(test_client)
        yield test_client


def test_readiness_is_authenticated_and_secret_free(client):
    response = client.get("/api/v1/ops/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["operator_auth_configured"] is True
    assert body["checks"]["model_loaded"] is True
    assert body["checks"]["websocket_transport"] == "process_local_best_effort"
    assert body["demo_only"] is True
    assert body["clinically_validated"] is False
    assert "VITALGUARD_AUTH_SECRET" not in response.text


def test_readiness_requires_authentication(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "unauth.sqlite3"))
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/ops/readiness")
    assert response.status_code == 401


def test_readiness_reports_missing_auth_configuration(client, monkeypatch):
    monkeypatch.delenv("VITALGUARD_AUTH_SECRET", raising=False)
    response = client.get("/api/v1/ops/readiness")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["operator_auth_configured"] is False

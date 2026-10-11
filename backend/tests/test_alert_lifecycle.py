from fastapi.testclient import TestClient
import pytest
from app.main import app
from auth_helpers import authenticate_test_client
from app.alert_service import create_alert

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "alerts.sqlite3"))
    with TestClient(app) as test_client:
        authenticate_test_client(test_client)
        yield test_client

def seed_alert():
    return create_alert(patient_id="DEMO-ALERT-01", event_key="test:event:1",
        severity="high", title="High demo risk", details={"risk_score": 77, "demo_only": True})

def test_alert_creation_is_idempotent(client):
    first = seed_alert()
    second = seed_alert()
    assert first["id"] == second["id"]
    response = client.get("/api/v1/alerts", params={"status": "open"})
    assert response.status_code == 200
    assert response.json()["count"] == 1

def test_acknowledge_resolve_and_audit(client):
    alert = seed_alert()
    alert_id = alert["id"]
    ack = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"actor": "demo-nurse"})
    assert ack.status_code == 200
    assert ack.json()["item"]["status"] == "acknowledged"
    assert ack.json()["item"]["acknowledged_by"] == "demo-operator"

    resolved = client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"actor": "demo-nurse"})
    assert resolved.status_code == 200
    assert resolved.json()["item"]["status"] == "resolved"

    audit = client.get(f"/api/v1/alerts/{alert_id}/audit")
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()["items"]]
    assert actions == ["created", "acknowledged", "resolved"]

def test_unknown_alert_returns_404(client):
    response = client.post("/api/v1/alerts/99999/resolve", json={"actor": "demo-operator"})
    assert response.status_code == 404

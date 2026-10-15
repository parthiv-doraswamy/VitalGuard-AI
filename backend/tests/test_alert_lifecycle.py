from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.alert_service import create_alert
from conftest import auth_headers

AUTH = auth_headers()

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "alerts.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client

def seed_alert():
    return create_alert(patient_id="DEMO-ALERT-01", event_key="test:event:1",
        severity="high", title="High demo risk", details={"risk_score": 77, "demo_only": True})

def test_alert_creation_is_idempotent(client):
    first = seed_alert()
    second = seed_alert()
    assert first["id"] == second["id"]
    response = client.get("/api/v1/alerts", headers=AUTH, params={"status": "open"})
    assert response.status_code == 200
    assert response.json()["count"] == 1

def test_acknowledge_resolve_and_audit(client):
    alert = seed_alert()
    alert_id = alert["id"]
    nurse = auth_headers("nurse.demo")
    # The audit actor is the signed-in user, never a name supplied in the request body.
    ack = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=nurse, json={"actor": "someone-else"})
    assert ack.status_code == 200
    assert ack.json()["item"]["status"] == "acknowledged"
    assert ack.json()["item"]["acknowledged_by"] == "nurse.demo"

    assert client.post(f"/api/v1/alerts/{alert_id}/resolve", headers=nurse, json={}).status_code == 403
    resolved = client.post(f"/api/v1/alerts/{alert_id}/resolve", headers=AUTH, json={"actor": "demo-nurse"})
    assert resolved.status_code == 200
    assert resolved.json()["item"]["status"] == "resolved"

    audit = client.get(f"/api/v1/alerts/{alert_id}/audit", headers=AUTH)
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()["items"]]
    assert actions == ["created", "acknowledged", "resolved"]

def test_unknown_alert_returns_404(client):
    response = client.post("/api/v1/alerts/99999/resolve", headers=AUTH, json={"actor": "demo-operator"})
    assert response.status_code == 404


def test_alert_endpoints_require_sign_in(client):
    alert = seed_alert()
    assert client.get("/api/v1/alerts").status_code == 401
    assert client.post(f"/api/v1/alerts/{alert['id']}/acknowledge", json={}).status_code == 401
    assert client.get("/api/v1/alerts", headers={"Authorization": "Bearer forged.token"}).status_code == 401


def test_doctors_only_see_and_act_on_their_assigned_patients(client):
    # P-SIM-003 (ICU) is assigned to doctor.demo; dr.khan covers Emergency.
    own = create_alert(patient_id="P-SIM-003", event_key="test:own", severity="high", title="Own", details={})
    other = create_alert(patient_id="P-SIM-004", event_key="test:other", severity="high", title="Other", details={})
    owner, outsider = auth_headers("doctor.demo"), auth_headers("dr.khan")

    listed = client.get("/api/v1/alerts", headers=owner).json()["items"]
    assert [item["patient_id"] for item in listed] == ["P-SIM-003"]
    assert client.get("/api/v1/alerts", headers=owner, params={"patient_id": "P-SIM-004"}).status_code == 403
    assert client.post(f"/api/v1/alerts/{other['id']}/acknowledge", headers=owner, json={}).status_code == 403
    assert client.post(f"/api/v1/alerts/{own['id']}/resolve", headers=outsider, json={}).status_code == 403
    resolved = client.post(f"/api/v1/alerts/{own['id']}/resolve", headers=owner, json={})
    assert resolved.status_code == 200 and resolved.json()["item"]["status"] == "resolved"
    # Nurses see alerts for every patient.
    assert client.get("/api/v1/alerts", headers=auth_headers("nurse.demo")).json()["count"] == 2

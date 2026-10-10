from fastapi.testclient import TestClient
from app.main import app
from app.alert_service import create_alert, transition_alert


def test_patient_timeline_combines_persisted_events(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "timeline.sqlite3"))
    with TestClient(app) as client:
        payload = {
            "patient_id": "DEMO-TIMELINE-001", "age": 58, "heart_rate": 82,
            "spo2": 98, "systolic_bp": 122, "diastolic_bp": 78,
            "temperature": 37, "respiratory_rate": 16,
        }
        prediction = client.post("/api/v1/risk/predict", json=payload)
        assert prediction.status_code == 200

        alert = create_alert(
            patient_id="DEMO-TIMELINE-001",
            event_key="timeline-test-event",
            severity="high",
            title="Synthetic timeline alert",
            details={"demo_only": True},
        )
        assert alert is not None
        transition_alert(alert["id"], "acknowledge", "timeline-demo-operator")
        transition_alert(alert["id"], "resolve", "timeline-demo-operator")

        response = client.get("/api/v1/patients/DEMO-TIMELINE-001/timeline?limit=20")

    assert response.status_code == 200
    body = response.json()
    assert body["demo_only"] is True
    assert body["patient_id"] == "DEMO-TIMELINE-001"
    types = {item["type"] for item in body["items"]}
    assert {"observation", "alert", "alert_audit"}.issubset(types)
    assert body["available_event_count"] >= 5
    assert body["count"] == len(body["items"])
    assert all(item["demo_only"] is True for item in body["items"])


def test_patient_timeline_limit_is_bounded():
    with TestClient(app) as client:
        response = client.get("/api/v1/patients/DEMO-001/timeline?limit=101")
    assert response.status_code == 422

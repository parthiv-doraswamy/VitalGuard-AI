from fastapi.testclient import TestClient
import pytest
from app.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "live.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client

def test_websocket_receives_observation_only_after_ingestion(client):
    with client.websocket_connect("/api/v1/live") as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "connected"
        response = client.post("/api/v1/demo/observations",
            json={"patient_id": "DEMO-WS-001", "scenario": "worsening", "step": 2})
        assert response.status_code == 200
        event = websocket.receive_json()
        assert event["type"] == "observation.created"
        assert event["event_id"] == response.json()["observation_id"]
        assert event["patient_id"] == "DEMO-WS-001"
        assert event["demo_only"] is True

def test_websocket_heartbeat(client):
    with client.websocket_connect("/api/v1/live") as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_text("ping")
        assert websocket.receive_json()["type"] == "pong"

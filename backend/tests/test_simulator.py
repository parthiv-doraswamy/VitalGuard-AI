from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.simulator import observation_for_step

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "simulator.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client

@pytest.mark.parametrize("scenario", ["stable", "worsening", "recovering"])
def test_scenarios_are_repeatable(scenario):
    assert observation_for_step(scenario, 2) == observation_for_step(scenario, 2)

def test_worsening_scenario_trends():
    early, later = observation_for_step("worsening", 0), observation_for_step("worsening", 4)
    assert later["heart_rate"] > early["heart_rate"]
    assert later["spo2"] < early["spo2"]
    assert later["systolic_bp"] < early["systolic_bp"]
    assert later["respiratory_rate"] > early["respiratory_rate"]

def test_recovery_scenario_trends():
    early, later = observation_for_step("recovering", 0), observation_for_step("recovering", 6)
    assert later["heart_rate"] < early["heart_rate"]
    assert later["spo2"] > early["spo2"]
    assert later["systolic_bp"] > early["systolic_bp"]

def test_ingestion_persists_observation(client):
    response = client.post("/api/v1/demo/observations",
        json={"patient_id": "DEMO-LIVE-007", "scenario": "worsening", "step": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["observation_id"] > 0 and body["demo_only"] is True
    history = client.get("/api/v1/observations", params={"patient_id": "DEMO-LIVE-007"})
    assert history.status_code == 200 and history.json()["count"] == 1
    assert history.json()["items"][0]["inputs"]["spo2"] == 91

def test_ingestion_rejects_invalid_requests(client):
    unknown = client.post("/api/v1/demo/observations",
        json={"scenario": "stable", "step": 0, "extra": "no"})
    invalid = client.post("/api/v1/demo/observations",
        json={"scenario": "unknown", "step": -1})
    assert unknown.status_code == 422 and invalid.status_code == 422


# --- Live-demo streams reuse the same deterministic simulator ---------------------------
from app import stream_service


@pytest.fixture
def stream_client(client, monkeypatch):
    monkeypatch.setattr(stream_service, "MIN_EMIT_GAP_SECONDS", 0)
    return client


def _stream(client, scenario, count):
    session = client.post("/api/v1/live-demo/sessions", json={"scenario": scenario, "takeover": True}).json()
    headers = {"X-Producer-Token": session["producer_token"]}
    path = f"/api/v1/live-demo/sessions/{session['session']['session_id']}/observations"
    return [client.post(path, json={"sequence": sequence}, headers=headers).json()["event"] for sequence in range(count)]


@pytest.mark.parametrize("scenario", ["stable", "worsening", "recovering"])
def test_stream_observations_come_from_the_backend_simulator(stream_client, scenario):
    events = _stream(stream_client, scenario, 4)
    assert [event["observation"] for event in events] == [observation_for_step(scenario, step) for step in range(4)]
    assert all(event["patient_id"].startswith("DEMO-STREAM-") for event in events)


def test_stream_scores_follow_the_scenario_direction(stream_client):
    worsening = [event["prediction"]["risk_score"] for event in _stream(stream_client, "worsening", 6)]
    recovering = [event["prediction"]["risk_score"] for event in _stream(stream_client, "recovering", 6)]
    stable = [event["prediction"]["risk_score"] for event in _stream(stream_client, "stable", 6)]
    assert worsening[-1] > worsening[0]
    assert recovering[-1] < recovering[0]
    assert max(stable) - min(stable) <= 10


@pytest.mark.parametrize("body", [
    {"scenario": "unknown"},
    {"scenario": "stable", "interval_ms": 100},
    {"scenario": "stable", "interval_ms": 60000},
    {"scenario": "stable", "patient_id": "bad id with spaces"},
    {"scenario": "stable", "extra": True},
])
def test_invalid_stream_requests_are_rejected(client, body):
    assert client.post("/api/v1/live-demo/sessions", json=body).status_code == 422


def test_invalid_sequence_is_rejected(client):
    session = client.post("/api/v1/live-demo/sessions", json={"scenario": "stable"}).json()
    path = f"/api/v1/live-demo/sessions/{session['session']['session_id']}/observations"
    headers = {"X-Producer-Token": session["producer_token"]}
    for sequence in (-1, 1001, "zero"):
        assert client.post(path, json={"sequence": sequence}, headers=headers).status_code == 422

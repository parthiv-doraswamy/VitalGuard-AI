from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from auth_helpers import authenticate_test_client


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "ingestion.sqlite3"))
    with TestClient(app) as test_client:
        authenticate_test_client(test_client)
        yield test_client


def item(event_id="source-event-001", **updates):
    payload = {
        "source_system": "synthetic-demo",
        "source_event_id": event_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "observation": {
            "patient_id": "DEMO-INGEST-001",
            "age": 58,
            "heart_rate": 82,
            "spo2": 98,
            "systolic_bp": 122,
            "diastolic_bp": 78,
            "temperature": 37.0,
            "respiratory_rate": 16,
        },
        "units": {
            "age": "years",
            "heart_rate": "bpm",
            "spo2": "percent",
            "systolic_bp": "mmHg",
            "diastolic_bp": "mmHg",
            "temperature": "degC",
            "respiratory_rate": "breaths/min",
        },
    }
    payload.update(updates)
    return payload


def test_batch_ingestion_accepts_valid_record_and_persists_provenance(client):
    response = client.post("/api/v1/ingestion/batch", json={"records": [item()]})
    assert response.status_code == 200
    body = response.json()
    assert (body["accepted"], body["duplicates"], body["rejected"]) == (1, 0, 0)
    record = body["items"][0]
    assert record["status"] == "accepted"
    assert record["observation_id"] > 0
    assert record["source_event_id"] == "source-event-001"
    assert record["demo_only"] is True


def test_batch_ingestion_is_idempotent_for_same_source_event(client):
    payload = {"records": [item()]}
    first = client.post("/api/v1/ingestion/batch", json=payload)
    second = client.post("/api/v1/ingestion/batch", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["items"][0]["observation_id"] == second.json()["items"][0]["observation_id"]
    assert second.json()["duplicates"] == 1
    assert second.json()["accepted"] == 0


def test_batch_ingestion_keeps_valid_records_when_peer_is_invalid(client):
    valid = item("valid-event")
    invalid = item("invalid-event", units={"heart_rate": "beats"})
    response = client.post("/api/v1/ingestion/batch", json={"records": [valid, invalid]})
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 1
    assert body["items"][1]["status"] == "rejected"
    assert body["items"][1]["errors"]


@pytest.mark.parametrize("change", [
    {"observation": {"patient_id": "PATIENT-REAL-1", "age": 58, "heart_rate": 82, "spo2": 98,
        "systolic_bp": 122, "diastolic_bp": 78, "temperature": 37, "respiratory_rate": 16}},
    {"observed_at": "2026-10-11T10:00:00"},
    {"source_system": "hospital-feed"},
])
def test_batch_ingestion_rejects_non_demo_or_untrusted_metadata(client, change):
    response = client.post("/api/v1/ingestion/batch", json={"records": [item("bad-event", **change)]})
    assert response.status_code == 200
    assert response.json()["rejected"] == 1
    assert response.json()["items"][0]["status"] == "rejected"


def test_batch_ingestion_requires_authentication():
    with TestClient(app) as unauthenticated:
        response = unauthenticated.post("/api/v1/ingestion/batch", json={"records": [item()]})
    assert response.status_code == 503 or response.status_code == 401

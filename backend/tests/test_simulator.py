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
def test_simulator_returns_repeatable_observations(scenario):
    assert observation_for_step(scenario, 2) == observation_for_step(scenario, 2)


def test_worsening_scenario_changes_over_time():
    early = observation_for_step("worsening", 0)
    later = observation_for_step("worsening", 4)
    assert later["heart_rate"] > early["heart_rate"]
    assert later["spo2"] < early["spo2"]
    assert later["systolic_bp"] < early["systolic_bp"]
    assert later["respiratory_rate"] > early["respiratory_rate"]


def test_recovery_scenario_moves_toward_stable_values():
    early = observation_for_step("recovering", 0)
    later = observation_for_step("recovering", 6)
    assert later["heart_rate"] < early["heart_rate"]
    assert later["spo2"] > early["spo2"]
    assert later["systolic_bp"] > early["systolic_bp"]


def test_demo_ingestion_scores_and_persists_observation(client):
    response = client.post(
        "/api/v1/demo/observations",
        json={"patient_id": "DEMO-LIVE-007", "scenario": "worsening", "step": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] == "DEMO-LIVE-007"
    assert body["observation_id"] > 0
    assert body["demo_only"] is True

    history = client.get(
        "/api/v1/observations", params={"patient_id": "DEMO-LIVE-007"}
    )
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"][0]["inputs"]["spo2"] == 91


def test_demo_ingestion_rejects_unknown_fields(client):
    response = client.post(
        "/api/v1/demo/observations",
        json={
            "patient_id": "DEMO-LIVE-008",
            "scenario": "stable",
            "step": 0,
            "extra": "not-allowed",
        },
    )
    assert response.status_code == 422


def test_demo_ingestion_rejects_invalid_scenario_and_step(client):
    invalid_scenario = client.post(
        "/api/v1/demo/observations", json={"scenario": "random", "step": 0}
    )
    invalid_step = client.post(
        "/api/v1/demo/observations", json={"scenario": "stable", "step": -1}
    )
    assert invalid_scenario.status_code == 422
    assert invalid_step.status_code == 422

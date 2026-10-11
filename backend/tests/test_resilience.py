from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from auth_helpers import authenticate_test_client


def valid_payload(index: int):
    return {
        "patient_id": f"DEMO-LOAD-{index:03d}",
        "age": 58,
        "heart_rate": 82 + (index % 5),
        "spo2": 98,
        "systolic_bp": 122,
        "diastolic_bp": 78,
        "temperature": 37.0,
        "respiratory_rate": 16,
    }


def test_burst_predictions_remain_valid_and_history_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "burst.sqlite3"))
    with TestClient(app) as client:
        authenticate_test_client(client)

        # A deterministic burst catches regressions in repeated persistence/API handling.
        results = [client.post("/api/v1/risk/predict", json=valid_payload(i)) for i in range(25)]
        assert all(response.status_code == 200 for response in results)
        ids = [response.json()["observation_id"] for response in results]
        assert len(set(ids)) == 25

        page = client.get("/api/v1/observations", params={"limit": 10})
        assert page.status_code == 200
        assert page.json()["count"] == 10
        assert page.json()["next_before_id"] is not None

        metrics = client.get("/api/v1/ops/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["request_count"] >= 28


def test_synthetic_observation_survives_application_restart(tmp_path, monkeypatch):
    db_path = tmp_path / "restart.sqlite3"
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(db_path))

    with TestClient(app) as first_client:
        authenticate_test_client(first_client)
        created = first_client.post("/api/v1/risk/predict", json=valid_payload(77))
        assert created.status_code == 200
        observation_id = created.json()["observation_id"]

    # A fresh TestClient starts a new app lifespan against the same persistent file.
    with TestClient(app) as restarted_client:
        authenticate_test_client(restarted_client)
        history = restarted_client.get(
            "/api/v1/observations",
            params={"patient_id": "DEMO-LOAD-077", "limit": 10},
        )
        assert history.status_code == 200
        assert history.json()["count"] == 1
        assert history.json()["items"][0]["id"] == observation_id


def test_invalid_burst_does_not_create_observations(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "invalid-burst.sqlite3"))
    with TestClient(app) as client:
        authenticate_test_client(client)
        invalid_payload = valid_payload(88)
        invalid_payload["spo2"] = 140

        responses = [client.post("/api/v1/risk/predict", json=invalid_payload) for _ in range(10)]
        assert all(response.status_code == 422 for response in responses)
        history = client.get("/api/v1/observations", params={"limit": 10})
        assert history.status_code == 200
        assert history.json()["count"] == 0

from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate each test so no local or deployed demo history leaks between tests.
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "test.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


def valid_payload():
    return {
        "patient_id": "DEMO-001",
        "age": 58,
        "heart_rate": 82,
        "spo2": 98,
        "systolic_bp": 122,
        "diastolic_bp": 78,
        "temperature": 37.0,
        "respiratory_rate": 16,
    }


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["demo_only"] is True


def test_model_info_is_explicit_about_synthetic_data(client):
    response = client.get("/api/v1/model/info")
    assert response.status_code == 200
    assert response.json()["clinically_validated"] is False
    assert response.json()["training_data"] == "generated synthetic observations only"


def test_prediction_is_saved_and_returns_observation_metadata(client):
    response = client.post("/api/v1/risk/predict", json=valid_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] == "DEMO-001"
    assert 0 <= body["risk_score"] <= 100
    assert body["risk_level"] in {"low", "moderate", "high", "critical"}
    assert 0 <= body["model_probability"] <= 1
    assert body["demo_only"] is True
    assert isinstance(body["factors"], list)
    assert body["observation_id"] > 0
    assert body["created_at"]

    history = client.get("/api/v1/observations", params={"patient_id": "DEMO-001"})
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"][0]["id"] == body["observation_id"]
    assert history.json()["items"][0]["inputs"]["spo2"] == 98


def test_history_can_filter_patient_and_limit(client):
    client.post("/api/v1/risk/predict", json=valid_payload())
    other = valid_payload()
    other["patient_id"] = "DEMO-002"
    client.post("/api/v1/risk/predict", json=other)

    first = client.get("/api/v1/observations", params={"patient_id": "DEMO-001", "limit": 1})
    assert first.status_code == 200
    assert first.json()["count"] == 1
    assert first.json()["items"][0]["patient_id"] == "DEMO-001"

    all_records = client.get("/api/v1/observations", params={"limit": 1})
    assert all_records.json()["count"] == 1
    assert all_records.json()["next_before_id"] is not None


def test_invalid_vitals_are_rejected(client):
    payload = valid_payload()
    payload["spo2"] = 140
    response = client.post("/api/v1/risk/predict", json=payload)
    assert response.status_code == 422


def test_diastolic_pressure_must_be_lower_than_systolic(client):
    payload = valid_payload()
    payload["diastolic_bp"] = 130
    response = client.post("/api/v1/risk/predict", json=payload)
    assert response.status_code == 422


def test_history_limit_is_bounded(client):
    response = client.get("/api/v1/observations", params={"limit": 101})
    assert response.status_code == 422



def test_postgres_database_url_is_normalized(monkeypatch):
    from app.storage import _database_url

    monkeypatch.setenv("DATABASE_URL", "postgres://demo:secret@localhost:5432/vitalguard")
    assert _database_url() == "postgresql+psycopg://demo:secret@localhost:5432/vitalguard"


def test_configured_sqlite_database_url_is_supported(tmp_path, monkeypatch):
    from app.storage import list_observations, save_observation

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'configured.sqlite3'}")
    monkeypatch.delenv("VITALGUARD_DB_PATH", raising=False)

    saved = save_observation(
        "DEMO-DB-URL",
        {"age": 58, "spo2": 98},
        {"model_version": "test-model", "risk_score": 12},
    )
    rows = list_observations(patient_id="DEMO-DB-URL", limit=10)

    assert saved["id"] > 0
    assert len(rows) == 1
    assert rows[0]["inputs"]["spo2"] == 98
    assert rows[0]["prediction"]["risk_score"] == 12


def test_api_returns_baseline_security_headers_and_request_id(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
    assert len(response.headers["x-request-id"]) == 36


def test_auth_login_fails_closed_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("VITALGUARD_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("VITALGUARD_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("VITALGUARD_AUTH_SECRET", raising=False)
    response = client.post("/api/v1/auth/login", json={"username": "demo", "password": "secret"})
    assert response.status_code == 503


def test_auth_login_and_identity_round_trip(client, monkeypatch):
    monkeypatch.setenv("VITALGUARD_AUTH_USERNAME", "demo-operator")
    monkeypatch.setenv("VITALGUARD_AUTH_PASSWORD", "a-long-demo-password")
    monkeypatch.setenv("VITALGUARD_AUTH_SECRET", "test-only-secret-that-is-at-least-32-chars")
    login = client.post("/api/v1/auth/login", json={
        "username": "demo-operator", "password": "a-long-demo-password"
    })
    assert login.status_code == 200
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    identity = client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {body['access_token']}"
    })
    assert identity.status_code == 200
    assert identity.json() == {"subject": "demo-operator", "authenticated": True}


def test_auth_rejects_invalid_credentials_and_tokens(client, monkeypatch):
    monkeypatch.setenv("VITALGUARD_AUTH_USERNAME", "demo-operator")
    monkeypatch.setenv("VITALGUARD_AUTH_PASSWORD", "a-long-demo-password")
    monkeypatch.setenv("VITALGUARD_AUTH_SECRET", "test-only-secret-that-is-at-least-32-chars")
    bad_login = client.post("/api/v1/auth/login", json={
        "username": "demo-operator", "password": "wrong-password"
    })
    assert bad_login.status_code == 401
    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    invalid = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer forged-token"})
    assert invalid.status_code == 401


def test_auth_login_rejects_unknown_fields(client, monkeypatch):
    monkeypatch.setenv("VITALGUARD_AUTH_USERNAME", "demo-operator")
    monkeypatch.setenv("VITALGUARD_AUTH_PASSWORD", "a-long-demo-password")
    monkeypatch.setenv("VITALGUARD_AUTH_SECRET", "test-only-secret-that-is-at-least-32-chars")
    response = client.post("/api/v1/auth/login", json={
        "username": "demo-operator", "password": "a-long-demo-password", "role": "admin"
    })
    assert response.status_code == 422

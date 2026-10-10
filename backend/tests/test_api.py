from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["demo_only"] is True


def test_model_info_is_explicit_about_synthetic_data():
    response = client.get("/api/v1/model/info")
    assert response.status_code == 200
    assert response.json()["clinically_validated"] is False
    assert response.json()["training_data"] == "generated synthetic observations only"


def test_prediction_response_contract():
    response = client.post("/api/v1/risk/predict", json=valid_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] == "DEMO-001"
    assert 0 <= body["risk_score"] <= 100
    assert body["risk_level"] in {"low", "moderate", "high", "critical"}
    assert 0 <= body["model_probability"] <= 1
    assert body["demo_only"] is True
    assert isinstance(body["factors"], list)


def test_invalid_vitals_are_rejected():
    payload = valid_payload()
    payload["spo2"] = 140
    response = client.post("/api/v1/risk/predict", json=payload)
    assert response.status_code == 422


def test_diastolic_pressure_must_be_lower_than_systolic():
    payload = valid_payload()
    payload["diastolic_bp"] = 130
    response = client.post("/api/v1/risk/predict", json=payload)
    assert response.status_code == 422

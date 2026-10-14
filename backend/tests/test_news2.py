import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.news2 import score_news2


def baseline(**updates):
    values = {
        "patient_id": "DEMO-NEWS2-TEST",
        "respiratory_rate": 16,
        "spo2": 98,
        "systolic_bp": 120,
        "heart_rate": 80,
        "temperature": 37.0,
        "consciousness": "alert",
        "supplemental_oxygen": False,
        "spo2_scale": 1,
        "scale2_authorized": False,
    }
    values.update(updates)
    return values


@pytest.mark.parametrize(("rr", "expected"), [(8, 3), (9, 1), (11, 1), (12, 0), (20, 0), (21, 2), (24, 2), (25, 3)])
def test_respiratory_rate_bands(rr, expected):
    result = score_news2(baseline(respiratory_rate=rr))
    assert result["parameter_scores"]["respiratory_rate"] == expected


@pytest.mark.parametrize(("spo2", "expected"), [(91, 3), (92, 2), (93, 2), (94, 1), (95, 1), (96, 0), (100, 0)])
def test_spo2_scale_1_bands(spo2, expected):
    result = score_news2(baseline(spo2=spo2))
    assert result["parameter_scores"]["spo2"] == expected


@pytest.mark.parametrize(("systolic", "expected"), [(90, 3), (91, 2), (100, 2), (101, 1), (110, 1), (111, 0), (219, 0), (220, 3)])
def test_systolic_pressure_bands(systolic, expected):
    result = score_news2(baseline(systolic_bp=systolic))
    assert result["parameter_scores"]["systolic_bp"] == expected


@pytest.mark.parametrize(("pulse", "expected"), [(40, 3), (41, 1), (50, 1), (51, 0), (90, 0), (91, 1), (110, 1), (111, 2), (130, 2), (131, 3)])
def test_pulse_bands(pulse, expected):
    result = score_news2(baseline(heart_rate=pulse))
    assert result["parameter_scores"]["heart_rate"] == expected


@pytest.mark.parametrize(("temperature", "expected"), [(35.0, 3), (35.1, 1), (36.0, 1), (36.1, 0), (38.0, 0), (38.1, 1), (39.0, 1), (39.1, 2)])
def test_temperature_bands(temperature, expected):
    result = score_news2(baseline(temperature=temperature))
    assert result["parameter_scores"]["temperature"] == expected


def test_oxygen_and_new_confusion_points_are_added():
    result = score_news2(baseline(supplemental_oxygen=True, consciousness="new_confusion"))
    assert result["parameter_scores"]["supplemental_oxygen"] == 2
    assert result["parameter_scores"]["consciousness"] == 3
    assert result["total_score"] == 5


def test_scale_2_air_and_oxygen_ranges():
    assert score_news2(baseline(spo2=92, spo2_scale=2, scale2_authorized=True))["parameter_scores"]["spo2"] == 0
    assert score_news2(baseline(spo2=94, spo2_scale=2, scale2_authorized=True, supplemental_oxygen=True))["parameter_scores"]["spo2"] == 1
    assert score_news2(baseline(spo2=97, spo2_scale=2, scale2_authorized=True, supplemental_oxygen=True))["parameter_scores"]["spo2"] == 3
    assert score_news2(baseline(spo2=93, spo2_scale=2, scale2_authorized=True, supplemental_oxygen=False))["parameter_scores"]["spo2"] == 0


def test_api_rejects_scale_2_without_authorization():
    with TestClient(app) as client:
        response = client.post("/api/v1/scores/news2", json=baseline(spo2_scale=2))
    assert response.status_code == 422


def test_api_returns_total_and_demo_disclaimer():
    with TestClient(app) as client:
        response = client.post("/api/v1/scores/news2", json=baseline())
    assert response.status_code == 200
    body = response.json()
    assert body["total_score"] == 0
    assert body["demo_only"] is True
    assert body["clinically_validated_implementation"] is False

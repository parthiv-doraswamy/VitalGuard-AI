from fastapi.testclient import TestClient

from app.main import app
from auth_helpers import authenticate_test_client


def test_metrics_requires_authentication():
    with TestClient(app) as client:
        response = client.get("/api/v1/ops/metrics")
    assert response.status_code == 401


def test_metrics_reports_aggregates_without_request_data(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "metrics.sqlite3"))
    with TestClient(app) as client:
        authenticate_test_client(client)
        before = client.get("/api/v1/ops/metrics")
        assert before.status_code == 200
        assert before.json()["demo_only"] is True

        # The route and status are aggregated; request query strings are never labels.
        client.get("/api/v1/model/info")
        response = client.get("/api/v1/ops/metrics?synthetic_query_marker=must_not_appear")
        assert response.status_code == 200
        body = response.json()
        assert body["request_count"] >= before.json()["request_count"]
        assert body["route_counts"].get("/api/v1/model/info", 0) >= 1
        assert body["status_counts"].get("200", 0) >= 1
        assert body["latency_ms"]["count"] == body["request_count"]
        assert body["latency_ms"]["mean"] >= 0
        assert body["scope"] == "current_process_since_startup"
        assert "synthetic_query_marker" not in response.text
        assert "patient_id" not in response.text
        assert "request_body" not in response.text

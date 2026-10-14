"""Durability, transaction and failure-handling tests for the storage layer.

Tests taking the `database` fixture run against SQLite and, when
VITALGUARD_TEST_POSTGRES_URL is set, against PostgreSQL as well.
"""
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from app import observation_service, storage
from app.alert_service import create_alert, list_alert_audit, transition_alert
from app.main import app
from app.storage import StorageConfigurationError, dispose_engines, get_engine, initialize_storage, save_observation
from app.storage_schema import alerts, audit_events, observations

ELEVATED = {"patient_id": "DEMO-PERSIST-001", "age": 70, "heart_rate": 180, "spo2": 78, "systolic_bp": 80,
            "diastolic_bp": 50, "temperature": 39.5, "respiratory_rate": 34}
NORMAL = {"patient_id": "DEMO-PERSIST-002", "age": 58, "heart_rate": 82, "spo2": 98, "systolic_bp": 122,
          "diastolic_bp": 78, "temperature": 37.0, "respiratory_rate": 16}


def _count(table) -> int:
    with get_engine().connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar()


def test_observation_alert_and_audit_survive_application_restart(database):
    with TestClient(app) as client:
        prediction = client.post("/api/v1/risk/predict", json=ELEVATED).json()
        alert = client.get("/api/v1/alerts", params={"patient_id": ELEVATED["patient_id"]}).json()["items"][0]
        client.post(f"/api/v1/alerts/{alert['id']}/acknowledge", json={"actor": "demo-nurse"})
        resolved = client.post(f"/api/v1/alerts/{alert['id']}/resolve", json={"actor": "demo-nurse"}).json()["item"]
    # Leaving the client runs shutdown, which disposes every pooled connection,
    # so the second app lifecycle reads only what the database itself kept.
    dispose_engines()
    with TestClient(app) as client:
        history = client.get("/api/v1/observations", params={"patient_id": ELEVATED["patient_id"]}).json()
        after = client.get("/api/v1/alerts", params={"patient_id": ELEVATED["patient_id"]}).json()["items"][0]
        audit = client.get(f"/api/v1/alerts/{alert['id']}/audit").json()
        health = client.get("/health").json()
    assert [item["id"] for item in history["items"]] == [prediction["observation_id"]]
    assert history["items"][0]["inputs"]["spo2"] == 78
    assert after == resolved
    assert after["acknowledged_at"] and after["resolved_at"]
    assert [item["action"] for item in audit["items"]] == ["created", "acknowledged", "resolved"]
    assert health["database"]["backend"] == database


def test_alert_failure_rolls_back_the_observation_and_publishes_nothing(database, monkeypatch):
    def failing_insert_alert(*_args, **_kwargs):
        raise OperationalError("INSERT INTO alerts", {}, Exception("simulated failure"))

    with TestClient(app) as client:
        monkeypatch.setattr(observation_service, "insert_alert", failing_insert_alert)
        with client.websocket_connect("/api/v1/live") as websocket:
            assert websocket.receive_json()["type"] == "connected"
            response = client.post("/api/v1/risk/predict", json=ELEVATED)
            websocket.send_text("ping")
            # The next frame must be the pong: no observation/alert event was sent.
            assert websocket.receive_json() == {"type": "pong"}
    assert response.status_code == 503
    assert response.json()["error"] == "database_unavailable"
    assert _count(observations) == 0
    assert _count(alerts) == 0
    assert _count(audit_events) == 0


def test_lost_database_connection_returns_503_without_events_or_secrets(database):
    broken = create_engine("postgresql+psycopg://demo:s3cret-test-password@127.0.0.1:1/unreachable",
                           connect_args={"connect_timeout": 1}, hide_parameters=True)
    with TestClient(app) as client:
        storage._ENGINES[storage._database_url()] = broken  # simulate the database going away after startup
        with client.websocket_connect("/api/v1/live") as websocket:
            assert websocket.receive_json()["type"] == "connected"
            write = client.post("/api/v1/risk/predict", json=NORMAL)
            simulated = client.post("/api/v1/demo/observations", json={"scenario": "stable", "step": 1})
            websocket.send_text("ping")
            assert websocket.receive_json() == {"type": "pong"}
        read = client.get("/api/v1/observations")
        alert_list = client.get("/api/v1/alerts")
        health = client.get("/health")
    for response in (write, simulated, read, alert_list):
        assert response.status_code == 503
        assert "s3cret" not in response.text and "127.0.0.1" not in response.text
        assert response.headers["x-request-id"]
    assert health.status_code == 503 and "s3cret" not in health.text


def test_startup_refuses_sqlite_when_postgres_is_required(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "not-durable.sqlite3"))
    monkeypatch.setenv("VITALGUARD_REQUIRE_POSTGRES", "true")
    with pytest.raises(StorageConfigurationError):
        initialize_storage()
    with pytest.raises(StorageConfigurationError):
        with TestClient(app):
            pass


def test_startup_rejects_unsupported_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://demo:secret@localhost/vitalguard")
    with pytest.raises(StorageConfigurationError) as error:
        initialize_storage()
    assert "secret" not in str(error.value)


def test_startup_fails_fast_when_database_is_unreachable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo@127.0.0.1:1/unreachable")
    monkeypatch.setenv("VITALGUARD_DB_CONNECT_TIMEOUT_SECONDS", "1")
    with pytest.raises(OperationalError):
        with TestClient(app):
            pass


def test_health_identifies_backend_without_exposing_configuration(database):
    with TestClient(app) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"
    assert body["database"]["backend"] == database
    assert body["database"]["durable_backend"] is (database == "postgresql")
    assert body["database"]["schema_version"] == body["database"]["latest_schema_version"]
    if database == "postgresql":
        assert body["database"]["server_version"]
        assert "postgresql+psycopg" not in str(body) and "@" not in str(body)


def test_observation_history_cursor_visits_every_record_once(database):
    with TestClient(app) as client:
        created = [client.post("/api/v1/risk/predict", json=NORMAL).json()["observation_id"] for _ in range(7)]
        seen, cursor = [], None
        while True:
            params = {"patient_id": NORMAL["patient_id"], "limit": 3}
            if cursor:
                params["before_id"] = cursor
            page = client.get("/api/v1/observations", params=params).json()
            seen.extend(item["id"] for item in page["items"])
            cursor = page["next_before_id"]
            if cursor is None:
                break
    assert seen == sorted(created, reverse=True)


def test_alert_list_is_cursor_paginated(database):
    with TestClient(app) as client:
        ids = [create_alert(patient_id="DEMO-PAGE", event_key=f"page:{index}", severity="high",
                            title="Synthetic", details={"demo_only": True})["id"] for index in range(5)]
        first = client.get("/api/v1/alerts", params={"limit": 2}).json()
        second = client.get("/api/v1/alerts", params={"limit": 2, "before_id": first["next_before_id"]}).json()
        last = client.get("/api/v1/alerts", params={"limit": 2, "before_id": second["next_before_id"]}).json()
        too_large = client.get("/api/v1/alerts", params={"limit": 101})
    assert [item["id"] for item in first["items"] + second["items"] + last["items"]] == sorted(ids, reverse=True)
    assert last["next_before_id"] is None
    assert too_large.status_code == 422


def test_audit_endpoint_finds_alerts_beyond_the_first_hundred(database):
    with TestClient(app) as client:
        first = create_alert(patient_id="DEMO-MANY", event_key="many:0", severity="high",
                             title="Synthetic", details={})
        for index in range(1, 105):
            create_alert(patient_id="DEMO-MANY", event_key=f"many:{index}", severity="high", title="Synthetic", details={})
        response = client.get(f"/api/v1/alerts/{first['id']}/audit")
        missing = client.get("/api/v1/alerts/999999/audit")
    assert response.status_code == 200 and response.json()["count"] == 1
    assert missing.status_code == 404


def test_concurrent_inserts_are_all_persisted_with_unique_ids(database):
    initialize_storage()

    def insert_batch(worker: int) -> list[int]:
        return [save_observation(f"DEMO-CONC-{worker}", {"spo2": 97}, {"model_version": "test", "risk_score": 1})["id"]
                for _ in range(10)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = [observation_id for batch in pool.map(insert_batch, range(8)) for observation_id in batch]
    assert len(ids) == len(set(ids)) == 80
    assert _count(observations) == 80


def test_concurrent_transitions_record_each_state_change_once(database):
    initialize_storage()
    alert = create_alert(patient_id="DEMO-RACE", event_key="race:1", severity="high", title="Synthetic", details={})
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda _: transition_alert(alert["id"], "acknowledge", "demo-nurse"), range(6)))
        list(pool.map(lambda _: transition_alert(alert["id"], "resolve", "demo-nurse"), range(6)))
    assert [item["action"] for item in list_alert_audit(alert["id"])] == ["created", "acknowledged", "resolved"]


def test_concurrent_duplicate_alerts_are_deduplicated(database):
    initialize_storage()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: create_alert(patient_id="DEMO-DUP", event_key="dup:1", severity="high",
                                                       title="Synthetic", details={}), range(6)))
    assert len({item["id"] for item in results}) == 1
    assert _count(alerts) == 1 and _count(audit_events) == 1

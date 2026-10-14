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


# --- Synchronized live-demo streaming -------------------------------------------------
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from app import observation_service, stream_service
from app.storage import get_engine
from app.storage_schema import alerts, observations

LIVE = "/api/v1/live-demo"


@pytest.fixture(autouse=True)
def _no_emit_rate_limit(monkeypatch):
    # Tests emit faster than a demo would; the rate limit has its own test below.
    monkeypatch.setattr(stream_service, "MIN_EMIT_GAP_SECONDS", 0)


def _count(table) -> int:
    with get_engine().connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar()


def start_stream(client, **body):
    response = client.post(f"{LIVE}/sessions", json={"scenario": "worsening", "interval_ms": 500, **body})
    assert response.status_code == 201, response.text
    data = response.json()
    return data["session"]["session_id"], data["producer_token"]


def emit(client, session_id, token, sequence):
    return client.post(f"{LIVE}/sessions/{session_id}/observations", json={"sequence": sequence},
                       headers={"X-Producer-Token": token} if token else {})


def receive_type(websocket, event_type):
    while True:
        message = websocket.receive_json()
        if message["type"] == event_type:
            return message


def drain(websocket):
    """Return every frame broadcast before a fresh pong."""
    websocket.send_text("ping")
    frames = []
    while (message := websocket.receive_json()) != {"type": "pong"}:
        frames.append(message)
    return frames


def assert_no_pending_events(websocket):
    # The pong must be the next frame: nothing else was broadcast in between.
    websocket.send_text("ping")
    assert websocket.receive_json() == {"type": "pong"}


def test_receiver_gets_the_same_committed_event_as_the_producer(database):
    with TestClient(app) as client, client.websocket_connect("/api/v1/live") as receiver:
        assert receiver.receive_json()["type"] == "connected"
        session_id, token = start_stream(client)
        started = receive_type(receiver, "stream.state")
        assert started["action"] == "started" and started["session"]["session_id"] == session_id
        assert "token" not in str(started)

        produced = emit(client, session_id, token, 0)
        assert produced.status_code == 200
        body = produced.json()
        received = receive_type(receiver, "observation.created")

    event = body["event"]
    assert body["duplicate"] is False
    assert received == event
    for key in ("event_id", "session_id", "sequence", "timestamp", "observation", "model_version",
                "prediction", "server_received_at", "published_at"):
        assert received[key] is not None, key
    assert received["session_id"] == session_id and received["sequence"] == 0
    assert received["demo_only"] is True and received["data_origin"] == "synthetic"
    assert received["prediction"]["observation_id"] == received["event_id"]


def test_retrying_a_sequence_creates_no_second_record_alert_or_broadcast(database):
    with TestClient(app) as client, client.websocket_connect("/api/v1/live") as receiver:
        receiver.receive_json()
        session_id, token = start_stream(client)
        receive_type(receiver, "stream.state")
        for sequence in range(8):  # worsening crosses the alert threshold
            emit(client, session_id, token, sequence)
        frames = drain(receiver)
        events = [frame for frame in frames if frame["type"] == "observation.created"]
        first_alert = next((event for event in events if event["alert"]), None)
        assert len(events) == 8
        assert first_alert is not None, "worsening scenario should raise an alert"
        assert sum(1 for frame in frames if frame["type"] == "alert.created") == sum(1 for event in events if event["alert"])
        observations_before, alerts_before = _count(observations), _count(alerts)

        retry = emit(client, session_id, token, first_alert["sequence"])
        assert retry.status_code == 200
        assert retry.json()["duplicate"] is True
        assert retry.json()["event"]["event_id"] == first_alert["event_id"]
        assert retry.json()["event"]["alert"]["id"] == first_alert["alert"]["id"]
        assert_no_pending_events(receiver)
    assert (_count(observations), _count(alerts)) == (observations_before, alerts_before)


def test_only_the_session_owner_can_emit_or_control(database):
    with TestClient(app) as client:
        session_id, token = start_stream(client)
        assert emit(client, session_id, None, 0).status_code == 403
        assert emit(client, session_id, "not-the-token", 0).json()["error"] == "not_session_owner"
        for action in ("pause", "resume", "stop"):
            response = client.post(f"{LIVE}/sessions/{session_id}/{action}", headers={"X-Producer-Token": "wrong"})
            assert response.status_code == 403
        assert emit(client, "no-such-session", token, 0).status_code == 404
        assert client.get(f"{LIVE}/sessions/current").json()["session"]["status"] == "running"
    assert _count(observations) == 0


def test_second_producer_is_rejected_unless_it_explicitly_takes_over(database):
    with TestClient(app) as client, client.websocket_connect("/api/v1/live") as receiver:
        receiver.receive_json()
        first_id, first_token = start_stream(client)
        receive_type(receiver, "stream.state")

        rejected = client.post(f"{LIVE}/sessions", json={"scenario": "stable"})
        assert rejected.status_code == 409
        assert rejected.json()["error"] == "producer_active"
        assert rejected.json()["active_session"]["session_id"] == first_id
        assert_no_pending_events(receiver)

        second_id, second_token = start_stream(client, scenario="stable", takeover=True)
        stopped = receive_type(receiver, "stream.state")
        assert (stopped["action"], stopped["session"]["session_id"]) == ("stopped", first_id)
        assert stopped["session"]["stop_reason"] == "takeover"
        assert receive_type(receiver, "stream.state")["session"]["session_id"] == second_id

        assert emit(client, first_id, first_token, 0).json()["error"] == "session_stopped"
        assert emit(client, second_id, second_token, 0).status_code == 200


def test_idle_session_can_be_replaced_without_takeover(database, monkeypatch):
    monkeypatch.setenv("VITALGUARD_STREAM_IDLE_TIMEOUT_SECONDS", "-1")
    with TestClient(app) as client:
        first_id, _ = start_stream(client)
        start_stream(client, scenario="stable")
        assert client.get(f"{LIVE}/sessions/{first_id}").json()["session"]["stop_reason"] == "idle_timeout"


def test_pause_resume_and_stop_lifecycle(database):
    with TestClient(app) as client, client.websocket_connect("/api/v1/live") as receiver:
        receiver.receive_json()
        session_id, token = start_stream(client)
        headers = {"X-Producer-Token": token}
        receive_type(receiver, "stream.state")
        assert emit(client, session_id, token, 0).status_code == 200
        receive_type(receiver, "observation.created")

        paused = client.post(f"{LIVE}/sessions/{session_id}/pause", headers=headers).json()
        assert paused["session"]["status"] == "paused" and paused["changed"] is True
        assert receive_type(receiver, "stream.state")["action"] == "paused"
        assert client.post(f"{LIVE}/sessions/{session_id}/pause", headers=headers).json()["changed"] is False
        assert emit(client, session_id, token, 1).json()["error"] == "session_paused"
        assert_no_pending_events(receiver)

        client.post(f"{LIVE}/sessions/{session_id}/resume", headers=headers)
        assert receive_type(receiver, "stream.state")["action"] == "resumed"
        assert emit(client, session_id, token, 1).json()["event"]["sequence"] == 1
        receive_type(receiver, "observation.created")

        stopped = client.post(f"{LIVE}/sessions/{session_id}/stop", headers=headers).json()["session"]
        assert stopped["status"] == "stopped" and stopped["stop_reason"] == "producer_stopped"
        assert receive_type(receiver, "stream.state")["action"] == "stopped"
        assert client.post(f"{LIVE}/sessions/{session_id}/resume", headers=headers).status_code == 409
        assert emit(client, session_id, token, 2).json()["error"] == "session_stopped"
        assert client.get(f"{LIVE}/sessions/current").json()["session"] is None
        # The receiver stays connected and listening after the producer stops.
        assert_no_pending_events(receiver)
    assert _count(observations) == 2


def test_out_of_order_sequence_is_rejected(database):
    with TestClient(app) as client:
        session_id, token = start_stream(client)
        response = emit(client, session_id, token, 3)
    assert response.status_code == 409
    assert response.json()["error"] == "sequence_out_of_order" and response.json()["expected_sequence"] == 0


def test_reconnecting_receiver_recovers_missed_events_without_duplicates(database):
    with TestClient(app) as client:
        session_id, token = start_stream(client)
        with client.websocket_connect("/api/v1/live") as receiver:
            receiver.receive_json()
            emit(client, session_id, token, 0)
            seen = receive_type(receiver, "observation.created")
        # Receiver is disconnected while the producer keeps streaming.
        missed = [emit(client, session_id, token, sequence).json()["event"] for sequence in range(1, 9)]
        recovered = client.get(f"{LIVE}/events", params={"after_id": seen["event_id"], "session_id": session_id}).json()
        again = client.get(f"{LIVE}/events", params={"after_id": seen["event_id"], "session_id": session_id}).json()
        history = client.get("/api/v1/observations", params={"session_id": session_id, "after_id": 0}).json()

    assert [item["event_id"] for item in recovered["items"]] == [item["event_id"] for item in missed]
    assert recovered == again  # catching up is read-only and repeatable
    for live, rest in zip(missed, recovered["items"]):
        for key in ("event_id", "sequence", "timestamp", "observation", "model_version", "prediction", "alert"):
            assert rest[key] == live[key], key
    assert [item["sequence"] for item in history["items"]] == list(range(9))
    assert _count(observations) == 9


def test_failed_write_during_stream_saves_nothing_and_publishes_nothing(database, monkeypatch):
    with TestClient(app) as client, client.websocket_connect("/api/v1/live") as receiver:
        receiver.receive_json()
        session_id, token = start_stream(client)
        receive_type(receiver, "stream.state")

        def failing_insert(*_args, **_kwargs):
            raise OperationalError("INSERT INTO observations", {}, Exception("simulated outage"))

        with monkeypatch.context() as patch:
            patch.setattr(observation_service, "insert_observation", failing_insert)
            failed = emit(client, session_id, token, 0)
        assert failed.status_code == 503
        assert_no_pending_events(receiver)
        assert client.get(f"{LIVE}/sessions/{session_id}").json()["session"]["next_sequence"] == 0

        retried = emit(client, session_id, token, 0)
        assert retried.status_code == 200 and retried.json()["duplicate"] is False
        assert receive_type(receiver, "observation.created")["event_id"] == retried.json()["event"]["event_id"]
    assert _count(observations) == 1


def test_concurrent_submissions_of_one_sequence_persist_once(database):
    with TestClient(app) as client:
        session_id, token = start_stream(client)
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: emit(client, session_id, token, 0), range(6)))
    bodies = [result.json() for result in results if result.status_code == 200]
    assert sum(1 for body in bodies if body["duplicate"] is False) == 1
    assert len({body["event"]["event_id"] for body in bodies}) == 1
    assert _count(observations) == 1


def test_concurrent_starts_leave_exactly_one_active_session(database):
    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda _: client.post(f"{LIVE}/sessions", json={"scenario": "stable"}), range(5)))
    assert sorted(result.status_code for result in results) == [201, 409, 409, 409, 409]


def test_emitting_faster_than_the_minimum_gap_is_rejected(database, monkeypatch):
    monkeypatch.setattr(stream_service, "MIN_EMIT_GAP_SECONDS", 60)
    with TestClient(app) as client:
        session_id, token = start_stream(client)
        assert emit(client, session_id, token, 0).status_code == 200
        too_fast = emit(client, session_id, token, 1)
    assert too_fast.status_code == 429 and too_fast.json()["error"] == "emitting_too_fast"


def test_producer_key_gates_starting_a_stream(database, monkeypatch):
    monkeypatch.setenv("VITALGUARD_STREAM_PRODUCER_KEY", "demo-key-for-tests")
    with TestClient(app) as client:
        assert client.get(f"{LIVE}/config").json()["producer_key_required"] is True
        missing = client.post(f"{LIVE}/sessions", json={"scenario": "stable"})
        wrong = client.post(f"{LIVE}/sessions", json={"scenario": "stable"}, headers={"X-Demo-Producer-Key": "nope"})
        allowed = client.post(f"{LIVE}/sessions", json={"scenario": "stable"},
                              headers={"X-Demo-Producer-Key": "demo-key-for-tests"})
    assert (missing.status_code, wrong.status_code, allowed.status_code) == (403, 403, 201)
    assert "demo-key-for-tests" not in missing.text


def test_producer_headers_are_allowed_by_cors_preflight(client):
    response = client.options(f"{LIVE}/sessions/abc/observations", headers={
        "Origin": "https://vitalguard-ai-g215.onrender.com", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-producer-token,x-demo-producer-key"})
    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "x-producer-token" in allowed and "x-demo-producer-key" in allowed


def test_timed_ping_returns_server_time_for_clock_offset(client):
    with client.websocket_connect("/api/v1/live") as websocket:
        assert websocket.receive_json()["server_time"]
        websocket.send_text('{"type":"ping","client_time":1234.5}')
        pong = websocket.receive_json()
        websocket.send_text("{not json")
        error = websocket.receive_json()
    assert pong["type"] == "pong" and pong["client_time"] == 1234.5 and pong["server_time"]
    assert error["type"] == "error"

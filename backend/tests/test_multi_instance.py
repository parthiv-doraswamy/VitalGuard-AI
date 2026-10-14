"""Two real backend processes sharing one PostgreSQL database (cross-instance delivery).

Runs only with VITALGUARD_TEST_POSTGRES_URL (CI provides a PostgreSQL service).
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text
from websockets.sync.client import connect

from conftest import POSTGRES_TEST_URL, reset_postgres_schema

BACKEND_DIR = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not POSTGRES_TEST_URL, reason="VITALGUARD_TEST_POSTGRES_URL not set")
NORMAL = {"age": 58, "heart_rate": 82, "spo2": 98, "systolic_bp": 122, "diastolic_bp": 78, "temperature": 37.0,
          "respiratory_rate": 16}
ELEVATED = {"age": 70, "heart_rate": 180, "spo2": 78, "systolic_bp": 80, "diastolic_bp": 50, "temperature": 39.5,
            "respiratory_rate": 34}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Instance:
    def __init__(self, name: str, log_dir: Path):
        self.name, self.port = name, _free_port()
        self.url, self.ws_url = f"http://127.0.0.1:{self.port}", f"ws://127.0.0.1:{self.port}/api/v1/live"
        self.log_path = log_dir / f"{name}.log"
        env = {**os.environ, "DATABASE_URL": POSTGRES_TEST_URL, "VITALGUARD_INSTANCE_ID": name,
               "VITALGUARD_REQUIRE_POSTGRES": "true", "VITALGUARD_EVENT_POLL_SECONDS": "0.5"}
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=BACKEND_DIR, env=env, stdout=open(self.log_path, "w"), stderr=subprocess.STDOUT)
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                if httpx.get(f"{self.url}/health/ready", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError(f"{name} did not start: {self.log_path.read_text()[-2000:]}")

    def health(self) -> dict:
        return httpx.get(f"{self.url}/health", timeout=5).json()

    def stop(self):
        self.process.terminate()
        self.process.wait(timeout=20)


class Receiver:
    """A WebSocket client collecting events on a background thread."""

    def __init__(self, url: str):
        self.events: list[dict] = []
        self._socket = connect(url)
        assert json.loads(self._socket.recv(timeout=5))["type"] == "connected"
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            for message in self._socket:
                self.events.append(json.loads(message))
        except Exception:
            pass

    def wait_for(self, predicate, timeout=10.0) -> list[dict]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            matched = [event for event in self.events if predicate(event)]
            if matched:
                return matched
            time.sleep(0.05)
        raise AssertionError(f"event not received within {timeout}s; got {[e.get('type') for e in self.events]}")

    def close(self):
        self._socket.close()


@pytest.fixture(scope="module")
def cluster(tmp_path_factory):
    reset_postgres_schema(POSTGRES_TEST_URL)
    log_dir = tmp_path_factory.mktemp("instances")
    a = Instance("instance-a", log_dir)
    b = Instance("instance-b", log_dir)
    yield a, b
    a.stop()
    b.stop()


def _observations(session_or_patient: str) -> int:
    engine = create_engine(POSTGRES_TEST_URL)
    try:
        with engine.connect() as connection:
            return connection.execute(text("SELECT count(*) FROM observations WHERE patient_id = :p"),
                                      {"p": session_or_patient}).scalar()
    finally:
        engine.dispose()


def test_both_instances_report_cross_instance_delivery(cluster):
    for instance in cluster:
        broker = instance.health()["event_broker"]
        assert broker["mode"] == "postgres" and broker["cross_instance_delivery"] is True
        assert broker["instance_id"] == instance.name


def test_one_event_reaches_clients_on_both_instances(cluster):
    a, b = cluster
    on_a, on_b = Receiver(a.ws_url), Receiver(b.ws_url)
    try:
        response = httpx.post(f"{a.url}/api/v1/risk/predict", json={"patient_id": "MULTI-ONE", **ELEVATED}, timeout=10)
        observation_id = response.json()["observation_id"]
        match = lambda e: e.get("type") == "observation.created" and e.get("event_id") == observation_id  # noqa: E731
        event_a, event_b = on_a.wait_for(match)[0], on_b.wait_for(match)[0]
        on_b.wait_for(lambda e: e.get("type") == "alert.created" and e.get("observation_id") == observation_id)
    finally:
        on_a.close(); on_b.close()
    assert event_a["event_seq"] == event_b["event_seq"] and event_a["event_uuid"] == event_b["event_uuid"]
    assert event_a["origin_instance"] == event_b["origin_instance"] == "instance-a"
    assert {k: v for k, v in event_a.items() if k != "published_at"} == {k: v for k, v in event_b.items() if k != "published_at"}


def test_concurrent_writes_on_both_instances_reach_every_client_exactly_once(cluster):
    a, b = cluster
    on_a, on_b = Receiver(a.ws_url), Receiver(b.ws_url)
    try:
        def post(index):
            target = a if index % 2 == 0 else b
            return httpx.post(f"{target.url}/api/v1/risk/predict", json={"patient_id": "MULTI-CONC", **NORMAL}, timeout=20)

        with ThreadPoolExecutor(max_workers=10) as pool:
            responses = list(pool.map(post, range(40)))
        assert all(response.status_code == 200 for response in responses)
        ids = {response.json()["observation_id"] for response in responses}
        is_ours = lambda e: e.get("type") == "observation.created" and e.get("event_id") in ids  # noqa: E731
        deadline = time.time() + 15
        while time.time() < deadline and not (len([e for e in on_a.events if is_ours(e)]) >= 40
                                              and len([e for e in on_b.events if is_ours(e)]) >= 40):
            time.sleep(0.1)
        time.sleep(1)  # allow any (wrong) duplicates to arrive
        for receiver in (on_a, on_b):
            received = [e["event_id"] for e in receiver.events if is_ours(e)]
            assert sorted(received) == sorted(ids), "every event exactly once"
    finally:
        on_a.close(); on_b.close()
    assert _observations("MULTI-CONC") == 40


def test_same_stream_sequence_sent_to_both_instances_is_stored_once(cluster):
    a, b = cluster
    session = httpx.post(f"{a.url}/api/v1/live-demo/sessions", json={"scenario": "worsening", "takeover": True}, timeout=10).json()
    session_id, headers = session["session"]["session_id"], {"X-Producer-Token": session["producer_token"]}
    barrier = threading.Barrier(2)

    def emit(instance):
        barrier.wait()
        return httpx.post(f"{instance.url}/api/v1/live-demo/sessions/{session_id}/observations",
                          json={"sequence": 0}, headers=headers, timeout=10)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(emit, cluster))
    bodies = [result.json() for result in results if result.status_code == 200]
    assert sum(1 for body in bodies if not body["duplicate"]) == 1
    assert len({body["event"]["event_seq"] for body in bodies}) == 1
    assert _observations(session["session"]["patient_id"]) == 1
    httpx.post(f"{a.url}/api/v1/live-demo/sessions/{session_id}/stop", headers=headers, timeout=10)


def test_broker_disconnection_is_reported_and_recovered(cluster):
    a, b = cluster
    on_b = Receiver(b.ws_url)
    engine = create_engine(POSTGRES_TEST_URL)
    try:
        with engine.begin() as connection:
            killed = connection.execute(text("SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity "
                                             "WHERE datname = current_database() AND application_name LIKE 'vitalguard-listener-instance-b%'")).scalar()
        assert killed == 1
        # Commit on A while B's listener is down; B must still deliver (poll + reconnect catch-up).
        observation_id = httpx.post(f"{a.url}/api/v1/risk/predict", json={"patient_id": "MULTI-OUTAGE", **NORMAL},
                                    timeout=10).json()["observation_id"]
        on_b.wait_for(lambda e: e.get("type") == "observation.created" and e.get("event_id") == observation_id, timeout=15)
        deadline = time.time() + 20
        broker = b.health()["event_broker"]
        while time.time() < deadline and not (broker["listener_connected"] and broker["listener_reconnects"] >= 1):
            time.sleep(0.2)
            broker = b.health()["event_broker"]
        assert broker["listener_reconnects"] >= 1 and broker["listener_connected"] is True and broker["status"] == "ok"
    finally:
        on_b.close()
        engine.dispose()


def test_disconnected_receiver_recovers_missed_events_from_either_instance(cluster):
    a, b = cluster
    receiver = Receiver(b.ws_url)
    first = httpx.post(f"{a.url}/api/v1/risk/predict", json={"patient_id": "MULTI-RECOVER", **NORMAL}, timeout=10).json()
    seen = receiver.wait_for(lambda e: e.get("type") == "observation.created" and e.get("event_id") == first["observation_id"])[0]
    receiver.close()
    missed = [httpx.post(f"{a.url}/api/v1/risk/predict", json={"patient_id": "MULTI-RECOVER", **NORMAL}, timeout=10).json()["observation_id"]
              for _ in range(5)]
    page = httpx.get(f"{b.url}/api/v1/events", params={"after_seq": seen["event_seq"], "limit": 500}, timeout=10).json()
    recovered = [item["event_id"] for item in page["items"]
                 if item["type"] == "observation.created" and item["patient_id"] == "MULTI-RECOVER"]
    assert recovered == missed
    assert page["history_truncated"] is False


def test_instance_logs_have_no_unhandled_exceptions(cluster):
    for instance in cluster:
        log = instance.log_path.read_text()
        assert "Traceback" not in log, log[-3000:]

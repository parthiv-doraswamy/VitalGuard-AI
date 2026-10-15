"""Web Push: ownership, transactional enqueue, minimal encrypted payloads, retries, cleanup, receipts.

A local mock push service stands in for FCM/Mozilla/Apple. Payloads are decrypted
with the fake browser's keys (real aes128gcm Web Push encryption) and the VAPID
JWT is verified, so the tests check exactly what a device would receive.
"""
import base64
import json
import logging
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import http_ece
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from fastapi.testclient import TestClient
from py_vapid import Vapid
from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError

from app import notification_service as service
from app import observation_service
from app.alert_service import create_alert
from app.main import app
from app.storage import get_engine
from app.storage_schema import push_deliveries, push_subscriptions
from conftest import auth_headers

AUTH = auth_headers()
# Alerts are pushed only to the assigned doctor: these ICU patients belong to doctor.demo.
DOCTOR = auth_headers("doctor.demo")

ELEVATED = {"patient_id": "P-SIM-006", "age": 70, "heart_rate": 180, "spo2": 78, "systolic_bp": 80,
            "diastolic_bp": 50, "temperature": 39.5, "respiratory_rate": 34}
b64 = lambda raw: base64.urlsafe_b64encode(raw).decode().rstrip("=")  # noqa: E731
unb64 = lambda text: base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))  # noqa: E731


class MockPushService:
    """Records POSTs per path and answers with scripted status codes (default 201)."""

    def __init__(self):
        self.requests: list[dict] = []
        self.scripts: dict[str, list[tuple[int, dict]]] = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                outer.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
                code, headers = (outer.scripts.get(self.path) or [(201, {})]).pop(0) if outer.scripts.get(self.path) else (201, {})
                self.send_response(code)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def endpoint(self, name: str) -> str:
        return f"http://127.0.0.1:{self.port}/push/{name}"

    def for_path(self, name: str) -> list[dict]:
        return [item for item in self.requests if item["path"] == f"/push/{name}"]


class FakeBrowser:
    """A subscriber key pair, as a browser's PushManager would create."""

    def __init__(self, endpoint: str):
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        self.endpoint = endpoint
        public = self.private_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.subscription = {"endpoint": endpoint, "expirationTime": None, "keys": {"p256dh": b64(public), "auth": b64(self.auth)}}

    def decrypt(self, body: bytes) -> dict:
        return json.loads(http_ece.decrypt(body, private_key=self.private_key, auth_secret=self.auth, version="aes128gcm"))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "push.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def push_service():
    mock = MockPushService()
    yield mock
    mock.server.shutdown()


@pytest.fixture
def vapid(monkeypatch, push_service):
    key = Vapid()
    key.generate_keys()
    raw_private = key.private_key.private_numbers().private_value.to_bytes(32, "big")
    monkeypatch.setenv("VITALGUARD_VAPID_PRIVATE_KEY", b64(raw_private))
    monkeypatch.setenv("VITALGUARD_VAPID_SUBJECT", "mailto:test@example.org")
    monkeypatch.setenv("VITALGUARD_PUSH_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setenv("VITALGUARD_PUSH_ALLOW_INSECURE_ENDPOINTS", "true")
    monkeypatch.setenv("VITALGUARD_PUSH_POLL_SECONDS", "0.2")
    push_service.requests.clear()
    push_service.scripts.clear()
    return key


def register(client, browser, headers=None, **body):
    response = client.post("/api/v1/notifications/subscriptions", headers=headers or DOCTOR,
                           json={"subscription": browser.subscription, **body})
    assert response.status_code == 201, response.text
    data = response.json()
    return data["subscription"]["subscription_id"], data["management_token"]


def owner(token):
    return {"X-Subscription-Token": token}


def deliveries(subscription_id=None):
    query = select(push_deliveries).order_by(push_deliveries.c.id)
    if subscription_id:
        query = query.where(push_deliveries.c.subscription_id == subscription_id)
    with get_engine().connect() as connection:
        return [dict(row) for row in connection.execute(query).mappings().all()]


def make_due():
    with get_engine().begin() as connection:
        connection.execute(update(push_deliveries).values(next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1)))


def wait_for(predicate, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met in time")


# --- Configuration and subscription management ---------------------------------------------

def test_config_reports_unavailable_without_vapid_keys(client, monkeypatch):
    monkeypatch.delenv("VITALGUARD_VAPID_PRIVATE_KEY", raising=False)
    body = client.get("/api/v1/notifications/config").json()
    assert body["push_available"] is False and body["vapid_public_key"] is None
    assert body["fallback"].startswith("in-app alert center")


def test_config_serves_the_public_key_derived_from_the_private_key(database, vapid):
    with TestClient(app) as client:
        body = client.get("/api/v1/notifications/config").json()
    expected = b64(vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    assert body["push_available"] is True and body["vapid_public_key"] == expected
    assert os.environ["VITALGUARD_VAPID_PRIVATE_KEY"] not in json.dumps(body)


@pytest.mark.parametrize("endpoint, error", [
    ("https://evil.example.org/push/x", "endpoint_not_allowed"),
    ("https://169.254.169.254/latest/meta-data", "endpoint_not_allowed"),
    ("https://user:pass@fcm.googleapis.com/fcm/send/x", "endpoint_not_allowed"),
])
def test_registration_only_accepts_real_push_services(database, vapid, monkeypatch, endpoint, error):
    monkeypatch.delenv("VITALGUARD_PUSH_ALLOWED_HOSTS")
    with TestClient(app) as client:
        response = client.post("/api/v1/notifications/subscriptions", headers=AUTH, json={"subscription": FakeBrowser(endpoint).subscription})
    assert response.status_code == 422 and response.json()["error"] == error


def test_registration_requires_https_and_valid_keys(database, vapid, monkeypatch, push_service):
    monkeypatch.setenv("VITALGUARD_PUSH_ALLOW_INSECURE_ENDPOINTS", "false")
    with TestClient(app) as client:
        insecure = client.post("/api/v1/notifications/subscriptions", headers=AUTH,
                               json={"subscription": FakeBrowser(push_service.endpoint("insecure")).subscription})
        monkeypatch.setenv("VITALGUARD_PUSH_ALLOW_INSECURE_ENDPOINTS", "true")
        bad = FakeBrowser(push_service.endpoint("badkeys")).subscription
        bad["keys"]["p256dh"] = b64(b"\x05" + os.urandom(64))
        bad_keys = client.post("/api/v1/notifications/subscriptions", headers=AUTH, json={"subscription": bad})
    assert insecure.json()["error"] == "endpoint_not_https"
    assert bad_keys.json()["error"] == "invalid_keys"


def test_ownership_token_is_required_and_only_its_hash_is_stored(database, vapid, push_service):
    browser = FakeBrowser(push_service.endpoint("owner"))
    with TestClient(app) as client:
        subscription_id, token = register(client, browser)
        assert client.get(f"/api/v1/notifications/subscriptions/{subscription_id}").status_code == 403
        assert client.get(f"/api/v1/notifications/subscriptions/{subscription_id}", headers=owner("wrong")).status_code == 403
        assert client.delete(f"/api/v1/notifications/subscriptions/{subscription_id}", headers=owner("wrong")).status_code == 403
        assert client.post(f"/api/v1/notifications/subscriptions/{subscription_id}/test").status_code == 403
        assert client.get("/api/v1/notifications/subscriptions/nope", headers=owner(token)).status_code == 404
        status = client.get(f"/api/v1/notifications/subscriptions/{subscription_id}", headers=owner(token)).json()
    with get_engine().connect() as connection:
        row = connection.execute(select(push_subscriptions)).mappings().one()
    assert row["token_hash"] != token and len(row["token_hash"]) == 64
    assert browser.endpoint not in json.dumps(status)


def test_reregistering_rotates_the_token(database, vapid, push_service):
    browser = FakeBrowser(push_service.endpoint("rotate"))
    with TestClient(app) as client:
        first_id, first_token = register(client, browser)
        second_id, second_token = register(client, browser)
        assert first_id == second_id and first_token != second_token
        assert client.get(f"/api/v1/notifications/subscriptions/{first_id}", headers=owner(first_token)).status_code == 403
        assert client.get(f"/api/v1/notifications/subscriptions/{first_id}", headers=owner(second_token)).status_code == 200


def test_unsubscribe_deletes_endpoint_keys_and_history(database, vapid, push_service):
    with TestClient(app) as client:
        subscription_id, token = register(client, FakeBrowser(push_service.endpoint("delete")))
        client.post(f"/api/v1/notifications/subscriptions/{subscription_id}/test", headers=owner(token))
        assert client.delete(f"/api/v1/notifications/subscriptions/{subscription_id}", headers=owner(token)).status_code == 204
    with get_engine().connect() as connection:
        assert connection.execute(select(func.count()).select_from(push_subscriptions)).scalar() == 0
    assert deliveries() == []


def test_subscription_limit(database, vapid, monkeypatch, push_service):
    monkeypatch.setenv("VITALGUARD_PUSH_MAX_SUBSCRIPTIONS", "1")
    with TestClient(app) as client:
        register(client, FakeBrowser(push_service.endpoint("limit-1")))
        response = client.post("/api/v1/notifications/subscriptions", headers=AUTH,
                               json={"subscription": FakeBrowser(push_service.endpoint("limit-2")).subscription})
    assert response.status_code == 503 and response.json()["error"] == "subscription_limit"


# --- Alert → push, end to end ---------------------------------------------------------------

def test_committed_alert_reaches_the_push_service_with_a_minimal_encrypted_payload(database, vapid, push_service):
    browser = FakeBrowser(push_service.endpoint("e2e"))
    with TestClient(app) as client:
        subscription_id, token = register(client, browser)
        prediction = client.post("/api/v1/risk/predict", json=ELEVATED).json()
        wait_for(lambda: push_service.for_path("e2e"))
        alert = client.get("/api/v1/alerts", headers=AUTH, params={"patient_id": ELEVATED["patient_id"]}).json()["items"][0]
        wait_for(lambda: deliveries(subscription_id) and deliveries(subscription_id)[0]["status"] == "accepted")
        status = client.get(f"/api/v1/notifications/subscriptions/{subscription_id}", headers=owner(token)).json()

    request = push_service.for_path("e2e")[0]
    payload = browser.decrypt(request["body"])
    assert set(payload) == {"v", "type", "alert_id", "severity", "title", "body", "url", "tag", "delivery_id", "receipt"}
    assert payload["alert_id"] == alert["id"] and payload["url"] == f"/#/alerts?alert={alert['id']}"
    text = json.dumps(payload)
    for secret in (ELEVATED["patient_id"], "heart_rate", "spo2", str(prediction["risk_score"]), "observation"):
        assert secret not in text, secret
    assert request["headers"]["ttl"] == "3600" and request["headers"]["urgency"] in {"high", "normal"}
    assert request["headers"]["topic"] == f"vg-alert-{alert['id']}"
    # VAPID: an ES256 JWT for this push service's origin, signed by our server key.
    scheme, params = request["headers"]["authorization"].split(" ", 1)
    assert scheme == "vapid"
    jwt = dict(part.strip().split("=", 1) for part in params.split(","))["t"]
    header_b64, claims_b64, signature_b64 = jwt.split(".")
    claims = json.loads(unb64(claims_b64))
    assert claims["aud"] == f"http://127.0.0.1:{push_service.port}" and claims["sub"] == "mailto:test@example.org"
    assert claims["exp"] > time.time()
    raw_signature = unb64(signature_b64)
    signature = encode_dss_signature(int.from_bytes(raw_signature[:32], "big"), int.from_bytes(raw_signature[32:], "big"))
    vapid.public_key.verify(signature, f"{header_b64}.{claims_b64}".encode(), ec.ECDSA(hashes.SHA256()))
    # Accepted by the push service, but not yet shown: only a device receipt sets displayed_at.
    delivery = status["deliveries"][0]
    assert delivery["status"] == "accepted" and delivery["displayed_at"] is None
    assert "not proof" in delivery["note"]


def test_receipts_record_display_and_click_only_with_a_valid_nonce(database, vapid, push_service):
    browser = FakeBrowser(push_service.endpoint("receipt"))
    with TestClient(app) as client:
        subscription_id, token = register(client, browser)
        client.post(f"/api/v1/notifications/subscriptions/{subscription_id}/test", headers=owner(token))
        wait_for(lambda: push_service.for_path("receipt"))
        payload = browser.decrypt(push_service.for_path("receipt")[0]["body"])
        assert payload["type"] == "test" and payload["receipt"]["url"].endswith("/api/v1/notifications/receipts")
        forged = client.post("/api/v1/notifications/receipts", json={"delivery_id": payload["delivery_id"],
                                                                     "nonce": "0" * 32, "event": "displayed"})
        shown = client.post("/api/v1/notifications/receipts", json={"delivery_id": payload["delivery_id"],
                                                                    "nonce": payload["receipt"]["nonce"], "event": "displayed"})
        clicked = client.post("/api/v1/notifications/receipts", json={"delivery_id": payload["delivery_id"],
                                                                      "nonce": payload["receipt"]["nonce"], "event": "clicked"})
        status = client.get(f"/api/v1/notifications/subscriptions/{subscription_id}", headers=owner(token)).json()
    assert forged.status_code == 403 and shown.status_code == 204 and clicked.status_code == 204
    assert status["deliveries"][0]["displayed_at"] and status["deliveries"][0]["clicked_at"]


def test_no_notification_is_queued_for_an_alert_that_rolls_back(database, vapid, push_service, monkeypatch):
    with TestClient(app) as client:
        register(client, FakeBrowser(push_service.endpoint("rollback")))
        original = observation_service.record_event

        def fail_on_alert_event(connection, event_type, *args, **kwargs):
            if event_type == "alert.created":
                raise OperationalError("insert", {}, Exception("outage after alert insert"))
            return original(connection, event_type, *args, **kwargs)

        monkeypatch.setattr(observation_service, "record_event", fail_on_alert_event)
        assert client.post("/api/v1/risk/predict", json=ELEVATED).status_code == 503
        time.sleep(0.5)
    assert deliveries() == [] and push_service.for_path("rollback") == []


def test_preferences_filter_by_severity_and_enabled(database, vapid, push_service):
    with TestClient(app) as client:
        critical_only, token = register(client, FakeBrowser(push_service.endpoint("critical-only")), min_severity="critical")
        paused, paused_token = register(client, FakeBrowser(push_service.endpoint("paused")))
        client.patch(f"/api/v1/notifications/subscriptions/{paused}", json={"enabled": False}, headers=owner(paused_token))
    create_alert(patient_id="P-SIM-003", event_key="pref:high", severity="high", title="t", details={})
    create_alert(patient_id="P-SIM-003", event_key="pref:critical", severity="critical", title="t", details={})
    assert [d["alert_id"] is not None for d in deliveries(critical_only)] == [True]
    assert deliveries(paused) == []


def test_alerts_reach_only_the_assigned_doctors_devices(database, vapid, push_service):
    with TestClient(app) as client:
        assert client.post("/api/v1/notifications/subscriptions",
                           json={"subscription": FakeBrowser(push_service.endpoint("anon")).subscription}).status_code == 401
        icu_doctor, _ = register(client, FakeBrowser(push_service.endpoint("icu-doctor")))
        er_doctor, er_token = register(client, FakeBrowser(push_service.endpoint("er-doctor")), headers=auth_headers("dr.khan"))
        admin, _ = register(client, FakeBrowser(push_service.endpoint("admin")), headers=AUTH)
        status = client.get(f"/api/v1/notifications/subscriptions/{er_doctor}", headers=owner(er_token)).json()
    assert status["subscription"]["username"] == "dr.khan"
    # P-SIM-003 is in the ICU (doctor.demo); P-SIM-004 is in Emergency (dr.khan); DEMO-X is not in the cohort.
    create_alert(patient_id="P-SIM-003", event_key="target:icu", severity="high", title="t", details={})
    create_alert(patient_id="P-SIM-004", event_key="target:er", severity="critical", title="t", details={})
    create_alert(patient_id="DEMO-X", event_key="target:none", severity="critical", title="t", details={})
    assert [d["event_key"] for d in deliveries(icu_doctor)] == ["alert:1:created"]
    assert [d["event_key"] for d in deliveries(er_doctor)] == ["alert:2:created"]
    assert deliveries(admin) == []


# --- Deduplication, retries and cleanup -------------------------------------------------------

def test_duplicate_alerts_and_repeated_or_concurrent_workers_send_once(database, vapid, push_service):
    with TestClient(app) as client:
        register(client, FakeBrowser(push_service.endpoint("dedupe")))
    for _ in range(3):
        create_alert(patient_id="P-SIM-003", event_key="dedupe:1", severity="high", title="t", details={})
    assert len(deliveries()) == 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: service.process_due(), range(4)))
    service.process_due()
    assert len(push_service.for_path("dedupe")) == 1 and deliveries()[0]["status"] == "accepted"


def test_transient_errors_are_retried_with_backoff_and_retry_after(database, vapid, push_service):
    push_service.scripts["/push/retry"] = [(500, {}), (429, {"Retry-After": "120"}), (201, {})]
    with TestClient(app) as client:
        register(client, FakeBrowser(push_service.endpoint("retry")))
    create_alert(patient_id="P-SIM-003", event_key="retry:1", severity="high", title="t", details={})
    assert service.process_due() == ["retrying"]
    assert service.process_due() == []  # not due yet: backoff respected
    make_due()
    assert service.process_due() == ["retrying"]
    next_attempt = deliveries()[0]["next_attempt_at"]
    next_attempt = next_attempt if next_attempt.tzinfo else next_attempt.replace(tzinfo=timezone.utc)  # SQLite is naive UTC
    delay = (next_attempt - datetime.now(timezone.utc)).total_seconds()
    assert 100 < delay <= 121  # Retry-After honoured
    make_due()
    assert service.process_due() == ["accepted"]
    final = deliveries()[0]
    assert final["attempts"] == 3 and final["last_status_code"] == 201


def test_network_failures_retry_then_give_up_after_max_attempts(database, vapid, push_service):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
    with TestClient(app) as client:
        register(client, FakeBrowser(f"http://127.0.0.1:{dead_port}/push/dead"))
    create_alert(patient_id="P-SIM-003", event_key="net:1", severity="high", title="t", details={})
    outcomes = []
    for _ in range(service.MAX_ATTEMPTS):
        make_due()
        outcomes += service.process_due()
    assert outcomes == ["retrying"] * (service.MAX_ATTEMPTS - 1) + ["failed"]
    assert deliveries()[0]["last_status_code"] is None


def test_gone_subscriptions_are_deactivated_and_pending_work_skipped(database, vapid, push_service):
    push_service.scripts["/push/gone"] = [(410, {})]
    with TestClient(app) as client:
        subscription_id, token = register(client, FakeBrowser(push_service.endpoint("gone")))
    create_alert(patient_id="P-SIM-003", event_key="gone:1", severity="high", title="t", details={})
    create_alert(patient_id="P-SIM-003", event_key="gone:2", severity="high", title="t", details={})
    service.process_due(limit=1)
    statuses = [d["status"] for d in deliveries(subscription_id)]
    assert statuses == ["expired", "skipped"]
    create_alert(patient_id="P-SIM-003", event_key="gone:3", severity="high", title="t", details={})
    assert len(deliveries(subscription_id)) == 2  # expired subscriptions get nothing new
    with get_engine().connect() as connection:
        assert connection.execute(select(push_subscriptions.c.status)).scalar() == "expired"
    assert len(push_service.for_path("gone")) == 1


def test_permanent_client_errors_are_not_retried(database, vapid, push_service):
    push_service.scripts["/push/toolarge"] = [(413, {})]
    with TestClient(app) as client:
        register(client, FakeBrowser(push_service.endpoint("toolarge")))
    create_alert(patient_id="P-SIM-003", event_key="large:1", severity="high", title="t", details={})
    assert service.process_due() == ["failed"]
    make_due()
    assert service.process_due() == []


def test_logs_never_contain_endpoints_keys_or_patient_data(database, vapid, push_service, caplog):
    caplog.set_level(logging.DEBUG, logger="vitalguard")
    browser = FakeBrowser(push_service.endpoint("logs"))
    with TestClient(app) as client:
        subscription_id, token = register(client, browser)
        client.post("/api/v1/risk/predict", json=ELEVATED)
        wait_for(lambda: push_service.for_path("logs"))
        wait_for(lambda: deliveries(subscription_id)[0]["status"] == "accepted")
    logs = caplog.text
    assert "push delivery" in logs and subscription_id[:8] in logs
    for secret in (browser.endpoint, "/push/logs", browser.subscription["keys"]["p256dh"],
                   browser.subscription["keys"]["auth"], token, ELEVATED["patient_id"], os.environ["VITALGUARD_VAPID_PRIVATE_KEY"]):
        assert secret not in logs, secret


def test_in_app_alerts_work_when_push_is_not_configured(database, monkeypatch):
    monkeypatch.delenv("VITALGUARD_VAPID_PRIVATE_KEY", raising=False)
    with TestClient(app) as client, client.websocket_connect("/api/v1/live") as receiver:
        receiver.receive_json()
        client.post("/api/v1/risk/predict", json=ELEVATED)
        while (event := receiver.receive_json())["type"] != "alert.created":
            pass
        health = client.get("/health").json()
        alerts = client.get("/api/v1/alerts", headers=AUTH).json()
    assert alerts["count"] == 1 and event["alert"]["id"] == alerts["items"][0]["id"]
    assert health["components"]["web_push"]["configured"] is False and health["status"] == "ok"
    assert deliveries() == []


def test_cors_allows_subscription_management(client):
    response = client.options("/api/v1/notifications/subscriptions/x", headers={
        "Origin": "https://vitalguard-ai-g215.onrender.com", "Access-Control-Request-Method": "DELETE",
        "Access-Control-Request-Headers": "x-subscription-token"})
    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert "x-subscription-token" in response.headers["access-control-allow-headers"].lower()

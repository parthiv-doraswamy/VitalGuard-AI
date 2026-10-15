"""Sign-in, role scoping, and cohort live streams that drive every existing demo patient."""
import pytest
from fastapi.testclient import TestClient

from app import stream_service
from app.auth import issue_token, verify_token
from app.cohort import cohort_vitals, get_patient, patients
from app.main import app
from conftest import auth_headers

LIVE = "/api/v1/live-demo"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "cohort.sqlite3"))
    monkeypatch.setenv("VITALGUARD_STREAM_IDLE_TIMEOUT_SECONDS", "120")
    monkeypatch.setattr(stream_service, "MIN_EMIT_GAP_SECONDS", 0)
    with TestClient(app) as test_client:
        yield test_client


def start_cohort(client, user="nurse.demo"):
    response = client.post(f"{LIVE}/sessions", json={"mode": "cohort", "interval_ms": 500}, headers=auth_headers(user))
    assert response.status_code == 201, response.text
    return response.json()["session"], response.json()["producer_token"]


def emit(client, session_id, token, sequence):
    response = client.post(f"{LIVE}/sessions/{session_id}/observations", json={"sequence": sequence},
                           headers={"X-Producer-Token": token})
    assert response.status_code == 200, response.text
    return response.json()


def test_login_returns_a_signed_token_for_demo_staff(client):
    response = client.post("/api/v1/auth/login", json={"username": "dr.khan", "password": "demo-access"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {"username": "dr.khan", "display_name": "Dr. Imran Khan", "role": "doctor", "wards": ["Emergency"]}
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.json()["user"]["role"] == "doctor"
    assert client.post("/api/v1/auth/login", json={"username": "dr.khan", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "nobody", "password": "demo-access"}).status_code == 401


def test_tokens_expire_and_cannot_be_tampered_with():
    token = issue_token("nurse.demo", now=1_000)
    assert verify_token(token, now=1_001)["role"] == "nurse"
    assert verify_token(token, now=10**10) is None
    body, signature = token.split(".")
    forged_body = issue_token("admin.demo", now=1_000).split(".")[0]
    assert verify_token(f"{forged_body}.{signature}", now=1_001) is None


def test_doctors_see_only_assigned_patients_and_staff_list_is_admin_only(client):
    mine = client.get("/api/v1/patients", headers=auth_headers("doctor.demo")).json()
    assert mine["scope"] == "assigned" and mine["count"] == 10
    assert {item["ward"] for item in mine["items"]} == {"ICU"}
    assert client.get("/api/v1/patients", headers=auth_headers("nurse.demo")).json()["count"] == len(patients())
    assert client.get("/api/v1/patients/P-SIM-004", headers=auth_headers("doctor.demo")).status_code == 403
    assert client.get("/api/v1/patients/P-SIM-003", headers=auth_headers("doctor.demo")).status_code == 200
    assert client.get("/api/v1/patients").status_code == 401
    assert client.get("/api/v1/staff", headers=auth_headers("nurse.demo")).status_code == 403
    staff = client.get("/api/v1/staff", headers=auth_headers()).json()["items"]
    assert sum(len(member["assigned_patients"]) for member in staff) == len(patients())


def test_cohort_vitals_are_deterministic_and_follow_each_scenario():
    worsening, recovering = get_patient("P-SIM-003"), get_patient("P-SIM-004")
    assert cohort_vitals(worsening, 7) == cohort_vitals(worsening, 7)
    assert cohort_vitals(worsening, 40)["spo2"] < cohort_vitals(worsening, 0)["spo2"]
    assert cohort_vitals(recovering, 40)["heart_rate"] < cohort_vitals(recovering, 0)["heart_rate"]
    for patient in patients():
        values = cohort_vitals(patient, 30)
        assert values["diastolic_bp"] < values["systolic_bp"]


def test_only_admins_and_nurses_can_start_a_stream(client):
    assert client.post(f"{LIVE}/sessions", json={"mode": "cohort"}).status_code == 401
    assert client.post(f"{LIVE}/sessions", json={"mode": "cohort"}, headers=auth_headers("doctor.demo")).status_code == 403
    session, _token = start_cohort(client, "admin.demo")
    assert session["mode"] == "cohort" and session["patient_count"] == len(patients())


def test_cohort_stream_updates_every_patient_and_retries_are_idempotent(client):
    session, token = start_cohort(client)
    first = emit(client, session["session_id"], token, 0)
    assert first["duplicate"] is False
    assert sorted(event["patient_id"] for event in first["events"]) == sorted(p["id"] for p in patients())
    assert {event["sequence"] for event in first["events"]} == {0}
    retry = emit(client, session["session_id"], token, 0)
    assert retry["duplicate"] is True
    assert [e["event_id"] for e in retry["events"]] == [e["event_id"] for e in first["events"]]
    history = client.get("/api/v1/observations", params={"patient_id": "P-SIM-003"}).json()
    assert history["count"] == 1
    # Receivers that reconnect recover the whole tick from the catch-up endpoint.
    missed = client.get(f"{LIVE}/events", params={"after_id": 0}).json()
    assert missed["count"] == len(patients())


def test_deteriorating_patients_alert_once_per_escalation_not_every_tick(client):
    session, token = start_cohort(client)
    for sequence in range(45):
        emit(client, session["session_id"], token, sequence)
    alerts = client.get("/api/v1/alerts", params={"limit": 100}, headers=auth_headers()).json()["items"]
    by_patient: dict[str, list[str]] = {}
    for alert in sorted(alerts, key=lambda item: item["id"]):
        by_patient.setdefault(alert["patient_id"], []).append(alert["severity"])
    worsening = {p["id"] for p in patients() if p["scenario"] == "worsening"}
    # Every worsening patient has deteriorated by sequence 45; recovering ones start high but never alert.
    assert set(by_patient) == worsening
    # One alert on reaching high and at most one more on escalating to critical.
    assert all(severities in (["high"], ["high", "critical"], ["critical"]) for severities in by_patient.values())
    # The ICU doctor sees only the ICU patients' alerts.
    icu = client.get("/api/v1/alerts", params={"limit": 100}, headers=auth_headers("doctor.demo")).json()["items"]
    assert icu and {get_patient(item["patient_id"])["ward"] for item in icu} == {"ICU"}

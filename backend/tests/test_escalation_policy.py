from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.escalation_policy import DEADLINES_MINUTES, POLICY_VERSION, evaluate_escalation


NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def alert(severity="high", status="open", minutes_ago=0):
    return {
        "id": 7,
        "patient_id": "DEMO-ESC-01",
        "severity": severity,
        "status": status,
        "created_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
    }


def test_high_deadline_boundary_and_metadata():
    before = evaluate_escalation(alert(minutes_ago=14), now=NOW)
    due = evaluate_escalation(alert(minutes_ago=15), now=NOW)
    assert before["review_due"] is False
    assert before["minutes_until_due"] == 1
    assert due["review_due"] is True
    assert due["reason"] == "unacknowledged_alert_exceeded_demo_review_deadline"
    assert due["policy_version"] == POLICY_VERSION
    assert due["notifications_sent"] is False
    assert due["clinical_policy"] is False


def test_severity_deadlines_and_low_has_no_deadline():
    assert DEADLINES_MINUTES["critical"] == 5
    assert DEADLINES_MINUTES["high"] == 15
    assert DEADLINES_MINUTES["medium"] == 60
    assert DEADLINES_MINUTES["low"] is None
    assert evaluate_escalation(alert("critical", minutes_ago=5), now=NOW)["review_due"] is True
    assert evaluate_escalation(alert("moderate", minutes_ago=60), now=NOW)["severity"] == "medium"
    low = evaluate_escalation(alert("low", minutes_ago=1000), now=NOW)
    assert low["review_due"] is False
    assert low["reason"] == "no_deadline_configured"


@pytest.mark.parametrize("status", ["acknowledged", "resolved"])
def test_closed_or_acknowledged_alerts_are_not_due(status):
    result = evaluate_escalation(alert(status=status, minutes_ago=120), now=NOW)
    assert result["review_due"] is False
    assert result["minutes_until_due"] is None
    assert result["reason"] == "alert_not_open"


def test_future_timestamp_clamps_elapsed_time_to_zero():
    future = alert()
    future["created_at"] = (NOW + timedelta(minutes=5)).isoformat()
    result = evaluate_escalation(future, now=NOW)
    assert result["elapsed_minutes"] == 0
    assert result["review_due"] is False


def test_naive_created_at_and_now_are_rejected():
    naive = alert()
    naive["created_at"] = "2026-10-11T11:00:00"
    with pytest.raises(ValueError, match="timezone"):
        evaluate_escalation(naive, now=NOW)
    with pytest.raises(ValueError, match="now"):
        evaluate_escalation(alert(), now=datetime(2026, 10, 11, 12, 0))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "escalation.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


def test_escalation_preview_fails_closed_if_token_not_configured(client, monkeypatch):
    monkeypatch.delenv("VITALGUARD_ALERT_ESCALATION_TOKEN", raising=False)
    response = client.get("/api/v1/alerts/escalation-preview")
    assert response.status_code == 503


def test_escalation_preview_requires_correct_bearer_token(client, monkeypatch):
    monkeypatch.setenv("VITALGUARD_ALERT_ESCALATION_TOKEN", "test-only-token")
    assert client.get("/api/v1/alerts/escalation-preview").status_code == 401
    assert client.get(
        "/api/v1/alerts/escalation-preview",
        headers={"Authorization": "Bearer wrong-token"},
    ).status_code == 401
    response = client.get(
        "/api/v1/alerts/escalation-preview",
        headers={"Authorization": "Bearer test-only-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["demo_only"] is True
    assert body["notifications_sent"] is False
    assert body["clinical_policy"] is False
    assert body["policy_version"] == POLICY_VERSION

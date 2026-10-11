from datetime import datetime, timedelta, timezone

import pytest

from app.escalation_policy import DEADLINES_MINUTES, POLICY_VERSION, evaluate_escalation


NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def alert(severity="high", status="open", minutes_ago=0):
    return {
        "id": 7,
        "severity": severity,
        "status": status,
        "created_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
    }


def test_high_alert_is_not_due_before_deadline():
    result = evaluate_escalation(alert(minutes_ago=14), now=NOW)
    assert result["review_due"] is False
    assert result["minutes_until_due"] == 1
    assert result["notifications_sent"] is False
    assert result["demo_only"] is True


def test_high_alert_is_due_at_deadline():
    result = evaluate_escalation(alert(minutes_ago=15), now=NOW)
    assert result["review_due"] is True
    assert result["reason"] == "unacknowledged_alert_exceeded_demo_review_deadline"


def test_critical_deadline_is_shorter_than_high():
    assert DEADLINES_MINUTES["critical"] == 5
    assert DEADLINES_MINUTES["critical"] < DEADLINES_MINUTES["high"]
    assert evaluate_escalation(alert("critical", minutes_ago=5), now=NOW)["review_due"] is True


def test_acknowledged_or_resolved_alerts_are_not_escalated():
    for status in ("acknowledged", "resolved"):
        result = evaluate_escalation(alert(status=status, minutes_ago=120), now=NOW)
        assert result["review_due"] is False
        assert result["minutes_until_due"] is None


def test_low_severity_has_no_deadline():
    result = evaluate_escalation(alert("low", minutes_ago=1000), now=NOW)
    assert result["deadline_minutes"] is None
    assert result["review_due"] is False
    assert result["reason"] == "no_deadline_configured"


def test_naive_timestamps_are_rejected():
    data = alert()
    data["created_at"] = "2026-10-11T11:00:00"
    with pytest.raises(ValueError, match="timezone"):
        evaluate_escalation(data, now=NOW)


def test_naive_now_is_rejected():
    with pytest.raises(ValueError, match="now"):
        evaluate_escalation(alert(), now=datetime(2026, 10, 11, 12, 0))


def test_result_has_policy_version_and_no_clinical_claim():
    result = evaluate_escalation(alert(), now=NOW)
    assert result["policy_version"] == POLICY_VERSION
    assert result["clinical_policy"] is False

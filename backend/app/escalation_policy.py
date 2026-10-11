"""Deterministic escalation preview for synthetic demo alerts.

This module computes workflow deadlines only. It does not page people, send
messages, or provide clinical triage. Thresholds are demo defaults, not care
standards.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

POLICY_VERSION = "demo-escalation-policy-0.1.0"
# Minutes before an unacknowledged alert is considered overdue for review.
DEADLINES_MINUTES = {"critical": 5, "high": 15, "medium": 60, "low": None}


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("created_at must be an ISO datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("created_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def evaluate_escalation(alert: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Return a deterministic due/overdue preview without sending notifications."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include a timezone")
    severity = str(alert.get("severity", "")).lower()
    status = str(alert.get("status", "")).lower()
    if severity not in DEADLINES_MINUTES:
        raise ValueError("unsupported alert severity")
    if status not in {"open", "acknowledged", "resolved"}:
        raise ValueError("unsupported alert status")

    deadline = DEADLINES_MINUTES[severity]
    created = _parse_datetime(alert.get("created_at"))
    elapsed = max(0.0, (now.astimezone(timezone.utc) - created).total_seconds() / 60)
    active = status == "open" and deadline is not None
    due = bool(active and elapsed >= deadline)
    return {
        "alert_id": alert.get("id"),
        "severity": severity,
        "status": status,
        "policy_version": POLICY_VERSION,
        "deadline_minutes": deadline,
        "elapsed_minutes": round(elapsed, 2),
        "review_due": due,
        "minutes_until_due": round(max(0.0, deadline - elapsed), 2) if active else None,
        "reason": (
            "unacknowledged_alert_exceeded_demo_review_deadline" if due else
            "within_demo_review_deadline" if active else
            "no_deadline_configured" if deadline is None else
            "alert_not_open"
        ),
        "demo_only": True,
        "notifications_sent": False,
        "clinical_policy": False,
    }

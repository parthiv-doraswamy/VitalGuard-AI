"""Deterministic review-deadline preview for synthetic alerts; no notifications are sent."""
from __future__ import annotations

import hmac
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import Header, HTTPException

POLICY_VERSION = "demo-escalation-policy-0.1.0"
# Illustrative workflow deadlines only; these are not clinical response standards.
DEADLINES_MINUTES: dict[str, int | None] = {
    "critical": 5,
    "high": 15,
    "medium": 60,
    "moderate": 60,  # Current risk labels use "moderate"; normalize to the policy's "medium".
    "low": None,
}


def authenticate_escalation_preview(authorization: str | None = Header(default=None)) -> dict[str, str]:
    """Require a separately configured server-side bearer token; fail closed if unset."""
    expected = os.getenv("VITALGUARD_ALERT_ESCALATION_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Alert escalation preview is not configured; set VITALGUARD_ALERT_ESCALATION_TOKEN.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token", headers={"WWW-Authenticate": "Bearer"})
    return {"sub": "escalation-preview-token"}


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("created_at must be an ISO datetime with a timezone") from exc
    else:
        raise ValueError("created_at must be an ISO datetime with a timezone")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("created_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def evaluate_escalation(alert: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Return a due/not-due preview. Does not send email, push, SMS, or pager alerts."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include a timezone")

    raw_severity = str(alert.get("severity", "")).lower()
    status = str(alert.get("status", "")).lower()
    if raw_severity not in DEADLINES_MINUTES:
        raise ValueError("unsupported alert severity")
    if status not in {"open", "acknowledged", "resolved"}:
        raise ValueError("unsupported alert status")

    severity = "medium" if raw_severity == "moderate" else raw_severity
    deadline = DEADLINES_MINUTES[raw_severity]
    created = _parse_datetime(alert.get("created_at"))
    elapsed = max(0.0, (now.astimezone(timezone.utc) - created).total_seconds() / 60)
    active = status == "open" and deadline is not None
    due = bool(active and elapsed >= deadline)

    if due:
        reason = "unacknowledged_alert_exceeded_demo_review_deadline"
    elif active:
        reason = "within_demo_review_deadline"
    elif deadline is None:
        reason = "no_deadline_configured"
    else:
        reason = "alert_not_open"

    return {
        "alert_id": alert.get("id"),
        "patient_id": alert.get("patient_id"),
        "severity": severity,
        "status": status,
        "created_at": created.isoformat(),
        "policy_version": POLICY_VERSION,
        "deadline_minutes": deadline,
        "elapsed_minutes": round(elapsed, 2),
        "review_due": due,
        "minutes_until_due": round(max(0.0, deadline - elapsed), 2) if active else None,
        "reason": reason,
        "demo_only": True,
        "notifications_sent": False,
        "clinical_policy": False,
    }

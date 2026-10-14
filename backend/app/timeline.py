"""Combine persisted synthetic observations, alerts, and audit events for a demo timeline."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _timestamp_key(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return 0.0


def build_patient_timeline(patient_id: str, observations: list[dict[str, Any]],
                           alerts: list[dict[str, Any]], audit_events: list[dict[str, Any]],
                           limit: int = 50) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for record in observations:
        prediction = record.get("prediction") or {}
        events.append({
            "event_id": "observation:" + str(record["id"]),
            "type": "observation",
            "occurred_at": record.get("created_at"),
            "patient_id": patient_id,
            "summary": "Synthetic risk prediction recorded",
            "observation_id": record["id"],
            "risk_score": prediction.get("risk_score"),
            "risk_level": prediction.get("risk_level"),
            "model_version": record.get("model_version"),
            "demo_only": True,
        })
    for alert in alerts:
        events.append({
            "event_id": "alert:" + str(alert["id"]),
            "type": "alert",
            "occurred_at": alert.get("created_at"),
            "patient_id": patient_id,
            "summary": alert.get("title", "Synthetic alert"),
            "alert_id": alert["id"],
            "severity": alert.get("severity"),
            "status": alert.get("status"),
            "demo_only": True,
        })
    for audit in audit_events:
        events.append({
            "event_id": "audit:" + str(audit["id"]),
            "type": "alert_audit",
            "occurred_at": audit.get("created_at"),
            "patient_id": patient_id,
            "summary": "Alert " + str(audit.get("action", "updated")),
            "alert_id": int(audit["entity_id"]),
            "action": audit.get("action"),
            "actor": audit.get("actor"),
            "demo_only": True,
        })
    events.sort(key=lambda event: (_timestamp_key(event.get("occurred_at")), event["event_id"]), reverse=True)
    return {
        "patient_id": patient_id,
        "items": events[:limit],
        "count": min(len(events), limit),
        "available_event_count": len(events),
        "limit": limit,
        "source": "persisted synthetic observations, alerts, and alert audit events",
        "demo_only": True,
        "disclaimer": "Synthetic demonstration timeline only; not a medical record or clinical workflow.",
    }

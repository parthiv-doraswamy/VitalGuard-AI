"""Persistence helpers for the synthetic demo alert workflow."""
from __future__ import annotations
import json
from typing import Any
from sqlalchemy import func, insert, select, update, desc
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from .event_broker import record_event
from .storage import get_engine
from .storage_schema import alerts, audit_events

VALID_STATUSES = {"open", "acknowledged", "resolved"}
MAX_AUDIT_EVENTS = 500


def _serialize(row: Any) -> dict:
    item = dict(row)
    for key in ("created_at", "acknowledged_at", "resolved_at"):
        if item.get(key) is not None and hasattr(item[key], "isoformat"):
            item[key] = item[key].isoformat()
    item["details"] = json.loads(item.pop("details_json"))
    return item


def _serialize_audit(row: Any) -> dict:
    item = dict(row)
    item["details"] = json.loads(item.pop("details_json"))
    if item.get("created_at") is not None and hasattr(item["created_at"], "isoformat"):
        item["created_at"] = item["created_at"].isoformat()
    return item


def _audit(connection, entity_id: str, action: str, actor: str, details: dict) -> None:
    connection.execute(insert(audit_events).values(
        entity_type="alert", entity_id=entity_id, action=action,
        actor=actor, details_json=json.dumps(details, separators=(",", ":")),
    ))


def alert_created_event(alert: dict, observation_id: int | None = None, session_id: str | None = None) -> dict:
    return {"type": "alert.created", "event_id": alert["id"], "observation_id": observation_id,
            "session_id": session_id, "alert": alert, "demo_only": True}


def insert_alert(connection: Connection, *, patient_id: str, event_key: str, severity: str,
                 title: str, details: dict, emit_event: bool = True) -> dict:
    """Insert an alert and its creation audit row inside the caller's transaction.

    With emit_event, the alert.created outbox event is written in the same transaction.
    """
    result = connection.execute(insert(alerts).values(
        patient_id=patient_id, event_key=event_key, severity=severity,
        status="open", title=title,
        details_json=json.dumps(details, separators=(",", ":")),
    ))
    row = connection.execute(select(alerts).where(alerts.c.id == result.inserted_primary_key[0])).mappings().one()
    _audit(connection, str(row["id"]), "created", "demo-system", {"severity": severity, "event_key": event_key})
    alert = _serialize(row)
    # Push deliveries are queued in this same transaction: they exist only if the alert commits.
    from .notification_service import enqueue_for_alert
    enqueue_for_alert(connection, alert)
    if emit_event:
        record_event(connection, "alert.created", alert_created_event(alert, details.get("observation_id")),
                     aggregate_id=alert["id"])
    return alert


def create_alert(*, patient_id: str, event_key: str, severity: str, title: str, details: dict) -> dict | None:
    """Create one alert per source event; duplicate event keys are ignored."""
    engine = get_engine()
    try:
        with engine.begin() as connection:
            existing = connection.execute(select(alerts).where(alerts.c.event_key == event_key)).mappings().first()
            if existing:
                return _serialize(existing)
            return insert_alert(connection, patient_id=patient_id, event_key=event_key,
                                severity=severity, title=title, details=details)
    except IntegrityError:
        # A concurrent request may win the unique event_key insert.
        with engine.connect() as connection:
            row = connection.execute(select(alerts).where(alerts.c.event_key == event_key)).mappings().first()
            return _serialize(row) if row else None


def get_alert(alert_id: int) -> dict | None:
    with get_engine().connect() as connection:
        row = connection.execute(select(alerts).where(alerts.c.id == alert_id)).mappings().first()
    return _serialize(row) if row else None


def list_alerts_by_event_keys(event_keys: list[str]) -> list[dict]:
    if not event_keys:
        return []
    with get_engine().connect() as connection:
        rows = connection.execute(select(alerts).where(alerts.c.event_key.in_(event_keys))).mappings().all()
    return [_serialize(row) for row in rows]


def list_alerts(status: str | None = None, patient_id: str | None = None, limit: int = 50,
                before_id: int | None = None, patient_ids: set[str] | None = None) -> list[dict]:
    """Newest first. `patient_ids`, when given, restricts results to those patients (an empty set matches none)."""
    query = select(alerts)
    if patient_ids is not None:
        query = query.where(alerts.c.patient_id.in_(sorted(patient_ids)))
    if status:
        query = query.where(alerts.c.status == status)
    if patient_id:
        query = query.where(alerts.c.patient_id == patient_id)
    if before_id is not None:
        query = query.where(alerts.c.id < before_id)
    query = query.order_by(desc(alerts.c.id)).limit(limit)
    with get_engine().connect() as connection:
        return [_serialize(row) for row in connection.execute(query).mappings().all()]


def transition_alert(alert_id: int, action: str, actor: str) -> dict | None:
    """Apply a state change with a conditional UPDATE.

    The WHERE clause on the current status means two concurrent requests
    cannot both transition the alert, so each audit row matches a real change.
    """
    if action not in {"acknowledge", "resolve"}:
        raise ValueError("Unsupported alert action")
    with get_engine().begin() as connection:
        row = connection.execute(select(alerts.c.id).where(alerts.c.id == alert_id)).first()
        if not row:
            return None
        if action == "acknowledge":
            changed = connection.execute(update(alerts)
                .where(alerts.c.id == alert_id, alerts.c.status == "open")
                .values(status="acknowledged", acknowledged_by=actor, acknowledged_at=func.now())).rowcount
            if changed:
                _audit(connection, str(alert_id), "acknowledged", actor, {})
        else:
            changed = connection.execute(update(alerts)
                .where(alerts.c.id == alert_id, alerts.c.status != "resolved")
                .values(status="resolved", resolved_at=func.now())).rowcount
            if changed:
                _audit(connection, str(alert_id), "resolved", actor, {})
        updated = _serialize(connection.execute(select(alerts).where(alerts.c.id == alert_id)).mappings().one())
        if changed:
            record_event(connection, "alert.updated", {"type": "alert.updated", "event_id": alert_id, "action": action,
                         "actor": actor, "alert": updated, "demo_only": True}, aggregate_id=alert_id)
        return updated


def list_alert_audit(alert_id: int, limit: int = MAX_AUDIT_EVENTS) -> list[dict]:
    with get_engine().connect() as connection:
        rows = connection.execute(select(audit_events).where(
            audit_events.c.entity_type == "alert",
            audit_events.c.entity_id == str(alert_id)
        ).order_by(audit_events.c.id).limit(limit)).mappings().all()
    return [_serialize_audit(row) for row in rows]


def list_audit_for_alerts(alert_ids: list[int], limit: int = MAX_AUDIT_EVENTS) -> list[dict]:
    """Fetch audit rows for several alerts in one bounded query (no per-alert round trips)."""
    if not alert_ids:
        return []
    with get_engine().connect() as connection:
        rows = connection.execute(select(audit_events).where(
            audit_events.c.entity_type == "alert",
            audit_events.c.entity_id.in_([str(alert_id) for alert_id in alert_ids])
        ).order_by(desc(audit_events.c.id)).limit(limit)).mappings().all()
    return [_serialize_audit(row) for row in rows]

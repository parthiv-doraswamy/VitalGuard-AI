"""Persistence helpers for the synthetic demo alert workflow."""
from __future__ import annotations
import json
from typing import Any
from sqlalchemy import insert, select, update, desc
from sqlalchemy.exc import IntegrityError
from .storage import _engine
from .storage_schema import alerts, audit_events

VALID_STATUSES = {"open", "acknowledged", "resolved"}


def _serialize(row: Any) -> dict:
    item = dict(row)
    for key in ("created_at", "acknowledged_at", "resolved_at"):
        if item.get(key) is not None and hasattr(item[key], "isoformat"):
            item[key] = item[key].isoformat()
    item["details"] = json.loads(item.pop("details_json"))
    return item


def _audit(connection, entity_id: str, action: str, actor: str, details: dict) -> None:
    connection.execute(insert(audit_events).values(
        entity_type="alert", entity_id=entity_id, action=action,
        actor=actor, details_json=json.dumps(details, separators=(",", ":")),
    ))


def create_alert(*, patient_id: str, event_key: str, severity: str, title: str, details: dict) -> dict | None:
    """Create one alert per source event; duplicate event keys are ignored."""
    engine = _engine()
    try:
        with engine.begin() as connection:
            existing = connection.execute(select(alerts).where(alerts.c.event_key == event_key)).mappings().first()
            if existing:
                return _serialize(existing)
            result = connection.execute(insert(alerts).values(
                patient_id=patient_id, event_key=event_key, severity=severity,
                status="open", title=title,
                details_json=json.dumps(details, separators=(",", ":")),
            ))
            row = connection.execute(select(alerts).where(alerts.c.id == result.inserted_primary_key[0])).mappings().one()
            _audit(connection, str(row["id"]), "created", "demo-system", {"severity": severity, "event_key": event_key})
            return _serialize(row)
    except IntegrityError:
        # A concurrent request may win the unique event_key insert.
        with engine.connect() as connection:
            row = connection.execute(select(alerts).where(alerts.c.event_key == event_key)).mappings().first()
            return _serialize(row) if row else None
    finally:
        engine.dispose()


def list_alerts(status: str | None = None, patient_id: str | None = None, limit: int = 50) -> list[dict]:
    engine = _engine()
    try:
        query = select(alerts)
        if status:
            query = query.where(alerts.c.status == status)
        if patient_id:
            query = query.where(alerts.c.patient_id == patient_id)
        query = query.order_by(desc(alerts.c.id)).limit(limit)
        with engine.connect() as connection:
            return [_serialize(row) for row in connection.execute(query).mappings().all()]
    finally:
        engine.dispose()


def transition_alert(alert_id: int, action: str, actor: str) -> dict | None:
    if action not in {"acknowledge", "resolve"}:
        raise ValueError("Unsupported alert action")
    engine = _engine()
    try:
        with engine.begin() as connection:
            row = connection.execute(select(alerts).where(alerts.c.id == alert_id)).mappings().first()
            if not row:
                return None
            if row["status"] == "resolved":
                return _serialize(row)
            if action == "acknowledge" and row["status"] == "open":
                connection.execute(update(alerts).where(alerts.c.id == alert_id).values(
                    status="acknowledged", acknowledged_by=actor))
                _audit(connection, str(alert_id), "acknowledged", actor, {})
            elif action == "resolve":
                connection.execute(update(alerts).where(alerts.c.id == alert_id).values(status="resolved"))
                _audit(connection, str(alert_id), "resolved", actor, {})
            updated = connection.execute(select(alerts).where(alerts.c.id == alert_id)).mappings().one()
            return _serialize(updated)
    finally:
        engine.dispose()


def list_alert_audit(alert_id: int) -> list[dict]:
    engine = _engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(select(audit_events).where(
                audit_events.c.entity_type == "alert",
                audit_events.c.entity_id == str(alert_id)
            ).order_by(audit_events.c.id)).mappings().all()
        output = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            if item.get("created_at") is not None and hasattr(item["created_at"], "isoformat"):
                item["created_at"] = item["created_at"].isoformat()
            output.append(item)
        return output
    finally:
        engine.dispose()

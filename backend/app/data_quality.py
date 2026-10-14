"""Data freshness and completeness checks for synthetic demo observations."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

REQUIRED_VITALS = (
    "heart_rate", "spo2", "systolic_bp", "diastolic_bp",
    "temperature", "respiratory_rate",
)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def assess_observations(records: list[dict[str, Any]], *, stale_after_seconds: int = 300,
                        now: datetime | None = None) -> dict[str, Any]:
    """Return one quality summary per patient from observation history.

    Uses only saved synthetic observations. The API caller supplies a bounded
    history page; this function never interprets missing vitals as normal.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        patient_id = record.get("patient_id")
        if not patient_id:
            continue
        existing = latest.get(patient_id)
        if existing is None or int(record.get("id", 0)) > int(existing.get("id", 0)):
            latest[patient_id] = record

    patients = []
    for patient_id, record in latest.items():
        timestamp = _parse_timestamp(record.get("created_at"))
        age_seconds = max(0, int((current - timestamp).total_seconds())) if timestamp else None
        inputs = record.get("inputs") or {}
        missing = [field for field in REQUIRED_VITALS if inputs.get(field) is None]
        if timestamp is None:
            status = "unknown"
        elif age_seconds is not None and age_seconds > stale_after_seconds:
            status = "stale"
        elif missing:
            status = "incomplete"
        else:
            status = "fresh"
        patients.append({
            "patient_id": patient_id,
            "latest_observation_id": record.get("id"),
            "last_observed_at": record.get("created_at"),
            "age_seconds": age_seconds,
            "status": status,
            "missing_fields": missing,
            "demo_only": True,
        })
    patients.sort(key=lambda item: ({"stale": 0, "incomplete": 1, "unknown": 2, "fresh": 3}[item["status"]], item["patient_id"]))
    return {
        "items": patients,
        "count": len(patients),
        "stale_after_seconds": stale_after_seconds,
        "source": "persisted synthetic observation history",
        "demo_only": True,
        "disclaimer": "Missing or stale data must never be interpreted as normal. Synthetic demo only.",
    }

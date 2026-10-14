"""Score, persist, then publish one synthetic observation.

Transactional contract:
1. The observation row and, when the score crosses the alert threshold, its
   alert and alert-creation audit row are written in ONE database transaction.
   Either all of them commit or none do.
2. WebSocket events are published only after that transaction has committed.
   A failed write raises before any event is sent, so clients never see an
   event for a record that does not exist.
3. Broadcasting is best effort; a dropped client does not undo the commit.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Callable
from sqlalchemy.engine import Connection
from starlette.concurrency import run_in_threadpool
from .alert_service import insert_alert
from .live_events import hub
from .model import active_model, explain, predict_probability, risk_level
from .schemas import RiskPrediction
from .storage import get_engine, insert_observation

ALERT_SCORE_THRESHOLD = 65


def score_observation(patient_id: str, values: dict[str, Any]) -> RiskPrediction:
    probability = predict_probability(values)
    score = round(probability * 100)
    return RiskPrediction(patient_id=patient_id, risk_score=score, risk_level=risk_level(score),
        model_probability=round(probability, 4), factors=explain(values), model_version=active_model().version)


def _alert_for(patient_id: str, result: RiskPrediction, observation_id: int, values: dict[str, Any]) -> dict | None:
    if result.risk_score < ALERT_SCORE_THRESHOLD:
        return None
    level = result.risk_level
    return {"patient_id": patient_id, "event_key": f"observation:{observation_id}:elevated-risk",
        "severity": "critical" if level == "critical" else "high", "title": f"{level.title()} demo risk score",
        "details": {"observation_id": observation_id, "risk_score": result.risk_score, "risk_level": level,
                    "vitals": values, "demo_only": True}}


def persist_observation(patient_id: str, values: dict[str, Any], result: RiskPrediction,
                        raise_alert: bool, *, session_id: str | None = None, sequence: int | None = None,
                        within: Callable[[Connection, dict[str, Any]], None] | None = None,
                        ) -> tuple[dict[str, Any], dict | None]:
    """Write the observation (and optional alert) atomically; returns the committed rows.

    `within` runs inside the same transaction after the inserts; raising from it
    rolls everything back (used by stream sessions to advance their sequence).
    """
    with get_engine().begin() as connection:
        saved = insert_observation(connection, patient_id, values, result.model_dump(),
                                   session_id=session_id, sequence=sequence)
        alert = None
        if raise_alert:
            spec = _alert_for(patient_id, result, saved["id"], values)
            if spec:
                alert = insert_alert(connection, **spec)
        if within:
            within(connection, saved)
    return saved, alert


def alert_summary(alert: dict | None) -> dict | None:
    if not alert:
        return None
    return {key: alert.get(key) for key in ("id", "patient_id", "severity", "status", "title", "created_at")}


def observation_event(record: dict[str, Any], alert: dict | None = None, **timing: str | None) -> dict[str, Any]:
    """The single event contract for a committed observation.

    Built from the persisted row, so the WebSocket broadcast and the REST
    catch-up endpoint return identical data for the same event_id.
    """
    prediction = {**record["prediction"], "observation_id": record["id"], "created_at": record["created_at"]}
    return {"type": "observation.created", "event_id": record["id"], "observation_id": record["id"],
        "session_id": record.get("session_id"), "sequence": record.get("sequence"),
        "patient_id": record["patient_id"], "created_at": record["created_at"], "timestamp": record["created_at"],
        "observation": record["inputs"], "model_version": record["model_version"], "prediction": prediction,
        "alert": alert_summary(alert), "server_received_at": timing.get("server_received_at"),
        "published_at": timing.get("published_at"), "demo_only": True, "data_origin": "synthetic"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def publish_committed(saved: dict[str, Any], alert: dict | None, *, server_received_at: str | None = None) -> dict[str, Any]:
    """Broadcast an observation (and its alert) that has already committed."""
    event = observation_event(saved, alert, server_received_at=server_received_at, published_at=utc_now())
    await hub.broadcast(event)
    if alert:
        await hub.broadcast({"type": "alert.created", "event_id": alert["id"], "observation_id": saved["id"],
            "session_id": saved.get("session_id"), "alert": alert, "demo_only": True})
    return event


async def record_observation(patient_id: str, values: dict[str, Any], *, raise_alert: bool) -> RiskPrediction:
    received_at = utc_now()
    result = score_observation(patient_id, values)
    # Database I/O is blocking; keep it off the event loop.
    saved, alert = await run_in_threadpool(persist_observation, patient_id, values, result, raise_alert)
    response = result.model_copy(update={"observation_id": saved["id"], "created_at": saved["created_at"]})
    await publish_committed(saved, alert, server_received_at=received_at)
    return response

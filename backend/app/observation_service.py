"""Score, persist, then publish one synthetic observation.

Transactional contract:
1. The observation row and, when the score crosses the alert threshold, its
   alert and alert-creation audit row are written in ONE database transaction.
   Either all of them commit or none do.
2. The matching live events are written to the transactional outbox in that same
   transaction (event_broker.record_event) and are delivered to WebSocket clients
   on every instance only after commit. A failed write leaves no event behind.
3. Delivery is best effort per client; a dropped client recovers from
   GET /api/v1/events and never undoes the commit.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Callable
from sqlalchemy import select
from sqlalchemy.engine import Connection
from starlette.concurrency import run_in_threadpool
from .alert_service import alert_created_event, insert_alert
from .event_broker import events, record_event
from .model import active_model, explain, predict_probability, risk_level
from .schemas import RiskPrediction
from .storage import get_engine, insert_observation, list_stream_observations
from .storage_schema import alerts as alerts_table

ALERT_SCORE_THRESHOLD = 65
_LEVEL_RANK = {"low": 0, "moderate": 1, "high": 2, "critical": 3}


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
                        server_received_at: str | None = None,
                        ) -> tuple[dict[str, Any], dict | None, dict[str, Any]]:
    """Write the observation, optional alert and their outbox events atomically.

    Returns (observation row, alert row or None, observation event envelope).

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
                alert = insert_alert(connection, **spec, emit_event=False)
        if within:
            within(connection, saved)
        event = record_event(connection, "observation.created",
                             observation_event(saved, alert, server_received_at=server_received_at),
                             session_id=session_id, aggregate_id=saved["id"])
        if alert:
            record_event(connection, "alert.created", alert_created_event(alert, saved["id"], session_id),
                         session_id=session_id, aggregate_id=alert["id"])
    return saved, alert, event


def _unresolved_alert_rank(connection: Connection, patient_id: str) -> int:
    """Highest severity rank among the patient's open or acknowledged alerts (0 if none)."""
    severities = connection.execute(select(alerts_table.c.severity).where(
        alerts_table.c.patient_id == patient_id, alerts_table.c.status != "resolved")).scalars().all()
    return max((_LEVEL_RANK.get(severity, 0) for severity in severities), default=0)


def persist_cohort_tick(session_id: str, sequence: int,
                        items: list[tuple[str, dict[str, Any], RiskPrediction]], *,
                        within: Callable[[Connection, list[dict[str, Any]]], None] | None = None,
                        server_received_at: str | None = None) -> list[dict[str, Any]]:
    """Write one stream sequence for every cohort patient, their alerts and outbox events atomically.

    Alert rule (cohort streams): a patient raises an alert only when its risk level rises
    into high or critical compared with its previous sequence, and it has no unresolved
    alert of that severity or higher already. A deteriorated patient therefore alerts once
    on reaching "high" and once more on escalating to "critical", not on every tick.
    """
    events: list[dict[str, Any]] = []
    with get_engine().begin() as connection:
        previous = {record["patient_id"]: record["prediction"]["risk_level"]
                    for record in (list_stream_observations(session_id, sequence - 1, connection) if sequence else [])}
        saved_rows = []
        for patient_id, values, result in items:
            saved = insert_observation(connection, patient_id, values, result.model_dump(),
                                       session_id=session_id, sequence=sequence)
            saved_rows.append(saved)
            alert = None
            rank = _LEVEL_RANK[result.risk_level]
            rose = patient_id in previous and rank > _LEVEL_RANK.get(previous[patient_id], 0)
            if rose and result.risk_score >= ALERT_SCORE_THRESHOLD and rank > _unresolved_alert_rank(connection, patient_id):
                spec = _alert_for(patient_id, result, saved["id"], values)
                if spec:
                    alert = insert_alert(connection, **spec, emit_event=False)
            event = record_event(connection, "observation.created",
                                 observation_event(saved, alert, server_received_at=server_received_at),
                                 session_id=session_id, aggregate_id=saved["id"])
            events.append(event)
            if alert:
                record_event(connection, "alert.created", alert_created_event(alert, saved["id"], session_id),
                             session_id=session_id, aggregate_id=alert["id"])
        if within:
            within(connection, saved_rows)
    return events


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


async def record_observation(patient_id: str, values: dict[str, Any], *, raise_alert: bool) -> RiskPrediction:
    received_at = utc_now()
    result = score_observation(patient_id, values)
    # Database I/O is blocking; keep it off the event loop.
    saved, _alert, _event = await run_in_threadpool(lambda: persist_observation(
        patient_id, values, result, raise_alert, server_received_at=received_at))
    response = result.model_copy(update={"observation_id": saved["id"], "created_at": saved["created_at"]})
    await events.after_commit()
    return response

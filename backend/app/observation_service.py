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
from typing import Any
from starlette.concurrency import run_in_threadpool
from .alert_service import insert_alert
from .live_events import hub
from .model import MODEL_VERSION, explain, predict_probability, risk_level
from .schemas import RiskPrediction
from .storage import get_engine, insert_observation

ALERT_SCORE_THRESHOLD = 65


def score_observation(patient_id: str, values: dict[str, Any]) -> RiskPrediction:
    probability = predict_probability(values)
    score = round(probability * 100)
    return RiskPrediction(patient_id=patient_id, risk_score=score, risk_level=risk_level(score),
        model_probability=round(probability, 4), factors=explain(values), model_version=MODEL_VERSION)


def _alert_for(patient_id: str, result: RiskPrediction, observation_id: int, values: dict[str, Any]) -> dict | None:
    if result.risk_score < ALERT_SCORE_THRESHOLD:
        return None
    level = result.risk_level
    return {"patient_id": patient_id, "event_key": f"observation:{observation_id}:elevated-risk",
        "severity": "critical" if level == "critical" else "high", "title": f"{level.title()} demo risk score",
        "details": {"observation_id": observation_id, "risk_score": result.risk_score, "risk_level": level,
                    "vitals": values, "demo_only": True}}


def persist_observation(patient_id: str, values: dict[str, Any], result: RiskPrediction,
                        raise_alert: bool) -> tuple[dict[str, Any], dict | None]:
    """Write the observation (and optional alert) atomically; returns the committed rows."""
    with get_engine().begin() as connection:
        saved = insert_observation(connection, patient_id, values, result.model_dump())
        alert = None
        if raise_alert:
            spec = _alert_for(patient_id, result, saved["id"], values)
            if spec:
                alert = insert_alert(connection, **spec)
    return saved, alert


async def record_observation(patient_id: str, values: dict[str, Any], *, raise_alert: bool) -> RiskPrediction:
    result = score_observation(patient_id, values)
    # Database I/O is blocking; keep it off the event loop.
    saved, alert = await run_in_threadpool(persist_observation, patient_id, values, result, raise_alert)
    response = result.model_copy(update={"observation_id": saved["id"], "created_at": saved["created_at"]})
    await hub.broadcast({"type": "observation.created", "event_id": saved["id"],
        "patient_id": patient_id, "created_at": saved["created_at"], "observation": values,
        "prediction": response.model_dump(), "demo_only": True})
    if alert:
        await hub.broadcast({"type": "alert.created", "event_id": alert["id"], "alert": alert, "demo_only": True})
    return response

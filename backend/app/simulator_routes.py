"""Demo-only API for submitting deterministic synthetic observations."""
from typing import Literal
from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from .event_broker import events
from .observation_service import record_observation, utc_now
from .schemas import RiskPrediction, StreamObservationRequest, StreamStartRequest
from .simulator import observation_for_step
from . import stream_service

router = APIRouter(prefix="/api/v1/demo", tags=["demo-simulator"])

class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: str = Field(default="DEMO-LIVE-001", min_length=1, max_length=64)
    scenario: Literal["stable", "worsening", "recovering"] = "stable"
    step: int = Field(default=0, ge=0, le=1000)

@router.post("/observations", response_model=RiskPrediction)
async def submit_demo_observation(payload: SimulationRequest):
    """Generate, score, persist, then broadcast one fictional observation."""
    values = observation_for_step(payload.scenario, payload.step)
    # The simulator has never raised alerts; that behavior is kept unchanged.
    return await record_observation(payload.patient_id, values, raise_alert=False)


live_router = APIRouter(prefix="/api/v1/live-demo", tags=["live-demo-stream"])


@live_router.get("/config")
def live_demo_config():
    return {"producer_key_required": stream_service.producer_key_required(),
            "max_sequence": stream_service.MAX_SEQUENCE, "min_interval_ms": stream_service.MIN_INTERVAL_MS,
            "max_interval_ms": stream_service.MAX_INTERVAL_MS,
            "idle_timeout_seconds": stream_service.idle_timeout_seconds(),
            "active_session": stream_service.current_session(), "demo_only": True}


@live_router.get("/sessions/current")
def current_stream_session():
    return {"session": stream_service.current_session(), "demo_only": True}


@live_router.get("/sessions/{session_id}")
def stream_session(session_id: str):
    return {"session": stream_service.get_session(session_id), "demo_only": True}


@live_router.post("/sessions", status_code=201)
async def start_stream(payload: StreamStartRequest,
                       x_demo_producer_key: str | None = Header(default=None)):
    """Start the single active producer session. The producer token is returned only here."""
    session, token, replaced = await run_in_threadpool(stream_service.start_session,
        scenario=payload.scenario, patient_id=payload.patient_id, interval_ms=payload.interval_ms,
        takeover=payload.takeover, producer_key=x_demo_producer_key)
    # stream.state events were written to the outbox in the same transaction.
    await events.after_commit()
    return {"session": session, "producer_token": token, "replaced_session": replaced, "demo_only": True}


async def _control(session_id: str, token: str | None, action: str):
    session, changed = await run_in_threadpool(stream_service.control_session, session_id, token, action)
    if changed:
        await events.after_commit()
    return {"session": session, "changed": changed, "demo_only": True}


@live_router.post("/sessions/{session_id}/pause")
async def pause_stream(session_id: str, x_producer_token: str | None = Header(default=None)):
    return await _control(session_id, x_producer_token, "pause")


@live_router.post("/sessions/{session_id}/resume")
async def resume_stream(session_id: str, x_producer_token: str | None = Header(default=None)):
    return await _control(session_id, x_producer_token, "resume")


@live_router.post("/sessions/{session_id}/stop")
async def stop_stream(session_id: str, x_producer_token: str | None = Header(default=None)):
    return await _control(session_id, x_producer_token, "stop")


@live_router.post("/sessions/{session_id}/observations")
async def emit_stream_observation(session_id: str, payload: StreamObservationRequest,
                                  x_producer_token: str | None = Header(default=None)):
    """Generate, score and persist the next fictional observation, then broadcast it after commit.

    Retrying a sequence that already committed returns the original event with
    duplicate=true; no new record, alert or broadcast is created.
    """
    received_at = utc_now()
    event, duplicate = await run_in_threadpool(stream_service.emit_observation,
        session_id, x_producer_token, payload.sequence, received_at)
    if not duplicate:
        await events.after_commit()
    return {"event": event, "duplicate": duplicate, "demo_only": True}


@live_router.get("/events")
def stream_events(after_id: int = Query(default=0, ge=0), session_id: str | None = Query(default=None, max_length=36),
                  limit: int = Query(default=100, ge=1, le=100)):
    """Committed observation events after `after_id`, oldest first, in the broadcast contract.

    Receivers call this after reconnecting to recover events missed while offline.
    """
    items = stream_service.missed_events(after_id, session_id, limit)
    return {"items": items, "count": len(items), "limit": limit,
            "next_after_id": items[-1]["event_id"] if len(items) == limit else None, "demo_only": True}

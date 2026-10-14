"""Synchronized live-demo stream sessions (synthetic data only).

One producer (Laptop A) owns a session and asks the backend to emit the next
fictional observation by sequence number. The backend generates it with the
existing deterministic simulator, scores it, persists it, and broadcasts the
committed result to every connected dashboard (Laptop B), which never computes
its own score.

Guarantees:
- Ownership: control and emit calls need the producer token returned once at
  session start (only its SHA-256 hash is stored).
- One active producer: a unique `active_slot` column allows at most one
  running/paused session. Starting another returns 409 unless the caller
  explicitly takes over, or the active session has been idle past the timeout.
- Idempotency: (session_id, sequence) is unique on observations, and the
  session's next_sequence advances in the same transaction as the insert.
  Retrying a sequence returns the original event without a new record, alert
  or broadcast.
- Optional start permission: when VITALGUARD_STREAM_PRODUCER_KEY is set, starting
  a stream requires the X-Demo-Producer-Key header to match it.
"""
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from .alert_service import list_alerts_by_event_keys
from .event_broker import event_for, record_event
from .observation_service import observation_event, persist_observation, score_observation
from .simulator import observation_for_step
from .storage import get_engine, get_stream_observation, list_observations
from .storage_schema import stream_sessions

MAX_SEQUENCE = 1000
MIN_INTERVAL_MS = 500
MAX_INTERVAL_MS = 10000
MIN_EMIT_GAP_SECONDS = 0.2
ACTIVE_STATUSES = ("running", "paused")


class StreamError(Exception):
    def __init__(self, status_code: int, code: str, detail: str, **extra: Any) -> None:
        super().__init__(detail)
        self.status_code, self.code, self.detail, self.extra = status_code, code, detail, extra


def idle_timeout_seconds() -> int:
    return int(os.getenv("VITALGUARD_STREAM_IDLE_TIMEOUT_SECONDS", "120"))


def producer_key_required() -> bool:
    return bool(os.getenv("VITALGUARD_STREAM_PRODUCER_KEY", "").strip())


def _check_producer_key(provided: str | None) -> None:
    expected = os.getenv("VITALGUARD_STREAM_PRODUCER_KEY", "").strip()
    if expected and not hmac.compare_digest((provided or "").encode(), expected.encode()):
        raise StreamError(403, "producer_key_invalid", "A valid demo producer key is required to start a stream.")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    # SQLite returns naive UTC timestamps.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _iso(value: datetime | None) -> str | None:
    value = _aware(value)
    return value.isoformat() if value else None


def public_session(row: Any) -> dict[str, Any]:
    """Session view safe to show any viewer: never includes the token hash."""
    return {"session_id": row["id"], "patient_id": row["patient_id"], "scenario": row["scenario"],
            "status": row["status"], "interval_ms": row["interval_ms"], "next_sequence": row["next_sequence"],
            "events_emitted": row["next_sequence"], "last_observation_id": row["last_observation_id"],
            "created_at": _iso(row["created_at"]), "updated_at": _iso(row["updated_at"]),
            "last_emit_at": _iso(row["last_emit_at"]), "stopped_at": _iso(row["stopped_at"]),
            "stop_reason": row["stop_reason"], "max_sequence": MAX_SEQUENCE, "demo_only": True}


def _last_activity(row: Any) -> datetime:
    return _aware(row["last_emit_at"]) or _aware(row["updated_at"]) or _aware(row["created_at"]) or _now()


def _is_idle(row: Any) -> bool:
    return _now() - _last_activity(row) > timedelta(seconds=idle_timeout_seconds())


def _active(connection: Connection) -> Any:
    return connection.execute(select(stream_sessions).where(stream_sessions.c.active_slot == 1)).mappings().first()


def _load(connection: Connection, session_id: str) -> Any:
    row = connection.execute(select(stream_sessions).where(stream_sessions.c.id == session_id)).mappings().first()
    if row is None:
        raise StreamError(404, "session_not_found", "Stream session not found.")
    return row


def _authorize(row: Any, token: str | None) -> None:
    if not token or not hmac.compare_digest(_hash(token), row["token_hash"]):
        raise StreamError(403, "not_session_owner", "This browser does not own the stream session.")


def _state_event(connection: Connection, session_id: str, action: str) -> None:
    """Record a stream.state event for the session's committed state, in the caller's transaction."""
    session = public_session(_load(connection, session_id))
    record_event(connection, "stream.state", {"type": "stream.state", "action": action, "session": session,
                 "demo_only": True}, session_id=session_id, aggregate_id=session_id)


def _stop(connection: Connection, session_id: str, reason: str) -> bool:
    now = _now()
    stopped = connection.execute(update(stream_sessions).where(stream_sessions.c.id == session_id,
        stream_sessions.c.status.in_(ACTIVE_STATUSES)).values(status="stopped", active_slot=None,
        stopped_at=now, updated_at=now, stop_reason=reason)).rowcount == 1
    if stopped:
        _state_event(connection, session_id, "stopped")
    return stopped


def current_session() -> dict[str, Any] | None:
    with get_engine().connect() as connection:
        row = _active(connection)
    return public_session(row) if row else None


def get_session(session_id: str) -> dict[str, Any]:
    with get_engine().connect() as connection:
        return public_session(_load(connection, session_id))


def start_session(*, scenario: str, patient_id: str | None, interval_ms: int, takeover: bool,
                  producer_key: str | None) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
    """Create the single active session; returns (session, producer_token, replaced_session)."""
    _check_producer_key(producer_key)
    session_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    replaced = None
    now = _now()
    try:
        with get_engine().begin() as connection:
            active = _active(connection)
            if active:
                idle = _is_idle(active)
                if not takeover and not idle:
                    raise StreamError(409, "producer_active",
                        "Another producer is already streaming. Stop it first or explicitly take over.",
                        active_session=public_session(active))
                _stop(connection, active["id"], "idle_timeout" if idle and not takeover else "takeover")
                replaced = public_session(_load(connection, active["id"]))
            connection.execute(insert(stream_sessions).values(
                id=session_id, patient_id=patient_id or f"DEMO-STREAM-{session_id[:6].upper()}",
                scenario=scenario, status="running", interval_ms=interval_ms, next_sequence=0,
                token_hash=_hash(token), active_slot=1, created_at=now, updated_at=now))
            _state_event(connection, session_id, "started")
            session = public_session(_load(connection, session_id))
    except IntegrityError:
        # Lost a race with a concurrent start for the single active slot.
        raise StreamError(409, "producer_active", "Another producer started a stream at the same time.",
                          active_session=current_session())
    return session, token, replaced


def control_session(session_id: str, token: str | None, action: str) -> tuple[dict[str, Any], bool]:
    """Pause, resume or stop a session. Returns (session, changed); repeated calls are no-ops."""
    transitions = {"pause": ("running", "paused"), "resume": ("paused", "running")}
    with get_engine().begin() as connection:
        row = _load(connection, session_id)
        _authorize(row, token)
        if action == "stop":
            changed = _stop(connection, session_id, "producer_stopped")
        else:
            source, target = transitions[action]
            if row["status"] == "stopped":
                raise StreamError(409, "session_stopped", "The stream session has been stopped.",
                                  session=public_session(row))
            changed = connection.execute(update(stream_sessions).where(stream_sessions.c.id == session_id,
                stream_sessions.c.status == source).values(status=target, updated_at=_now())).rowcount == 1
            if changed:
                _state_event(connection, session_id, {"pause": "paused", "resume": "resumed"}[action])
        return public_session(_load(connection, session_id)), changed


def _existing_event(session_id: str, sequence: int) -> dict[str, Any] | None:
    """The original committed event for a sequence (same event_seq/event_uuid the receivers got)."""
    record = get_stream_observation(session_id, sequence)
    if not record:
        return None
    return event_for("observation.created", record["id"]) or events_for_records([record])[0]


class _SequenceConflict(Exception):
    pass


_last_emit: dict[str, float] = {}
_last_emit_lock = threading.Lock()


def emit_observation(session_id: str, token: str | None, sequence: int,
                     server_received_at: str) -> tuple[dict[str, Any], bool]:
    """Persist the observation for `sequence` with its outbox events. Returns (event, duplicate)."""
    with get_engine().connect() as connection:
        row = _load(connection, session_id)
    _authorize(row, token)
    if sequence < row["next_sequence"]:
        existing = _existing_event(session_id, sequence)
        if existing:
            return existing, True
    if row["status"] != "running":
        raise StreamError(409, f"session_{row['status']}", f"The stream session is {row['status']}.",
                          session=public_session(row))
    if sequence != row["next_sequence"]:
        raise StreamError(409, "sequence_out_of_order", "Sequence must be the session's next sequence.",
                          expected_sequence=row["next_sequence"])
    if sequence >= MAX_SEQUENCE:
        with get_engine().begin() as connection:
            _stop(connection, session_id, "max_sequence_reached")
        raise StreamError(409, "session_complete", "The stream reached its maximum length and was stopped.")
    with _last_emit_lock:
        last = _last_emit.get(session_id)
        # A session has no previous emission until its first observation. Do not
        # compare against 0.0: monotonic time can be less than the configured gap
        # on a fresh process, which incorrectly rejects the first sequence.
        now = time.monotonic()
        if last is not None and now - last < MIN_EMIT_GAP_SECONDS:
            raise StreamError(429, "emitting_too_fast", "Observations are being submitted too quickly.")
        _last_emit[session_id] = now

    values = observation_for_step(row["scenario"], sequence)
    result = score_observation(row["patient_id"], values)

    def advance(connection: Connection, saved: dict[str, Any]) -> None:
        moved = connection.execute(update(stream_sessions).where(stream_sessions.c.id == session_id,
            stream_sessions.c.status == "running", stream_sessions.c.next_sequence == sequence).values(
            next_sequence=sequence + 1, last_observation_id=saved["id"], last_emit_at=_now(),
            updated_at=_now())).rowcount
        if moved != 1:
            raise _SequenceConflict()

    try:
        _saved, _alert, event = persist_observation(row["patient_id"], values, result, True, session_id=session_id,
                                                    sequence=sequence, within=advance, server_received_at=server_received_at)
    except (IntegrityError, _SequenceConflict):
        # A concurrent duplicate committed first, or the session was paused/stopped meanwhile.
        existing = _existing_event(session_id, sequence)
        if existing:
            return existing, True
        raise StreamError(409, "session_changed", "The stream session changed state; nothing was saved.",
                          session=get_session(session_id))
    return event, False


def events_for_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rebuild the broadcast contract for stored observations, including any alert they raised."""
    keys = [f"observation:{record['id']}:elevated-risk" for record in records]
    alerts_by_key = {alert["event_key"]: alert for alert in list_alerts_by_event_keys(keys)}
    return [observation_event(record, alerts_by_key.get(key)) for record, key in zip(records, keys)]


def missed_events(after_id: int, session_id: str | None, limit: int) -> list[dict[str, Any]]:
    return events_for_records(list_observations(after_id=after_id, session_id=session_id, limit=limit))

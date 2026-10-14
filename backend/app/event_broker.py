"""Cross-instance live events: transactional outbox + PostgreSQL LISTEN/NOTIFY.

Lifecycle of every live event
1. The producing request writes its data (observation, alert, stream session...)
   and calls record_event() in the SAME database transaction. The event row in
   `event_outbox` gets a global sequence id (event_seq).
2. On PostgreSQL, record_event() also issues pg_notify() in that transaction.
   PostgreSQL delivers notifications only when the transaction commits, so no
   instance is ever told about an event that rolled back.
3. Each backend instance runs a Dispatcher that reads committed outbox rows in
   id order and pushes them to its own WebSocket clients. NOTIFY only wakes the
   dispatcher; the outbox is the source of truth, so a missed notification
   (listener reconnecting) is recovered by the next poll.
4. Clients that were disconnected recover from GET /api/v1/events?after_seq=…,
   which reads the same outbox rows.

Brokers
- postgres: cross-instance delivery through the existing PostgreSQL database.
  No extra service or secret is needed. Requires session-level connections
  (direct or session-pooled); transaction-pooling proxies drop LISTEN.
- memory: single-instance only (SQLite/local development). Events reach only
  the clients of the instance that committed them, and health reports
  cross_instance_delivery=false.

Redis Pub/Sub is not used: the deployment has no Redis, and Pub/Sub does not
retain messages, so it would still need this outbox for recovery.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.engine import Connection
from starlette.concurrency import run_in_threadpool

from .live_events import hub
from .storage import get_engine
from .storage_schema import event_outbox

SCHEMA_VERSION = 1
CHANNEL = "vitalguard_events"
BATCH_LIMIT = 500
MAX_TRACKED_GAPS = 10_000

logger = logging.getLogger("vitalguard.events")


def instance_id() -> str:
    return os.getenv("VITALGUARD_INSTANCE_ID") or f"{socket.gethostname()}-{os.getpid()}"


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# --- Producing events (inside the caller's transaction) -----------------------------------

def record_event(connection: Connection, event_type: str, payload: dict[str, Any], *,
                 session_id: str | None = None, aggregate_id: str | int | None = None) -> dict[str, Any]:
    """Append an event to the outbox in the caller's transaction; returns its envelope (without published_at)."""
    event_uuid = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    origin = instance_id()
    result = connection.execute(insert(event_outbox).values(
        event_uuid=event_uuid, event_type=event_type, schema_version=SCHEMA_VERSION, session_id=session_id,
        aggregate_id=str(aggregate_id) if aggregate_id is not None else None, origin_instance=origin,
        payload_json=json.dumps(payload, separators=(",", ":"), default=str), created_at=created_at))
    sequence = int(result.inserted_primary_key[0])
    if connection.dialect.name == "postgresql":
        # Delivered by PostgreSQL only if and when this transaction commits.
        connection.execute(text("SELECT pg_notify(:channel, :payload)"), {"channel": CHANNEL, "payload": str(sequence)})
    return _envelope(payload, sequence, event_uuid, created_at, origin)


def _envelope(payload: dict[str, Any], sequence: int, event_uuid: str, created_at: Any, origin: str) -> dict[str, Any]:
    if hasattr(created_at, "isoformat"):
        # Always UTC, whatever the database session time zone, so every instance emits identical text.
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_at = created_at.astimezone(timezone.utc).isoformat()
    return {**payload, "event_seq": sequence, "event_uuid": event_uuid, "schema_version": SCHEMA_VERSION,
            "emitted_at": created_at, "origin_instance": origin}


def _row_envelope(row: Any) -> dict[str, Any]:
    return _envelope(json.loads(row["payload_json"]), int(row["id"]), row["event_uuid"], row["created_at"], row["origin_instance"])


# --- Reading committed events ---------------------------------------------------------------

def events_after(after_seq: int, limit: int = 100, session_id: str | None = None) -> list[dict[str, Any]]:
    query = select(event_outbox).where(event_outbox.c.id > after_seq)
    if session_id:
        query = query.where(event_outbox.c.session_id == session_id)
    with get_engine().connect() as connection:
        rows = connection.execute(query.order_by(event_outbox.c.id).limit(limit)).mappings().all()
    return [_row_envelope(row) for row in rows]


def events_by_ids(ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    with get_engine().connect() as connection:
        rows = connection.execute(select(event_outbox).where(event_outbox.c.id.in_(ids)).order_by(event_outbox.c.id)).mappings().all()
    return [_row_envelope(row) for row in rows]


def event_for(event_type: str, aggregate_id: str | int) -> dict[str, Any] | None:
    with get_engine().connect() as connection:
        row = connection.execute(select(event_outbox).where(event_outbox.c.event_type == event_type,
            event_outbox.c.aggregate_id == str(aggregate_id)).order_by(event_outbox.c.id).limit(1)).mappings().first()
    return _row_envelope(row) if row else None


def sequence_bounds() -> tuple[int | None, int | None]:
    with get_engine().connect() as connection:
        low, high = connection.execute(select(func.min(event_outbox.c.id), func.max(event_outbox.c.id))).one()
    return (int(low) if low is not None else None, int(high) if high is not None else None)


def prune_outbox(retention_hours: float) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    with get_engine().begin() as connection:
        return connection.execute(delete(event_outbox).where(event_outbox.c.created_at < cutoff)).rowcount or 0


# --- Per-instance dispatch ------------------------------------------------------------------

class Dispatcher:
    """Pushes committed outbox events to this instance's WebSocket clients, once each.

    Sequence ids are allocated at insert time but transactions can commit out of
    order, and rolled-back inserts leave permanent holes. When a scan skips ids,
    they are tracked as gaps and re-checked; a late commit is delivered when it
    appears, and a gap older than the gap timeout is treated as a rollback.
    """

    def __init__(self) -> None:
        self.high_water: int = 0
        self.gaps: dict[int, float] = {}
        self.delivered = 0
        self.duplicate_wakeups = 0
        self.late_deliveries = 0
        self.last_dispatch_at: str | None = None
        self._lock: asyncio.Lock | None = None
        self._condition: asyncio.Condition | None = None
        self._requested = 0
        self._completed = 0
        self._running = False
        self.coalesced = 0
        self.gap_timeout = 60.0

    async def start(self) -> None:
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition()
        self._requested = self._completed = 0
        self._running = False
        self.gap_timeout = _float_env("VITALGUARD_EVENT_GAP_TIMEOUT_SECONDS", 60)
        _, high = await run_in_threadpool(sequence_bounds)
        # New connections start live; anything earlier is recovered through REST.
        self.high_water = high or 0
        self.gaps.clear()

    async def dispatch(self) -> list[dict[str, Any]]:
        """Return once a dispatch that started after this call has completed.

        Concurrent callers are coalesced: a single scan covers every commit made
        before it began, so N simultaneous requests cost one outbox query instead
        of N serialized ones, while each caller still knows its own committed
        events were pushed to this instance's clients before it returns.
        """
        if self._condition is None:
            return []
        self._requested += 1
        ticket = self._requested
        sent: list[dict[str, Any]] = []
        while True:
            async with self._condition:
                while self._running and self._completed < ticket:
                    await self._condition.wait()
                if self._completed >= ticket:
                    self.coalesced += 1
                    return sent
                self._running = True
                covered = self._requested
            try:
                sent = await self._dispatch_once()
            finally:
                async with self._condition:
                    self._completed = max(self._completed, covered)
                    self._running = False
                    self._condition.notify_all()

    async def _dispatch_once(self) -> list[dict[str, Any]]:
        async with self._lock:
            sent: list[dict[str, Any]] = []
            if self.gaps:
                late = await run_in_threadpool(events_by_ids, sorted(self.gaps))
                for event in late:
                    self.gaps.pop(event["event_seq"], None)
                    self.late_deliveries += 1
                    sent.append(await self._send(event))
                now = time.monotonic()
                for sequence, first_seen in list(self.gaps.items()):
                    if now - first_seen > self.gap_timeout:
                        del self.gaps[sequence]
            while True:
                batch = await run_in_threadpool(events_after, self.high_water, BATCH_LIMIT)
                for event in batch:
                    sequence = event["event_seq"]
                    for missing in range(self.high_water + 1, sequence):
                        if len(self.gaps) < MAX_TRACKED_GAPS:
                            self.gaps.setdefault(missing, time.monotonic())
                    self.high_water = sequence
                    sent.append(await self._send(event))
                if len(batch) < BATCH_LIMIT:
                    break
            if not sent:
                self.duplicate_wakeups += 1
            return sent

    async def _send(self, event: dict[str, Any]) -> dict[str, Any]:
        event = {**event, "published_at": datetime.now(timezone.utc).isoformat()}
        await hub.broadcast(event)
        self.delivered += 1
        self.last_dispatch_at = event["published_at"]
        return event

    def stats(self) -> dict[str, Any]:
        return {"high_water_seq": self.high_water, "pending_gaps": len(self.gaps), "delivered": self.delivered,
                "late_deliveries": self.late_deliveries, "empty_dispatches": self.duplicate_wakeups,
                "coalesced_dispatch_requests": self.coalesced,
                "last_dispatch_at": self.last_dispatch_at}


class EventSystem:
    """Chooses the broker, runs the dispatcher and background loops for this instance."""

    def __init__(self) -> None:
        self.dispatcher = Dispatcher()
        self.mode = "memory"
        self.listener_connected = False
        self.listener_reconnects = 0
        self.last_notification_at: str | None = None
        self.last_error: str | None = None
        self._tasks: list[asyncio.Task] = []
        self._wake: asyncio.Event | None = None
        self._listener_ready: asyncio.Event | None = None
        self._stopping = False

    def _resolve_mode(self) -> str:
        requested = os.getenv("VITALGUARD_EVENT_BROKER", "auto").strip().lower()
        dialect = get_engine().dialect.name
        if requested == "auto":
            return "postgres" if dialect == "postgresql" else "memory"
        if requested == "postgres" and dialect != "postgresql":
            raise RuntimeError("VITALGUARD_EVENT_BROKER=postgres requires DATABASE_URL to point to PostgreSQL")
        if requested not in {"postgres", "memory"}:
            raise RuntimeError(f"Unsupported VITALGUARD_EVENT_BROKER '{requested}'")
        return requested

    async def start(self) -> None:
        self._stopping = False
        self.mode = self._resolve_mode()
        self.listener_connected = False
        self._wake = asyncio.Event()
        self._listener_ready = asyncio.Event()
        await self.dispatcher.start()
        self._tasks = [asyncio.create_task(self._worker(), name="vitalguard-event-worker")]
        if self.mode == "postgres":
            self._tasks.append(asyncio.create_task(self._listen(), name="vitalguard-event-listener"))
            # Avoid reporting "degraded" for the first moments of a healthy instance.
            try:
                await asyncio.wait_for(self._listener_ready.wait(),
                                       timeout=_float_env("VITALGUARD_EVENT_LISTENER_STARTUP_TIMEOUT_SECONDS", 5))
            except asyncio.TimeoutError:
                logger.error("Event listener did not connect at startup; serving with degraded cross-instance delivery")
        else:
            logger.warning("Event broker 'memory': live events reach only this instance's clients (no cross-instance delivery)")

    async def stop(self) -> None:
        self._stopping = True
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks = []

    async def after_commit(self) -> list[dict[str, Any]]:
        """Fast path: deliver this instance's just-committed events before the HTTP response returns."""
        return await self.dispatcher.dispatch()

    async def _worker(self) -> None:
        poll = _float_env("VITALGUARD_EVENT_POLL_SECONDS", 2.0)
        retention = _float_env("VITALGUARD_EVENT_RETENTION_HOURS", 168)
        last_prune = 0.0
        while not self._stopping:
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=poll)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
            try:
                await self.dispatcher.dispatch()
                if time.monotonic() - last_prune > 3600:
                    await run_in_threadpool(prune_outbox, retention)
                    last_prune = time.monotonic()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # database briefly unavailable: keep the loop alive and retry
                self.last_error = f"dispatch: {type(exc).__name__}"
                logger.warning("Event dispatch failed (%s); will retry", type(exc).__name__)

    async def _listen(self) -> None:
        import psycopg
        url = get_engine().url.set(drivername="postgresql")
        conninfo = url.render_as_string(hide_password=False)
        delay = 1.0
        while not self._stopping:
            try:
                async with await psycopg.AsyncConnection.connect(
                        conninfo, autocommit=True, connect_timeout=10,
                        application_name=f"vitalguard-listener-{instance_id()}"[:63]) as connection:
                    await connection.execute(f"LISTEN {CHANNEL}")
                    self.listener_connected, delay = True, 1.0
                    self._listener_ready.set()
                    self._wake.set()  # catch up on anything committed while disconnected
                    async for _notification in connection.notifies():
                        self.last_notification_at = datetime.now(timezone.utc).isoformat()
                        self._wake.set()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"listener: {type(exc).__name__}"
                logger.warning("Event listener disconnected (%s); reconnecting in %.0fs", type(exc).__name__, delay)
            self.listener_connected = False
            if self._stopping:
                break
            self.listener_reconnects += 1
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)

    def health(self) -> dict[str, Any]:
        cross = self.mode == "postgres"
        status = "ok" if not cross or self.listener_connected else "degraded"
        return {"status": status, "mode": self.mode, "cross_instance_delivery": cross and self.listener_connected,
                "instance_id": instance_id(), "listener_connected": self.listener_connected if cross else None,
                "listener_reconnects": self.listener_reconnects, "last_notification_at": self.last_notification_at,
                "last_error": self.last_error, "websocket_clients": hub.client_count(), **self.dispatcher.stats(),
                "note": None if cross else "single-instance mode: events reach only clients of the instance that committed them"}


events = EventSystem()

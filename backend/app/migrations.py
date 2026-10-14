"""Versioned, repeatable schema migrations for the VitalGuard demo database.

Each migration runs in its own transaction together with its ledger row, so a
failed step leaves the previous version intact and is retried on next start.
Every step is idempotent, which also makes it safe on databases created before
the ledger existed. On PostgreSQL an advisory lock serializes concurrent
startups (for example two instances during a deploy).
"""
from __future__ import annotations
from typing import Callable
from contextlib import contextmanager
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, cast, func, insert, inspect, select, text, update
from sqlalchemy.engine import Connection, Engine

from .storage_schema import alerts, audit_events, event_outbox, metadata as _APP_METADATA, stream_sessions

_MIGRATION_METADATA = MetaData()
MIGRATIONS = Table(
    "schema_migrations", _MIGRATION_METADATA,
    Column("version", Integer, primary_key=True),
    Column("name", String(120)),
    Column("applied_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
_ADVISORY_LOCK_ID = 74_212_001


def _baseline_tables(connection: Connection) -> None:
    """v1: observations, patients, alerts and audit_events (checkfirst, so legacy tables are kept)."""
    _APP_METADATA.create_all(connection, checkfirst=True)


def _create_indexes(connection: Connection, names: set[str] | None = None) -> None:
    for table in _APP_METADATA.sorted_tables:
        for index in table.indexes:
            if names is None or index.name in names:
                index.create(connection, checkfirst=True)


def _history_indexes(connection: Connection) -> None:
    """v2: id-ordered indexes for bounded, cursor-paginated history queries."""
    _create_indexes(connection, {"idx_observations_patient_id_desc", "idx_alerts_status_id_desc",
                                 "idx_alerts_patient_id_desc", "idx_audit_entity_id"})


def _backfill_alert_timestamps(connection: Connection) -> None:
    """v3: populate acknowledged_at/resolved_at for existing alerts from their audit trail.

    Earlier versions recorded transitions only as audit events; the alert row's
    timestamp columns stayed NULL.
    """
    for action, column in (("acknowledged", alerts.c.acknowledged_at), ("resolved", alerts.c.resolved_at)):
        first_event = (select(func.min(audit_events.c.created_at))
                       .where(audit_events.c.entity_type == "alert",
                              audit_events.c.entity_id == cast(alerts.c.id, String),
                              audit_events.c.action == action)
                       .scalar_subquery())
        connection.execute(update(alerts).where(column.is_(None)).values({column.key: first_event}))


def _live_stream_sessions(connection: Connection) -> None:
    """v4: stream session table and per-session sequence columns on observations."""
    columns = {column["name"] for column in inspect(connection).get_columns("observations")}
    if "session_id" not in columns:
        connection.execute(text("ALTER TABLE observations ADD COLUMN session_id VARCHAR(36)"))
    if "sequence" not in columns:
        connection.execute(text("ALTER TABLE observations ADD COLUMN sequence INTEGER"))
    stream_sessions.create(connection, checkfirst=True)
    _create_indexes(connection, {"uq_observations_session_sequence", "idx_stream_sessions_status"})


def _event_outbox(connection: Connection) -> None:
    """v5: transactional outbox for cross-instance live events and missed-event recovery."""
    event_outbox.create(connection, checkfirst=True)
    _create_indexes(connection, {"idx_event_outbox_created", "idx_event_outbox_session_id"})


STEPS: tuple[tuple[int, str, Callable[[Connection], None]], ...] = (
    (1, "baseline_tables", _baseline_tables),
    (2, "history_indexes", _history_indexes),
    (3, "backfill_alert_timestamps", _backfill_alert_timestamps),
    (4, "live_stream_sessions", _live_stream_sessions),
    (5, "event_outbox", _event_outbox),
)
LATEST_VERSION = STEPS[-1][0]


def _ensure_ledger(connection: Connection) -> None:
    _MIGRATION_METADATA.create_all(connection, checkfirst=True)
    # Ledgers created before migration names were recorded lack the column.
    columns = {column["name"] for column in inspect(connection).get_columns("schema_migrations")}
    if "name" not in columns:
        connection.execute(text("ALTER TABLE schema_migrations ADD COLUMN name VARCHAR(120)"))


def current_version(connection: Connection) -> int:
    if not inspect(connection).has_table("schema_migrations"):
        return 0
    return connection.execute(select(func.max(MIGRATIONS.c.version))).scalar() or 0


@contextmanager
def _migration_lock(engine: Engine):
    if engine.dialect.name != "postgresql":
        yield
        return
    with engine.connect() as lock_connection:
        lock_connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _ADVISORY_LOCK_ID})
        lock_connection.commit()
        try:
            yield
        finally:
            lock_connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _ADVISORY_LOCK_ID})
            lock_connection.commit()


def migrate(engine: Engine) -> list[int]:
    """Apply pending migrations in order and return the versions applied by this call."""
    applied_now: list[int] = []
    with _migration_lock(engine):
        with engine.begin() as connection:
            _ensure_ledger(connection)
        for version, name, step in STEPS:
            with engine.begin() as connection:
                already = connection.execute(
                    select(MIGRATIONS.c.version).where(MIGRATIONS.c.version == version)).first()
                if already:
                    continue
                step(connection)
                connection.execute(insert(MIGRATIONS).values(version=version, name=name))
                applied_now.append(version)
        # Idempotent repair: recreate any table or index dropped after its migration ran.
        with engine.begin() as connection:
            _baseline_tables(connection)
            _create_indexes(connection)
    return applied_now

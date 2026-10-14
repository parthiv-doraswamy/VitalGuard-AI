"""Durable tables for the synthetic VitalGuard demo.

Every row in these tables is synthetic demonstration data. None of them is a
medical record, and real patient data must never be written to them.
"""
from sqlalchemy import (
    Column, DateTime, Index, Integer, MetaData, String, Table, Text, func,
)

metadata = MetaData()

observations = Table(
    "observations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("patient_id", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("input_json", Text, nullable=False),
    Column("prediction_json", Text, nullable=False),
    Column("model_version", String(128), nullable=False),
    # Set only for observations produced by a live-demo stream session.
    Column("session_id", String(36)),
    Column("sequence", Integer),
)
Index("idx_observations_patient_created", observations.c.patient_id,
      observations.c.created_at.desc(), observations.c.id.desc())
# History pages are keyed by id (before_id cursor), so filter + order by id.
Index("idx_observations_patient_id_desc", observations.c.patient_id, observations.c.id.desc())
# One persisted observation per stream sequence number: retries cannot duplicate records.
Index("uq_observations_session_sequence", observations.c.session_id, observations.c.sequence, unique=True)

stream_sessions = Table(
    "stream_sessions", metadata,
    Column("id", String(36), primary_key=True),
    Column("patient_id", String(64), nullable=False),
    Column("scenario", String(16), nullable=False),
    Column("status", String(16), nullable=False),
    Column("interval_ms", Integer, nullable=False),
    Column("next_sequence", Integer, nullable=False, server_default="0"),
    Column("token_hash", String(64), nullable=False),
    # 1 while running/paused, NULL once stopped. The unique constraint means at most
    # one active session can exist, even when two producers start at the same instant.
    Column("active_slot", Integer, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_emit_at", DateTime(timezone=True)),
    Column("stopped_at", DateTime(timezone=True)),
    Column("stop_reason", String(40)),
    Column("last_observation_id", Integer),
)
Index("idx_stream_sessions_status", stream_sessions.c.status, stream_sessions.c.created_at.desc())

patients = Table(
    "patients", metadata,
    Column("patient_id", String(64), primary_key=True),
    Column("display_name", String(120), nullable=False),
    Column("unit", String(80), nullable=False, server_default="Demo Ward"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)

alerts = Table(
    "alerts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("patient_id", String(64), nullable=False, index=True),
    Column("event_key", String(160), nullable=False, unique=True),
    Column("severity", String(16), nullable=False),
    Column("status", String(24), nullable=False, server_default="open"),
    Column("title", String(180), nullable=False),
    Column("details_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("acknowledged_by", String(120)),
    Column("acknowledged_at", DateTime(timezone=True)),
    Column("resolved_at", DateTime(timezone=True)),
)
Index("idx_alerts_status_created", alerts.c.status, alerts.c.created_at.desc())
Index("idx_alerts_status_id_desc", alerts.c.status, alerts.c.id.desc())
Index("idx_alerts_patient_id_desc", alerts.c.patient_id, alerts.c.id.desc())

audit_events = Table(
    "audit_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("entity_type", String(32), nullable=False),
    Column("entity_id", String(160), nullable=False),
    Column("action", String(80), nullable=False),
    Column("actor", String(120), nullable=False, server_default="demo-system"),
    Column("details_json", Text, nullable=False, server_default="{}"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
Index("idx_audit_entity_created", audit_events.c.entity_type, audit_events.c.entity_id, audit_events.c.created_at.desc())
Index("idx_audit_entity_id", audit_events.c.entity_type, audit_events.c.entity_id, audit_events.c.id)

# Tables in foreign-key-safe order, used by migrations and backup/restore.
APPLICATION_TABLES = (observations, patients, alerts, audit_events, stream_sessions)

"""Durable tables for the synthetic VitalGuard demo.

Every row in these tables is synthetic demonstration data. None of them is a
medical record, and real patient data must never be written to them.
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Index, Integer, MetaData, String, Table, Text, UniqueConstraint, func,
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

# Transactional outbox: every live event is written in the same transaction as the
# data change it describes. `id` is the global event sequence used for ordering and
# for missed-event recovery; the broker only signals that new rows exist.
event_outbox = Table(
    "event_outbox", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("event_uuid", String(36), nullable=False, unique=True),
    Column("event_type", String(40), nullable=False),
    Column("schema_version", Integer, nullable=False),
    Column("session_id", String(36)),
    Column("aggregate_id", String(64)),
    Column("origin_instance", String(120), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    # SQLite would otherwise reuse ids after pruning, breaking "after_seq" recovery.
    sqlite_autoincrement=True,
)
Index("idx_event_outbox_created", event_outbox.c.created_at)
Index("idx_event_outbox_session_id", event_outbox.c.session_id, event_outbox.c.id)

# Web Push: one row per browser subscription (device-scoped; there is no user identity yet).
# The endpoint is a capability URL, so it is only ever logged by its hash; the management
# token that proves ownership is stored only as a SHA-256 hash.
push_subscriptions = Table(
    "push_subscriptions", metadata,
    Column("id", String(36), primary_key=True),
    Column("endpoint_hash", String(64), nullable=False, unique=True),
    Column("endpoint", Text, nullable=False),
    Column("p256dh", String(200), nullable=False),
    Column("auth", String(100), nullable=False),
    Column("token_hash", String(64), nullable=False),
    Column("min_severity", String(16), nullable=False, server_default="high"),
    Column("enabled", Boolean, nullable=False, server_default="1"),
    Column("status", String(16), nullable=False, server_default="active"),
    Column("receipt_base", String(300)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_success_at", DateTime(timezone=True)),
    Column("last_failure_at", DateTime(timezone=True)),
    Column("consecutive_failures", Integer, nullable=False, server_default="0"),
    Column("expired_reason", String(80)),
)
Index("idx_push_subscriptions_status", push_subscriptions.c.status, push_subscriptions.c.enabled)

# Durable delivery queue. Rows are created in the same transaction as the alert, so a
# notification can only exist for a committed alert; (subscription_id, event_key) is
# unique, so retries, duplicate alerts and multiple instances never send twice.
push_deliveries = Table(
    "push_deliveries", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("subscription_id", String(36), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("event_key", String(160), nullable=False),
    Column("alert_id", Integer),
    Column("payload_json", Text, nullable=False),
    Column("status", String(16), nullable=False, server_default="pending"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("next_attempt_at", DateTime(timezone=True), nullable=False),
    Column("locked_until", DateTime(timezone=True)),
    Column("last_status_code", Integer),
    Column("last_error", String(200)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("accepted_at", DateTime(timezone=True)),
    Column("displayed_at", DateTime(timezone=True)),
    Column("clicked_at", DateTime(timezone=True)),
    UniqueConstraint("subscription_id", "event_key", name="uq_push_delivery_subscription_event"),
    sqlite_autoincrement=True,
)
Index("idx_push_deliveries_due", push_deliveries.c.status, push_deliveries.c.next_attempt_at)
Index("idx_push_deliveries_subscription", push_deliveries.c.subscription_id, push_deliveries.c.id)

# Tables in foreign-key-safe order, used by migrations and backup/restore.
APPLICATION_TABLES = (observations, patients, alerts, audit_events, stream_sessions, event_outbox,
                      push_subscriptions, push_deliveries)

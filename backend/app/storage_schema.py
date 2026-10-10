"""Additional durable tables for the synthetic VitalGuard demo."""
from sqlalchemy import (
    Column, DateTime, Index, Integer, MetaData, String, Table, Text, func,
)

metadata = MetaData()

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

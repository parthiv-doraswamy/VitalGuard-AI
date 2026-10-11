"""Schema for source provenance and idempotent synthetic ingestion."""
from sqlalchemy import Column, DateTime, Index, Integer, MetaData, String, Table, Text, UniqueConstraint, func

metadata = MetaData()

ingestion_records = Table(
    "ingestion_records", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("source_system", String(80), nullable=False),
    Column("source_event_id", String(128), nullable=False),
    Column("patient_id", String(64), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("observation_id", Integer, nullable=False),
    Column("units_json", Text, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    UniqueConstraint("source_system", "source_event_id", name="uq_ingestion_source_event"),
)
Index("idx_ingestion_patient_observed", ingestion_records.c.patient_id, ingestion_records.c.observed_at.desc())

"""Small explicit schema migration runner for the VitalGuard demo.

For a production clinical system, use a reviewed Alembic migration workflow.
This lightweight runner keeps this prototype's schema evolution explicit.
"""
from sqlalchemy import (
    Column, DateTime, Integer, MetaData, String, Table, func, insert, select,
    text,
)
from sqlalchemy.engine import Engine

from .storage_schema import metadata


MIGRATIONS = Table(
    "schema_migrations",
    MetaData(),
    Column("version", Integer, primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
LATEST_VERSION = 1


def migrate(engine: Engine) -> None:
    """Apply additive, idempotent schema changes in version order."""
    MIGRATIONS.metadata.create_all(engine)
    with engine.begin() as connection:
        applied = set(connection.execute(select(MIGRATIONS.c.version)).scalars())
        if 1 not in applied:
            metadata.create_all(connection)
            connection.execute(insert(MIGRATIONS).values(version=1))

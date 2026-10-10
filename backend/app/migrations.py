"""Versioned schema initialization for the VitalGuard demo database.

This is a minimal migration ledger for the current prototype schema. Use
Alembic before introducing non-additive production schema changes.
"""
from sqlalchemy import Column, DateTime, Integer, MetaData, Table, func, insert, select
from sqlalchemy.engine import Engine

from .storage import _METADATA

_MIGRATION_METADATA = MetaData()
MIGRATIONS = Table(
    "schema_migrations",
    _MIGRATION_METADATA,
    Column("version", Integer, primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
LATEST_VERSION = 1


def migrate(engine: Engine) -> None:
    """Create the current schema and record its migration version exactly once."""
    _MIGRATION_METADATA.create_all(engine)
    with engine.begin() as connection:
        applied = set(connection.execute(select(MIGRATIONS.c.version)).scalars())
        if 1 not in applied:
            _METADATA.create_all(connection)
            connection.execute(insert(MIGRATIONS).values(version=1))

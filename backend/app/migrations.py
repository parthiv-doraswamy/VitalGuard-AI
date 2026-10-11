"""Small, ordered, idempotent schema migrations for the demo database.

The migration ledger is applied sequentially. Schema changes must be added as a
new version rather than editing a previously released migration. This remains
a lightweight SQLAlchemy migration runner; a managed PostgreSQL service and
backup/restore drill are separate release requirements.
"""
from sqlalchemy import Column, DateTime, Integer, MetaData, Table, func, insert, select, text
from sqlalchemy.engine import Engine

from .storage import _METADATA
from .storage_schema import metadata as _EXTENDED_METADATA

_MIGRATION_METADATA = MetaData()
MIGRATIONS = Table(
    "schema_migrations", _MIGRATION_METADATA,
    Column("version", Integer, primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

# Keep migration definitions immutable after release. Each step should be
# safe to re-run after an interrupted startup.
LATEST_VERSION = 2



def _applied_versions(engine: Engine) -> set[int]:
    with engine.connect() as connection:
        return set(connection.execute(select(MIGRATIONS.c.version)).scalars())


def _record_version(engine: Engine, version: int) -> None:
    with engine.begin() as connection:
        connection.execute(insert(MIGRATIONS).values(version=version))


def migrate(engine: Engine) -> None:
    """Apply all known schema versions in order; safe to invoke repeatedly."""
    _MIGRATION_METADATA.create_all(engine)

    # Version 1: establish the original synthetic demo schema. Re-running
    # create_all is intentionally safe for a partially initialized database.
    applied = _applied_versions(engine)
    _METADATA.create_all(engine)
    _EXTENDED_METADATA.create_all(engine)
    if 1 not in applied:
        _record_version(engine, 1)

    # Version 2: index alert worklist queries by patient, status and creation.
    # checkfirst=True supports both fresh databases and interrupted upgrades.
    applied = _applied_versions(engine)
    if 2 not in applied:
        with engine.begin() as connection:
            connection.execute(text("CREATE INDEX IF NOT EXISTS idx_alerts_patient_status_created ON alerts (patient_id, status, created_at DESC)"))
        _record_version(engine, 2)
    else:
        # Ensure a partially restored schema is repaired without rewriting the
        # migration ledger.
        with engine.begin() as connection:
            connection.execute(text("CREATE INDEX IF NOT EXISTS idx_alerts_patient_status_created ON alerts (patient_id, status, created_at DESC)"))

    applied = _applied_versions(engine)
    expected = set(range(1, LATEST_VERSION + 1))
    if not expected.issubset(applied):
        raise RuntimeError(f"Database migrations incomplete: expected {sorted(expected)}, found {sorted(applied)}")

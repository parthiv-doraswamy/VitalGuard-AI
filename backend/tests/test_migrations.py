from sqlalchemy import create_engine, inspect, insert, select
from app.migrations import MIGRATIONS, migrate
from app.storage import _METADATA, database_health, initialize_storage
from app.storage_schema import metadata as EXTENDED_METADATA


def test_migrations_create_required_tables_and_indexes(tmp_path, monkeypatch):
    db_path = tmp_path / "migration.sqlite3"
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(db_path))
    initialize_storage()
    initialize_storage()
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        names = set(inspector.get_table_names())
        assert {"observations", "patients", "alerts", "audit_events", "schema_migrations", "ingestion_records"} <= names
        with engine.connect() as connection:
            versions = connection.execute(select(MIGRATIONS.c.version).order_by(MIGRATIONS.c.version)).scalars().all()
        assert versions == [1, 2, 3]
        index_names = {item["name"] for item in inspector.get_indexes("alerts")}
        assert "idx_alerts_patient_status_created" in index_names
    finally:
        engine.dispose()


def test_v1_database_upgrades_to_v2_idempotently(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    try:
        # Simulate a database produced by the previous release.
        MIGRATIONS.metadata.create_all(engine)
        _METADATA.create_all(engine)
        EXTENDED_METADATA.create_all(engine)
        with engine.begin() as connection:
            connection.execute(insert(MIGRATIONS).values(version=1))
        migrate(engine)
        migrate(engine)
        with engine.connect() as connection:
            versions = connection.execute(select(MIGRATIONS.c.version).order_by(MIGRATIONS.c.version)).scalars().all()
        assert versions == [1, 2, 3]
        index_names = {item["name"] for item in inspect(engine).get_indexes("alerts")}
        assert "idx_alerts_patient_status_created" in index_names
    finally:
        engine.dispose()


def test_database_health_reports_sqlite_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "health.sqlite3"))
    initialize_storage()
    result = database_health()
    assert result == {"status": "ok", "backend": "sqlite"}

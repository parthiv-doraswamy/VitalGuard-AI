from sqlalchemy import create_engine, inspect, select
from app.migrations import MIGRATIONS, migrate
from app.storage import database_health, initialize_storage


def test_migrations_create_required_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "migration.sqlite3"
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(db_path))
    initialize_storage()
    initialize_storage()
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    try:
        names = set(inspect(engine).get_table_names())
        assert {"observations", "patients", "alerts", "audit_events", "schema_migrations"} <= names
        with engine.connect() as connection:
            versions = connection.execute(select(MIGRATIONS.c.version)).scalars().all()
        assert versions == [1]
    finally:
        engine.dispose()


def test_database_health_reports_sqlite_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "health.sqlite3"))
    initialize_storage()
    result = database_health()
    assert result == {"status": "ok", "backend": "sqlite"}

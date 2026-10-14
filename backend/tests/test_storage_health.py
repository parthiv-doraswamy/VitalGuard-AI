"""Readiness checks for the synthetic demo database."""
import pytest
from sqlalchemy import create_engine, text

from app.storage import database_health, initialize_storage, _engine


def test_health_reports_backend_and_migration_version(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "health.sqlite3"))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    initialize_storage()
    result = database_health()

    assert result["status"] == "ok"
    assert result["backend"] == "sqlite"
    assert result["schema_version"] == result["latest_schema_version"] == 3


def test_health_fails_when_required_schema_table_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "incomplete.sqlite3"))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    initialize_storage()
    engine = _engine()
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE ingestion_records"))
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="schema is incomplete"):
        database_health()

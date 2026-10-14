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



def test_observation_survives_storage_reinitialization(tmp_path, monkeypatch):
    """A fresh engine after app-style initialization must see committed history."""
    from app.storage import list_observations, save_observation

    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "restart.sqlite3"))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    initialize_storage()
    saved = save_observation(
        "DEMO-RESTART-001",
        {"age": 58, "spo2": 98},
        {"model_version": "test-model", "risk_score": 24},
    )

    # Simulate a process restart: re-run startup migrations and query via a new engine.
    initialize_storage()
    rows = list_observations(patient_id="DEMO-RESTART-001", limit=10)

    assert len(rows) == 1
    assert rows[0]["id"] == saved["id"]
    assert rows[0]["inputs"] == {"age": 58, "spo2": 98}
    assert rows[0]["prediction"]["risk_score"] == 24

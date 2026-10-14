import json
from sqlalchemy import create_engine, inspect, select, text
from app.migrations import LATEST_VERSION, MIGRATIONS, migrate
from app.storage import database_health, get_engine, initialize_storage, list_observations
from app.alert_service import get_alert, list_alert_audit


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
            versions = connection.execute(select(MIGRATIONS.c.version).order_by(MIGRATIONS.c.version)).scalars().all()
        assert versions == list(range(1, LATEST_VERSION + 1))
    finally:
        engine.dispose()


def test_migrations_are_repeatable_and_create_history_indexes(database):
    engine = get_engine()
    assert migrate(engine) == []  # already applied when the engine was created
    assert migrate(engine) == []
    inspector = inspect(engine)
    observation_indexes = {index["name"] for index in inspector.get_indexes("observations")}
    alert_indexes = {index["name"] for index in inspector.get_indexes("alerts")}
    audit_indexes = {index["name"] for index in inspector.get_indexes("audit_events")}
    assert {"idx_observations_patient_created", "idx_observations_patient_id_desc"} <= observation_indexes
    assert {"idx_alerts_status_id_desc", "idx_alerts_patient_id_desc"} <= alert_indexes
    assert {"idx_audit_entity_created", "idx_audit_entity_id"} <= audit_indexes


def test_migration_repairs_a_dropped_index(database):
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX idx_alerts_patient_id_desc"))
    migrate(engine)
    assert "idx_alerts_patient_id_desc" in {index["name"] for index in inspect(engine).get_indexes("alerts")}


def _seed_legacy_v1_database(path) -> None:
    """Recreate the schema and data written by the previous release (ledger v1, no name column)."""
    engine = create_engine(f"sqlite+pysqlite:///{path}")
    statements = [
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)",
        "INSERT INTO schema_migrations (version) VALUES (1)",
        "CREATE TABLE observations (id INTEGER PRIMARY KEY, patient_id VARCHAR(64) NOT NULL, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, input_json TEXT NOT NULL, "
        "prediction_json TEXT NOT NULL, model_version VARCHAR(128) NOT NULL)",
        "CREATE INDEX idx_observations_patient_created ON observations (patient_id, created_at DESC, id DESC)",
        "CREATE TABLE patients (patient_id VARCHAR(64) PRIMARY KEY, display_name VARCHAR(120) NOT NULL, "
        "unit VARCHAR(80) DEFAULT 'Demo Ward' NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)",
        "CREATE TABLE alerts (id INTEGER PRIMARY KEY, patient_id VARCHAR(64) NOT NULL, event_key VARCHAR(160) NOT NULL UNIQUE, "
        "severity VARCHAR(16) NOT NULL, status VARCHAR(24) DEFAULT 'open' NOT NULL, title VARCHAR(180) NOT NULL, "
        "details_json TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, acknowledged_by VARCHAR(120), "
        "acknowledged_at DATETIME, resolved_at DATETIME)",
        "CREATE TABLE audit_events (id INTEGER PRIMARY KEY, entity_type VARCHAR(32) NOT NULL, entity_id VARCHAR(160) NOT NULL, "
        "action VARCHAR(80) NOT NULL, actor VARCHAR(120) DEFAULT 'demo-system' NOT NULL, details_json TEXT DEFAULT '{}' NOT NULL, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)",
        "INSERT INTO observations (patient_id, created_at, input_json, prediction_json, model_version) VALUES "
        "('DEMO-LEGACY-1', '2026-10-01 08:00:00', '{\"spo2\":97}', '{\"risk_score\":12,\"model_version\":\"legacy\"}', 'legacy')",
        "INSERT INTO alerts (patient_id, event_key, severity, status, title, details_json, created_at, acknowledged_by) VALUES "
        "('DEMO-LEGACY-1', 'legacy:1', 'high', 'resolved', 'Legacy demo alert', '{\"demo_only\":true}', '2026-10-01 08:00:01', 'demo-nurse')",
        "INSERT INTO audit_events (entity_type, entity_id, action, actor, created_at) VALUES "
        "('alert', '1', 'created', 'demo-system', '2026-10-01 08:00:01'), "
        "('alert', '1', 'acknowledged', 'demo-nurse', '2026-10-01 08:05:00'), "
        "('alert', '1', 'resolved', 'demo-nurse', '2026-10-01 08:10:00')",
    ]
    try:
        with engine.begin() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)
    finally:
        engine.dispose()


def test_migration_upgrades_existing_v1_database_without_losing_records(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.sqlite3"
    _seed_legacy_v1_database(db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(db_path))

    initialize_storage()

    with get_engine().connect() as connection:
        ledger = connection.execute(select(MIGRATIONS.c.version, MIGRATIONS.c.name).order_by(MIGRATIONS.c.version)).all()
    assert [row.version for row in ledger] == [1, 2, 3]
    assert ledger[0].name is None and ledger[2].name == "backfill_alert_timestamps"

    observations = list_observations(patient_id="DEMO-LEGACY-1")
    assert len(observations) == 1 and observations[0]["inputs"] == {"spo2": 97}
    alert = get_alert(1)
    assert alert["status"] == "resolved" and alert["details"] == {"demo_only": True}
    assert alert["acknowledged_at"].startswith("2026-10-01T08:05:00")
    assert alert["resolved_at"].startswith("2026-10-01T08:10:00")
    assert [item["action"] for item in list_alert_audit(1)] == ["created", "acknowledged", "resolved"]


def test_migration_adopts_database_created_before_the_ledger(tmp_path, monkeypatch):
    db_path = tmp_path / "preledger.sqlite3"
    _seed_legacy_v1_database(db_path)
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE schema_migrations"))
    engine.dispose()
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(db_path))

    initialize_storage()

    assert database_health()["schema_version"] == LATEST_VERSION
    assert len(list_observations(patient_id="DEMO-LEGACY-1")) == 1


def test_database_health_reports_sqlite_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "health.sqlite3"))
    initialize_storage()
    result = database_health()
    assert result["status"] == "ok"
    assert result["backend"] == "sqlite"
    assert result["durable_backend"] is False
    assert result["schema_version"] == result["latest_schema_version"] == LATEST_VERSION
    assert str(tmp_path) not in json.dumps(result)

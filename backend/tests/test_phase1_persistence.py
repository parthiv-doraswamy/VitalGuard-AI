"""Phase 1: database selection, migration safety, transactional writes and failure behaviour.

Tests taking the `database` fixture run on SQLite and, when VITALGUARD_TEST_POSTGRES_URL
points at a disposable database, on PostgreSQL too. All data is synthetic.
"""
import json
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, func, insert, inspect, select
from sqlalchemy.exc import OperationalError

from app import migrations, notification_service, observation_service, stream_service, storage
from app.main import app
from app.migrations import LATEST_VERSION, MIGRATIONS, STEPS, migrate
from app.storage import StorageConfigurationError, dispose_engines, initialize_storage
from app.storage_schema import alerts, audit_events, event_outbox, observations, stream_sessions

ELEVATED = {"patient_id": "DEMO-P1-ELEVATED", "age": 70, "heart_rate": 180, "spo2": 78, "systolic_bp": 80,
            "diastolic_bp": 50, "temperature": 39.5, "respiratory_rate": 34}
SECRET = "Sup3r-Secret-Pw"


# --- Historical schemas ----------------------------------------------------------------------

def _v1_metadata() -> MetaData:
    """The schema created by the release that ran in production before PR #94 (ledger without `name`)."""
    md = MetaData()
    Table("schema_migrations", md, Column("version", Integer, primary_key=True),
          Column("applied_at", DateTime(timezone=True), nullable=False, server_default=func.now()))
    Table("observations", md, Column("id", Integer, primary_key=True, autoincrement=True),
          Column("patient_id", String(64), nullable=False),
          Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
          Column("input_json", Text, nullable=False), Column("prediction_json", Text, nullable=False),
          Column("model_version", String(128), nullable=False))
    Table("patients", md, Column("patient_id", String(64), primary_key=True), Column("display_name", String(120), nullable=False),
          Column("unit", String(80), nullable=False, server_default="Demo Ward"),
          Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
          Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()))
    Table("alerts", md, Column("id", Integer, primary_key=True, autoincrement=True),
          Column("patient_id", String(64), nullable=False, index=True), Column("event_key", String(160), nullable=False, unique=True),
          Column("severity", String(16), nullable=False), Column("status", String(24), nullable=False, server_default="open"),
          Column("title", String(180), nullable=False), Column("details_json", Text, nullable=False),
          Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
          Column("acknowledged_by", String(120)), Column("acknowledged_at", DateTime(timezone=True)),
          Column("resolved_at", DateTime(timezone=True)))
    Table("audit_events", md, Column("id", Integer, primary_key=True, autoincrement=True),
          Column("entity_type", String(32), nullable=False), Column("entity_id", String(160), nullable=False),
          Column("action", String(80), nullable=False), Column("actor", String(120), nullable=False, server_default="demo-system"),
          Column("details_json", Text, nullable=False, server_default="{}"),
          Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()))
    return md


def _build_historical_database(version: int) -> None:
    """Create the schema exactly as a database at `version` has it: v1 DDL plus the real steps 2..version."""
    engine = create_engine(storage._database_url())
    try:
        md = _v1_metadata()
        md.create_all(engine)
        with engine.begin() as connection:
            connection.execute(insert(md.tables["schema_migrations"]).values(version=1))
            if version >= 2:
                migrations._ensure_ledger(connection)
            for step_version, name, step in STEPS[1:version]:
                step(connection)
                connection.execute(insert(MIGRATIONS).values(version=step_version, name=name))
            _seed(connection, md, version)
    finally:
        engine.dispose()


def _seed(connection, md, version: int) -> None:
    """Synthetic records valid for that schema version."""
    when = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
    obs = md.tables["observations"] if version < 4 else observations
    connection.execute(insert(obs).values(patient_id="DEMO-HIST-1", created_at=when, input_json='{"spo2":97}',
                                          prediction_json='{"risk_score":12,"model_version":"legacy"}', model_version="legacy"))
    # Releases before v3 left acknowledged_at/resolved_at empty (v3 backfills them); v3+ code writes them.
    timestamps = {} if version < 3 else {"acknowledged_at": when.replace(minute=5), "resolved_at": when.replace(minute=10)}
    connection.execute(insert(md.tables["alerts"]).values(patient_id="DEMO-HIST-1", event_key="hist:1", severity="high",
                       status="resolved", title="Historical demo alert", details_json='{"demo_only":true}',
                       created_at=when, acknowledged_by="demo-nurse", **timestamps))
    for action, minute in (("created", 0), ("acknowledged", 5), ("resolved", 10)):
        connection.execute(insert(md.tables["audit_events"]).values(entity_type="alert", entity_id="1", action=action,
                           actor="demo-nurse", details_json="{}", created_at=when.replace(minute=minute)))
    if version >= 4:
        connection.execute(insert(stream_sessions).values(id="00000000-0000-0000-0000-000000000001", patient_id="DEMO-HIST-S",
                           scenario="stable", status="stopped", interval_ms=2000, next_sequence=1, token_hash="0" * 64,
                           active_slot=None, created_at=when, updated_at=when))
    if version >= 5:
        connection.execute(insert(event_outbox).values(event_uuid="00000000-0000-0000-0000-0000000000aa",
                           event_type="observation.created", schema_version=1, origin_instance="historical",
                           payload_json='{"type":"observation.created"}', created_at=when))


def _counts(engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {table.name: connection.execute(select(func.count()).select_from(table)).scalar()
                for table in (observations, alerts, audit_events, stream_sessions, event_outbox)
                if inspect(connection).has_table(table.name)}


@pytest.mark.parametrize("version", range(1, LATEST_VERSION))
def test_upgrade_from_every_previous_schema_version_preserves_data(database, version):
    _build_historical_database(version)
    initialize_storage()  # startup path: migrates to the latest version
    engine = storage.get_engine()
    with engine.connect() as connection:
        ledger = connection.execute(select(MIGRATIONS.c.version).order_by(MIGRATIONS.c.version)).scalars().all()
        alert = connection.execute(select(alerts)).mappings().one()
        historical = connection.execute(select(observations).where(observations.c.patient_id == "DEMO-HIST-1")).mappings().one()
    assert ledger == list(range(1, LATEST_VERSION + 1))
    assert historical["input_json"] == '{"spo2":97}' and historical["session_id"] is None
    assert alert["status"] == "resolved" and alert["acknowledged_at"] is not None and alert["resolved_at"] is not None
    before = _counts(engine)
    assert before["observations"] == 1 and before["audit_events"] == 3
    assert migrate(engine) == []  # repeated startup is a no-op
    assert _counts(engine) == before
    # The upgraded database works for new writes (observation + alert + audit + outbox, one transaction).
    with TestClient(app) as client:
        assert client.post("/api/v1/risk/predict", json=ELEVATED).status_code == 200
        assert client.get("/health").json()["database"]["schema_version"] == LATEST_VERSION
    after = _counts(storage.get_engine())
    assert after["observations"] == before["observations"] + 1 and after["alerts"] == before["alerts"] + 1


def test_fresh_database_initialises_once_and_restarts_cleanly(database):
    initialize_storage()
    engine = storage.get_engine()
    with engine.connect() as connection:
        assert migrations.current_version(connection) == LATEST_VERSION
    for _ in range(3):  # repeated startups, each with a new engine
        dispose_engines()
        initialize_storage()
    with storage.get_engine().connect() as connection:
        versions = connection.execute(select(MIGRATIONS.c.version)).scalars().all()
    assert sorted(versions) == list(range(1, LATEST_VERSION + 1))


@pytest.mark.parametrize("database", ["postgresql"], indirect=True)
def test_concurrent_startup_migrations_apply_each_version_once(database):
    """Several instances starting together (deploy overlap): the advisory lock serialises them."""
    url = storage._database_url()
    engines = [storage._build_engine(url) for _ in range(6)]
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            applied = list(pool.map(migrate, engines))
        with engines[0].connect() as connection:
            versions = connection.execute(select(MIGRATIONS.c.version).order_by(MIGRATIONS.c.version)).scalars().all()
    finally:
        for engine in engines:
            engine.dispose()
    assert versions == list(range(1, LATEST_VERSION + 1))
    assert sorted(version for result in applied for version in result) == list(range(1, LATEST_VERSION + 1))


# --- Persistence across connections and transactional rollback --------------------------------

def test_related_records_persist_across_connections_and_restart(database):
    with TestClient(app) as client:
        prediction = client.post("/api/v1/risk/predict", json=ELEVATED).json()
        alert_id = client.get("/api/v1/alerts", params={"patient_id": ELEVATED["patient_id"]}).json()["items"][0]["id"]
        client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"actor": "demo-nurse"})
        session = client.post("/api/v1/live-demo/sessions", json={"scenario": "stable"}).json()
    dispose_engines()
    # An independent engine (a different connection pool, as another process would have) sees every record.
    independent = create_engine(storage._database_url())
    try:
        with independent.connect() as connection:
            saved = connection.execute(select(observations).where(observations.c.id == prediction["observation_id"])).mappings().one()
            alert = connection.execute(select(alerts).where(alerts.c.id == alert_id)).mappings().one()
            audit = connection.execute(select(audit_events.c.action).where(audit_events.c.entity_id == str(alert_id))
                                       .order_by(audit_events.c.id)).scalars().all()
            outbox = connection.execute(select(event_outbox.c.event_type).order_by(event_outbox.c.id)).scalars().all()
            stream = connection.execute(select(stream_sessions.c.status)).scalar()
    finally:
        independent.dispose()
    assert json.loads(saved["input_json"])["spo2"] == 78
    assert alert["status"] == "acknowledged" and audit == ["created", "acknowledged"]
    assert outbox == ["observation.created", "alert.created", "alert.updated", "stream.state"]
    assert stream == "running" and session["session"]["status"] == "running"
    with TestClient(app) as client:  # a restarted application reads the same data
        history = client.get("/api/v1/observations", params={"patient_id": ELEVATED["patient_id"]}).json()
    assert history["items"][0]["id"] == prediction["observation_id"]


def _assert_nothing_written(engine):
    assert {name: count for name, count in _counts(engine).items() if count} == {}


def test_failure_in_push_enqueue_rolls_back_observation_alert_audit_and_events(database, monkeypatch):
    def failing_enqueue(*_args, **_kwargs):
        raise OperationalError("INSERT INTO push_deliveries", {}, Exception("simulated failure"))

    with TestClient(app) as client:
        monkeypatch.setattr(notification_service, "enqueue_for_alert", failing_enqueue)
        response = client.post("/api/v1/risk/predict", json=ELEVATED)
        _assert_nothing_written(storage.get_engine())
    assert response.status_code == 503 and response.json()["error"] == "database_unavailable"


def test_failure_writing_the_event_rolls_back_a_stream_observation(database, monkeypatch):
    monkeypatch.setattr(stream_service, "MIN_EMIT_GAP_SECONDS", 0)
    with TestClient(app) as client:
        session = client.post("/api/v1/live-demo/sessions", json={"scenario": "worsening"}).json()
        session_id, token = session["session"]["session_id"], session["producer_token"]
        original = observation_service.record_event

        def failing_record_event(connection, event_type, *args, **kwargs):
            if event_type == "observation.created":
                raise OperationalError("INSERT INTO event_outbox", {}, Exception("simulated failure"))
            return original(connection, event_type, *args, **kwargs)

        monkeypatch.setattr(observation_service, "record_event", failing_record_event)
        failed = client.post(f"/api/v1/live-demo/sessions/{session_id}/observations", json={"sequence": 0},
                             headers={"X-Producer-Token": token})
        state = client.get(f"/api/v1/live-demo/sessions/{session_id}").json()["session"]
        counts = _counts(storage.get_engine())
    assert failed.status_code == 503
    assert state["next_sequence"] == 0
    assert counts["observations"] == 0 and counts["alerts"] == 0


# --- Configuration and availability ----------------------------------------------------------

@pytest.mark.parametrize("value", [
    f"postgresql//vgadmin:{SECRET}@db.internal:5432/vg",
    f'"postgresql://vgadmin:{SECRET}@db.internal:5432/vg"',
    f"postgresql://vgadmin:{SECRET}@db.internal:notaport/vg",
])
def test_malformed_database_url_fails_with_an_actionable_error_that_hides_the_value(monkeypatch, value):
    monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(StorageConfigurationError) as error:
        initialize_storage()
    rendered = "".join(traceback.format_exception(error.value))
    assert SECRET not in rendered and "db.internal" not in rendered
    assert "DATABASE_URL" in str(error.value) and "not shown" in str(error.value)


def test_hosted_platform_on_sqlite_is_reported_not_silent(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("VITALGUARD_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "ephemeral.sqlite3"))
    monkeypatch.setenv("RENDER", "true")
    caplog.set_level(logging.ERROR, logger="vitalguard.storage")
    with TestClient(app) as client:
        body = client.get("/health").json()
    database = body["database"]
    assert body["status"] == "degraded" and database["status"] == "degraded"
    assert database["backend"] == "sqlite" and database["durable_backend"] is False
    assert database["hosted_platform"] == "render" and "data is lost on restart" in database["warnings"][0]
    assert "Storage misconfiguration" in caplog.text


def test_local_sqlite_is_not_flagged(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("VITALGUARD_HOSTED", raising=False)
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "local.sqlite3"))
    with TestClient(app) as client:
        database = client.get("/health").json()["database"]
    assert database["status"] == "ok" and database["warnings"] == [] and database["hosted_platform"] is None


@pytest.mark.parametrize("database", ["postgresql"], indirect=True)
def test_hosted_platform_on_postgresql_is_healthy(database, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    with TestClient(app) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok" and body["database"]["backend"] == "postgresql"
    assert body["database"]["warnings"] == [] and body["database"]["durable_backend"] is True


def test_required_postgres_refuses_hosted_sqlite_startup(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "x.sqlite3"))
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("VITALGUARD_REQUIRE_POSTGRES", "true")
    with pytest.raises(StorageConfigurationError, match="refusing to start"):
        with TestClient(app):
            pass


def test_database_unavailable_after_startup_gives_honest_errors(database):
    broken = create_engine(f"postgresql+psycopg://vg:{SECRET}@127.0.0.1:1/unreachable", connect_args={"connect_timeout": 1},
                           hide_parameters=True)
    with TestClient(app) as client:
        storage._ENGINES[storage._database_url()] = broken
        write = client.post("/api/v1/risk/predict", json=ELEVATED)
        ready = client.get("/health/ready")
        health = client.get("/health")
        live = client.get("/health/live")
    assert write.status_code == 503 and write.json()["error"] == "database_unavailable"
    assert ready.status_code == 503 and health.status_code == 503 and live.status_code == 200
    for response in (write, ready, health):
        assert SECRET not in response.text

import json
import pytest
from fastapi.testclient import TestClient
from app.db_tools import RestoreRefused, _build_engine, export_snapshot, main, restore_snapshot, table_digests
from app.main import app
from app.storage import get_engine
from conftest import POSTGRES_TEST_URL, reset_postgres_schema

ELEVATED = {"patient_id": "DEMO-BACKUP-001", "age": 70, "heart_rate": 180, "spo2": 78, "systolic_bp": 80,
            "diastolic_bp": 50, "temperature": 39.5, "respiratory_rate": 34}


def _seed_records() -> None:
    with TestClient(app) as client:
        client.post("/api/v1/risk/predict", json=ELEVATED)
        client.post("/api/v1/demo/observations", json={"patient_id": "DEMO-BACKUP-002", "scenario": "worsening", "step": 2})
        alert_id = client.get("/api/v1/alerts").json()["items"][0]["id"]
        client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"actor": "demo-nurse"})
        client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"actor": "demo-nurse"})


def _restore_targets(tmp_path):
    targets = [("sqlite", f"sqlite+pysqlite:///{tmp_path / 'restored.sqlite3'}")]
    if POSTGRES_TEST_URL:
        targets.append(("postgresql", POSTGRES_TEST_URL))
    return targets


def test_snapshot_restores_identically_into_an_empty_database(database, tmp_path):
    _seed_records()
    snapshot = export_snapshot(get_engine())
    assert snapshot["synthetic_demo_data_only"] is True
    assert snapshot["digests"]["observations"]["rows"] == 2
    assert snapshot["digests"]["audit_events"]["rows"] == 4

    for backend, url in _restore_targets(tmp_path):
        if backend == database == "postgresql":
            continue  # source and target would be the same database
        if backend == "postgresql":
            reset_postgres_schema(url)
        target = _build_engine(url)
        try:
            restored = restore_snapshot(target, snapshot)
            assert restored == snapshot["digests"]
            # Sequences/rowids continue after the restored ids, so new writes do not collide.
            from app.storage import insert_observation
            with target.begin() as connection:
                new_row = insert_observation(connection, "DEMO-AFTER-RESTORE", {}, {"model_version": "test"})
            assert new_row["id"] > max(row["id"] for row in snapshot["tables"]["observations"])
        finally:
            target.dispose()


def test_restore_refuses_a_non_empty_target(database):
    _seed_records()
    snapshot = export_snapshot(get_engine())
    with pytest.raises(RestoreRefused, match="not empty"):
        restore_snapshot(get_engine(), snapshot)
    assert table_digests(get_engine()) == snapshot["digests"]


def test_restore_refuses_a_tampered_snapshot(database, tmp_path):
    _seed_records()
    snapshot = export_snapshot(get_engine())
    snapshot["tables"]["alerts"][0]["status"] = "tampered"
    target = _build_engine(f"sqlite+pysqlite:///{tmp_path / 'tampered.sqlite3'}")
    try:
        with pytest.raises(RestoreRefused, match="checksum"):
            restore_snapshot(target, snapshot)
    finally:
        target.dispose()


def test_cli_round_trip_reads_urls_only_from_environment(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "source.sqlite3"))
    _seed_records()
    monkeypatch.setenv("SOURCE_DB", f"sqlite:///{tmp_path / 'source.sqlite3'}")
    monkeypatch.setenv("TARGET_DB", f"sqlite:///{tmp_path / 'target.sqlite3'}")
    snapshot_path = tmp_path / "snapshot.json"

    assert main(["export", "--url-env", "SOURCE_DB", "--out", str(snapshot_path)]) == 0
    assert oct(snapshot_path.stat().st_mode & 0o777) == "0o600"
    assert main(["restore", "--url-env", "TARGET_DB", "--in", str(snapshot_path)]) == 0
    assert main(["verify", "--url-env", "TARGET_DB", "--in", str(snapshot_path)]) == 0
    assert main(["restore", "--url-env", "TARGET_DB", "--in", str(snapshot_path)]) == 2  # target no longer empty
    output = capsys.readouterr().out
    assert str(tmp_path) not in output.replace(str(snapshot_path), "")
    assert json.loads(snapshot_path.read_text())["format"] == "vitalguard-demo-snapshot"

"""Regression coverage for committed demo history across storage reinitialization."""
from app.storage import initialize_storage, list_observations, save_observation


def test_observation_survives_storage_reinitialization(tmp_path, monkeypatch):
    """A fresh engine after app-style initialization can read the committed record."""
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "restart.sqlite3"))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    initialize_storage()
    saved = save_observation(
        "DEMO-RESTART-001",
        {"age": 58, "spo2": 98},
        {"model_version": "test-model", "risk_score": 24},
    )

    # Simulate a process restart by rerunning startup initialization.
    initialize_storage()
    rows = list_observations(patient_id="DEMO-RESTART-001", limit=10)

    assert len(rows) == 1
    assert rows[0]["id"] == saved["id"]
    assert rows[0]["inputs"] == {"age": 58, "spo2": 98}
    assert rows[0]["prediction"]["risk_score"] == 24

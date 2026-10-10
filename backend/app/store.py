"""Small SQLite store for synthetic monitoring demo observations.

The default database lives in /tmp on hosted deployments and is ephemeral.
Set VITALGUARD_DB_PATH to choose another writable path. This is not a
production patient-record store.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _database_path() -> str:
    return os.getenv("VITALGUARD_DB_PATH", "/tmp/vitalguard-observations.sqlite3")


def _connect() -> sqlite3.Connection:
    path = _database_path()
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_store() -> None:
    with _connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                vitals_json TEXT NOT NULL,
                prediction_json TEXT NOT NULL
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_patient_time "
            "ON observations(patient_id, recorded_at DESC)"
        )


def save_observation(vitals: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    initialize_store()
    recorded_at = datetime.now(timezone.utc).isoformat()
    patient_id = str(vitals["patient_id"])
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO observations(patient_id, recorded_at, vitals_json, prediction_json) "
            "VALUES (?, ?, ?, ?)",
            (
                patient_id,
                recorded_at,
                json.dumps(vitals, separators=(",", ":")),
                json.dumps(prediction, separators=(",", ":")),
            ),
        )
        record_id = int(cursor.lastrowid)
    return {
        "id": record_id,
        "patient_id": patient_id,
        "recorded_at": recorded_at,
        "vitals": vitals,
        "prediction": prediction,
    }


def list_observations(patient_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    initialize_store()
    with _connect() as connection:
        if patient_id:
            rows = connection.execute(
                "SELECT * FROM observations WHERE patient_id = ? "
                "ORDER BY recorded_at DESC, id DESC LIMIT ?",
                (patient_id, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM observations ORDER BY recorded_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [
        {
            "id": row["id"],
            "patient_id": row["patient_id"],
            "recorded_at": row["recorded_at"],
            "vitals": json.loads(row["vitals_json"]),
            "prediction": json.loads(row["prediction_json"]),
        }
        for row in rows
    ]

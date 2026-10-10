"""Small SQLite repository for synthetic demo predictions.

Stores only inputs and outputs submitted to this prototype. This is not a
production patient-record system and must not be used with real patient data.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

_DEFAULT_DB = Path(__file__).resolve().parents[1] / "vitalguard_demo.sqlite3"


def _db_path() -> str:
    return os.getenv("VITALGUARD_DB_PATH", str(_DEFAULT_DB))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_storage() -> None:
    with _connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                input_json TEXT NOT NULL,
                prediction_json TEXT NOT NULL,
                model_version TEXT NOT NULL
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_patient_created "
            "ON observations(patient_id, created_at DESC, id DESC)"
        )


def save_observation(patient_id: str, inputs: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    initialize_storage()
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO observations(patient_id, input_json, prediction_json, model_version) VALUES (?, ?, ?, ?)",
            (patient_id, json.dumps(inputs, separators=(",", ":")),
             json.dumps(prediction, separators=(",", ":")), prediction["model_version"]),
        )
        row = connection.execute(
            "SELECT id, patient_id, created_at, input_json, prediction_json, model_version "
            "FROM observations WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _serialize(row)


def list_observations(patient_id: str | None = None, limit: int = 50, before_id: int | None = None) -> list[dict[str, Any]]:
    initialize_storage()
    clauses: list[str] = []
    args: list[Any] = []
    if patient_id is not None:
        clauses.append("patient_id = ?")
        args.append(patient_id)
    if before_id is not None:
        clauses.append("id < ?")
        args.append(before_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(limit)
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, patient_id, created_at, input_json, prediction_json, model_version "
            f"FROM observations{where} ORDER BY id DESC LIMIT ?", args
        ).fetchall()
    return [_serialize(row) for row in rows]


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "patient_id": row["patient_id"],
        "created_at": row["created_at"],
        "inputs": json.loads(row["input_json"]),
        "prediction": json.loads(row["prediction_json"]),
        "model_version": row["model_version"],
    }

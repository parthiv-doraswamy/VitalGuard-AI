"""Database repository for synthetic demo predictions.

Uses DATABASE_URL when configured (PostgreSQL on a hosted deployment), and
falls back to a local SQLite file for development. This prototype must not be
used with real patient data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    insert,
    select,
)
from sqlalchemy.engine import Engine

_DEFAULT_DB = Path(__file__).resolve().parents[1] / "vitalguard_demo.sqlite3"
_METADATA = MetaData()
_OBSERVATIONS = Table(
    "observations",
    _METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("patient_id", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("input_json", Text, nullable=False),
    Column("prediction_json", Text, nullable=False),
    Column("model_version", String(128), nullable=False),
)
Index(
    "idx_observations_patient_created",
    _OBSERVATIONS.c.patient_id,
    _OBSERVATIONS.c.created_at.desc(),
    _OBSERVATIONS.c.id.desc(),
)


def _database_url() -> str:
    """Prefer a hosted DATABASE_URL; preserve SQLite as the local default."""
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured:
        if configured.startswith("postgres://"):
            return "postgresql+psycopg://" + configured[len("postgres://") :]
        if configured.startswith("postgresql://"):
            return "postgresql+psycopg://" + configured[len("postgresql://") :]
        return configured

    path = os.getenv("VITALGUARD_DB_PATH", str(_DEFAULT_DB))
    if path == ":memory:":
        return "sqlite+pysqlite:///:memory:"
    absolute_path = Path(path).expanduser().resolve()
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{absolute_path.as_posix()}"


def _engine() -> Engine:
    url = _database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def initialize_storage() -> None:
    engine = _engine()
    try:
        _METADATA.create_all(engine)
    finally:
        engine.dispose()


def save_observation(
    patient_id: str,
    inputs: dict[str, Any],
    prediction: dict[str, Any],
) -> dict[str, Any]:
    engine = _engine()
    try:
        _METADATA.create_all(engine)
        with engine.begin() as connection:
            result = connection.execute(
                insert(_OBSERVATIONS).values(
                    patient_id=patient_id,
                    input_json=json.dumps(inputs, separators=(",", ":")),
                    prediction_json=json.dumps(prediction, separators=(",", ":")),
                    model_version=prediction["model_version"],
                )
            )
            observation_id = result.inserted_primary_key[0]
            row = connection.execute(
                select(_OBSERVATIONS).where(_OBSERVATIONS.c.id == observation_id)
            ).mappings().one()
        return _serialize(row)
    finally:
        engine.dispose()


def list_observations(
    patient_id: str | None = None,
    limit: int = 50,
    before_id: int | None = None,
) -> list[dict[str, Any]]:
    engine = _engine()
    try:
        _METADATA.create_all(engine)
        query = select(_OBSERVATIONS)
        if patient_id is not None:
            query = query.where(_OBSERVATIONS.c.patient_id == patient_id)
        if before_id is not None:
            query = query.where(_OBSERVATIONS.c.id < before_id)
        query = query.order_by(_OBSERVATIONS.c.id.desc()).limit(limit)
        with engine.connect() as connection:
            rows = connection.execute(query).mappings().all()
        return [_serialize(row) for row in rows]
    finally:
        engine.dispose()


def _serialize(row: Any) -> dict[str, Any]:
    created_at = row["created_at"]
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    return {
        "id": row["id"],
        "patient_id": row["patient_id"],
        "created_at": created_at,
        "inputs": json.loads(row["input_json"]),
        "prediction": json.loads(row["prediction_json"]),
        "model_version": row["model_version"],
    }

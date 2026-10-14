"""Database repository for synthetic demo predictions; never use real patient data.

PostgreSQL (via DATABASE_URL) is the durable hosted store. SQLite is a
local-development and test fallback only; on hosted ephemeral filesystems it
does not survive restarts or redeploys.
"""
from __future__ import annotations
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any
from sqlalchemy import create_engine, event, insert, select, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import StaticPool

from .storage_schema import observations as _OBSERVATIONS

_DEFAULT_DB = Path(__file__).resolve().parents[1] / "vitalguard_demo.sqlite3"
_ENGINES: dict[str, Engine] = {}
_ENGINES_LOCK = threading.Lock()
logger = logging.getLogger("vitalguard.storage")


class StorageConfigurationError(RuntimeError):
    """Raised at startup when the configured database is unusable or not allowed."""


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise StorageConfigurationError(f"{name} must be an integer") from exc


def _database_url() -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured.startswith("postgres://"):
        return "postgresql+psycopg://" + configured[len("postgres://"):]
    if configured.startswith("postgresql://"):
        return "postgresql+psycopg://" + configured[len("postgresql://"):]
    if configured:
        return configured
    path = os.getenv("VITALGUARD_DB_PATH", str(_DEFAULT_DB))
    if path == ":memory:":
        return "sqlite+pysqlite:///:memory:"
    absolute_path = Path(path).expanduser().resolve()
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{absolute_path.as_posix()}"


def _backend_name(url: str) -> str:
    """Dialect name of a database URL; never echoes the URL (it may contain a password)."""
    try:
        return make_url(url).get_backend_name()
    except (ArgumentError, ValueError):
        raise StorageConfigurationError(
            "DATABASE_URL could not be parsed. Expected postgresql://USER:PASSWORD@HOST:PORT/DBNAME "
            "without surrounding quotes or spaces (the configured value is not shown).") from None


def hosted_platform() -> str | None:
    """Name of the hosting platform when running hosted (Render sets RENDER=true), else None."""
    if os.getenv("VITALGUARD_HOSTED", "").strip().lower() in {"1", "true", "yes"}:
        return "configured"
    if os.getenv("RENDER", "").strip().lower() == "true":
        return "render"
    return None


def _storage_warnings(backend: str) -> list[str]:
    if backend == "sqlite" and hosted_platform():
        return ["Hosted deployment is using SQLite on the instance's local disk; data is lost on restart or "
                "redeploy. Set DATABASE_URL to the managed PostgreSQL database, verify /health reports "
                "postgresql, then set VITALGUARD_REQUIRE_POSTGRES=true."]
    return []


def postgres_required() -> bool:
    """Hosted deployments set VITALGUARD_REQUIRE_POSTGRES=true to refuse SQLite."""
    return os.getenv("VITALGUARD_REQUIRE_POSTGRES", "").strip().lower() in {"1", "true", "yes"}


def _build_engine(url: str) -> Engine:
    backend = _backend_name(url)
    # hide_parameters keeps bound values (synthetic vitals) out of error text and logs.
    if backend == "sqlite":
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False,
                                                   "timeout": _int_env("VITALGUARD_SQLITE_BUSY_TIMEOUT_SECONDS", 15)}}
        if url.endswith(":memory:"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, hide_parameters=True, pool_pre_ping=True, **kwargs)
        if not url.endswith(":memory:"):
            @event.listens_for(engine, "connect")
            def _sqlite_pragmas(dbapi_connection, _record):
                cursor = dbapi_connection.cursor()
                # WAL lets readers proceed during a write; NORMAL is durable in WAL mode.
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()
        return engine
    if backend == "postgresql":
        statement_timeout_ms = _int_env("VITALGUARD_DB_STATEMENT_TIMEOUT_MS", 15000)
        idle_tx_timeout_ms = _int_env("VITALGUARD_DB_IDLE_TX_TIMEOUT_MS", 30000)
        return create_engine(
            url,
            hide_parameters=True,
            pool_pre_ping=True,
            pool_size=_int_env("VITALGUARD_DB_POOL_SIZE", 5),
            max_overflow=_int_env("VITALGUARD_DB_MAX_OVERFLOW", 5),
            pool_timeout=_int_env("VITALGUARD_DB_POOL_TIMEOUT_SECONDS", 10),
            pool_recycle=_int_env("VITALGUARD_DB_POOL_RECYCLE_SECONDS", 1800),
            connect_args={
                "connect_timeout": _int_env("VITALGUARD_DB_CONNECT_TIMEOUT_SECONDS", 10),
                "application_name": "vitalguard-api",
                "options": f"-c statement_timeout={statement_timeout_ms} "
                           f"-c idle_in_transaction_session_timeout={idle_tx_timeout_ms}",
            },
        )
    raise StorageConfigurationError(
        f"Unsupported database backend '{backend}'. Use PostgreSQL, or SQLite for local development only.")


def get_engine() -> Engine:
    """Return the pooled engine for the configured URL, migrating it on first use.

    Engines are cached per URL so requests share a connection pool instead of
    opening and disposing a pool per call.
    """
    url = _database_url()
    engine = _ENGINES.get(url)
    if engine is not None:
        return engine
    with _ENGINES_LOCK:
        engine = _ENGINES.get(url)
        if engine is None:
            engine = _build_engine(url)
            from .migrations import migrate
            try:
                migrate(engine)
            except Exception:
                engine.dispose()
                raise
            _ENGINES[url] = engine
        return engine


# Kept for modules that import the previous private helper name.
_engine = get_engine


def dispose_engines() -> None:
    """Close every pooled connection; called at shutdown and between isolated tests."""
    with _ENGINES_LOCK:
        for engine in _ENGINES.values():
            engine.dispose()
        _ENGINES.clear()


def initialize_storage() -> None:
    """Validate database selection and apply migrations before serving traffic.

    Fails fast (the process does not start) when PostgreSQL is required but the
    configuration resolves to anything else, or when the database is unreachable.
    """
    url = _database_url()
    backend = _backend_name(url)
    if postgres_required() and backend != "postgresql":
        raise StorageConfigurationError(
            "VITALGUARD_REQUIRE_POSTGRES is set but DATABASE_URL does not point to PostgreSQL; "
            "refusing to start on non-durable storage.")
    for warning in _storage_warnings(backend):
        # Not fatal unless VITALGUARD_REQUIRE_POSTGRES is set, but never silent.
        logger.error("Storage misconfiguration: %s", warning)
    engine = get_engine()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def database_health() -> dict[str, Any]:
    """Read-only probe of the live database; never returns the URL or credentials."""
    from .migrations import LATEST_VERSION, current_version
    engine = get_engine()
    started = time.perf_counter()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        schema_version = current_version(connection)
        server_version = None
        if engine.dialect.name == "postgresql":
            server_version = connection.execute(text("SHOW server_version")).scalar()
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    backend = "postgresql" if engine.dialect.name == "postgresql" else "sqlite"
    warnings = _storage_warnings(backend)
    if schema_version != LATEST_VERSION:
        warnings.append(f"Schema version {schema_version} is behind the application ({LATEST_VERSION}).")
    return {
        "status": "ok" if not warnings else "degraded",
        "backend": backend,
        "durable_backend": backend == "postgresql",
        "postgres_required": postgres_required(),
        "hosted_platform": hosted_platform(),
        "warnings": warnings,
        "server_version": server_version,
        "schema_version": schema_version,
        "latest_schema_version": LATEST_VERSION,
        "latency_ms": latency_ms,
    }


def insert_observation(connection: Connection, patient_id: str, inputs: dict[str, Any],
                       prediction: dict[str, Any], session_id: str | None = None,
                       sequence: int | None = None) -> dict[str, Any]:
    """Insert one observation inside the caller's transaction."""
    result = connection.execute(insert(_OBSERVATIONS).values(
        patient_id=patient_id,
        session_id=session_id,
        sequence=sequence,
        input_json=json.dumps(inputs, separators=(",", ":")),
        prediction_json=json.dumps(prediction, separators=(",", ":")),
        model_version=prediction["model_version"],
    ))
    observation_id = result.inserted_primary_key[0]
    row = connection.execute(select(_OBSERVATIONS).where(_OBSERVATIONS.c.id == observation_id)).mappings().one()
    return _serialize(row)


def save_observation(patient_id: str, inputs: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    with get_engine().begin() as connection:
        return insert_observation(connection, patient_id, inputs, prediction)


def list_observations(patient_id: str | None = None, limit: int = 50, before_id: int | None = None,
                      after_id: int | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
    """Newest first by default; with after_id, oldest first (for catching up after a reconnect)."""
    query = select(_OBSERVATIONS)
    if patient_id is not None:
        query = query.where(_OBSERVATIONS.c.patient_id == patient_id)
    if session_id is not None:
        query = query.where(_OBSERVATIONS.c.session_id == session_id)
    if before_id is not None:
        query = query.where(_OBSERVATIONS.c.id < before_id)
    if after_id is not None:
        query = query.where(_OBSERVATIONS.c.id > after_id).order_by(_OBSERVATIONS.c.id.asc()).limit(limit)
    else:
        query = query.order_by(_OBSERVATIONS.c.id.desc()).limit(limit)
    with get_engine().connect() as connection:
        rows = connection.execute(query).mappings().all()
    return [_serialize(row) for row in rows]


def get_stream_observation(session_id: str, sequence: int) -> dict[str, Any] | None:
    query = select(_OBSERVATIONS).where(_OBSERVATIONS.c.session_id == session_id, _OBSERVATIONS.c.sequence == sequence)
    with get_engine().connect() as connection:
        row = connection.execute(query).mappings().first()
    return _serialize(row) if row else None


def _serialize(row: Any) -> dict[str, Any]:
    created_at = row["created_at"]
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    return {"id": row["id"], "patient_id": row["patient_id"], "created_at": created_at,
            "inputs": json.loads(row["input_json"]), "prediction": json.loads(row["prediction_json"]), "model_version": row["model_version"],
            "session_id": row["session_id"], "sequence": row["sequence"]}

"""Operational database tools for the synthetic VitalGuard demo.

Run from backend/:  python -m app.db_tools <command>

  status                         Show backend, schema version and row counts.
  migrate                        Apply pending migrations.
  export  --out FILE             Write a checksummed logical snapshot of all tables.
  restore --in FILE              Load a snapshot into an EMPTY database, then verify it.
  verify  --in FILE              Compare a database against a snapshot's checksums.

Database URLs are read only from environment variables (DATABASE_URL by
default; override with --url-env NAME) so credentials never appear in shell
history or process listings. Output never prints the URL.

The logical snapshot is a portable restore *drill* for small demo databases
and works across SQLite and PostgreSQL. For hosted PostgreSQL, the provider's
managed backups or pg_dump/pg_restore remain the primary backup mechanism; see
docs/PERSISTENCE.md. Snapshots contain every stored record; keep them private
and never commit them.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import func, insert, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .migrations import LATEST_VERSION, current_version, migrate
from .storage import _build_engine
from .storage_schema import APPLICATION_TABLES

SNAPSHOT_FORMAT = "vitalguard-demo-snapshot"


class RestoreRefused(RuntimeError):
    pass


def _normalize(value: Any) -> Any:
    # SQLite returns naive UTC timestamps; PostgreSQL returns aware ones.
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return value


def _table_rows(connection, table) -> list[dict[str, Any]]:
    primary_key = list(table.primary_key.columns)
    rows = connection.execute(select(table).order_by(*primary_key)).mappings().all()
    return [{key: _normalize(value) for key, value in row.items()} for row in rows]


def _digest(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def table_digests(engine: Engine) -> dict[str, dict[str, Any]]:
    with engine.connect() as connection:
        return {table.name: {"rows": len(rows), "sha256": _digest(rows)}
                for table in APPLICATION_TABLES for rows in [_table_rows(connection, table)]}


def export_snapshot(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        version = current_version(connection)
        tables = {table.name: _table_rows(connection, table) for table in APPLICATION_TABLES}
    return {
        "format": SNAPSHOT_FORMAT,
        "format_version": 1,
        "synthetic_demo_data_only": True,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_backend": engine.dialect.name,
        "schema_version": version,
        "tables": tables,
        "digests": {name: {"rows": len(rows), "sha256": _digest(rows)} for name, rows in tables.items()},
    }


def _parse_row(table, row: dict[str, Any]) -> dict[str, Any]:
    parsed = {}
    for key, value in row.items():
        column = table.c[key]
        if value is not None and column.type.python_type is datetime:
            value = datetime.fromisoformat(value)
        parsed[key] = value
    return parsed


def restore_snapshot(engine: Engine, snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Restore into an empty, migrated database in one transaction and verify checksums."""
    if snapshot.get("format") != SNAPSHOT_FORMAT:
        raise RestoreRefused("File is not a VitalGuard demo snapshot")
    if snapshot.get("schema_version") != LATEST_VERSION:
        raise RestoreRefused(f"Snapshot schema version {snapshot.get('schema_version')} does not match "
                             f"this release ({LATEST_VERSION}); migrate the source and export again")
    for name, rows in snapshot["tables"].items():
        if _digest(rows) != snapshot["digests"][name]["sha256"]:
            raise RestoreRefused(f"Snapshot checksum mismatch for table {name}; file is corrupt or edited")
    migrate(engine)
    with engine.begin() as connection:
        for table in APPLICATION_TABLES:
            if connection.execute(select(func.count()).select_from(table)).scalar():
                raise RestoreRefused(f"Target table {table.name} is not empty; restore only into an empty database")
        for table in APPLICATION_TABLES:
            rows = [_parse_row(table, row) for row in snapshot["tables"].get(table.name, [])]
            if rows:
                connection.execute(insert(table), rows)
        if engine.dialect.name == "postgresql":
            # Explicit ids bypass sequences; move them past the restored maximum.
            for table in APPLICATION_TABLES:
                if "id" in table.c:
                    connection.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                        f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table.name}"))
    restored = table_digests(engine)
    mismatched = [name for name, digest in snapshot["digests"].items() if restored.get(name) != digest]
    if mismatched:
        raise RestoreRefused(f"Restored data does not match snapshot for: {', '.join(mismatched)}")
    return restored


def _engine_from_env(name: str) -> Engine:
    url = os.getenv(name, "").strip()
    if not url:
        raise SystemExit(f"Environment variable {name} is not set")
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
    if url.startswith("sqlite:///") and not url.startswith("sqlite+"):
        url = "sqlite+pysqlite:///" + url[len("sqlite:///"):]
    return _build_engine(url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.db_tools", description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["status", "migrate", "export", "restore", "verify"])
    parser.add_argument("--url-env", default="DATABASE_URL", help="environment variable holding the database URL")
    parser.add_argument("--out", help="snapshot file to write (export)")
    parser.add_argument("--in", dest="infile", help="snapshot file to read (restore/verify)")
    args = parser.parse_args(argv)
    engine = _engine_from_env(args.url_env)
    try:
        if args.command == "status":
            with engine.connect() as connection:
                version = current_version(connection)
            counts = {name: info["rows"] for name, info in table_digests(engine).items()} if version else {}
            print(json.dumps({"backend": engine.dialect.name, "schema_version": version,
                              "latest_schema_version": LATEST_VERSION, "row_counts": counts}, indent=2))
        elif args.command == "migrate":
            applied = migrate(engine)
            print(json.dumps({"backend": engine.dialect.name, "applied": applied, "schema_version": LATEST_VERSION}))
        elif args.command == "export":
            if not args.out:
                parser.error("export requires --out")
            snapshot = export_snapshot(engine)
            descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as handle:
                json.dump(snapshot, handle)
            print(json.dumps({"backend": engine.dialect.name, "out": args.out, "digests": snapshot["digests"]}, indent=2))
        else:
            if not args.infile:
                parser.error(f"{args.command} requires --in")
            with open(args.infile) as handle:
                snapshot = json.load(handle)
            if args.command == "restore":
                restored = restore_snapshot(engine, snapshot)
                print(json.dumps({"backend": engine.dialect.name, "restored": restored, "verified": True}, indent=2))
            else:
                current = table_digests(engine)
                matches = {name: current.get(name) == digest for name, digest in snapshot["digests"].items()}
                print(json.dumps({"backend": engine.dialect.name, "matches": matches}, indent=2))
                return 0 if all(matches.values()) else 1
    except RestoreRefused as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    except SQLAlchemyError as exc:
        # Driver messages can include host names; report only the error class.
        print(f"Database error ({type(exc).__name__}); check that {args.url_env} points to a reachable database.",
              file=sys.stderr)
        return 3
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

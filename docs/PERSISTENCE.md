# Persistence — configuration, guarantees, migrations, backup and restore

> Every record stored by this service is **synthetic demonstration data**. The
> database is not a medical record system. Never store real patient data.

## 1. Database selection

| Setting | Effect |
| --- | --- |
| `DATABASE_URL` set to `postgres://…` or `postgresql://…` | PostgreSQL via psycopg 3. **The only supported hosted, durable store.** |
| `DATABASE_URL` unset | SQLite file at `VITALGUARD_DB_PATH` (default `backend/vitalguard_demo.sqlite3`). Local development and tests only. |
| `DATABASE_URL` with any other scheme | Startup fails with `StorageConfigurationError`. |
| `VITALGUARD_REQUIRE_POSTGRES=true` | Startup fails unless the URL resolves to PostgreSQL. **Set this on every hosted backend service.** |

Startup (`initialize_storage`, run from the FastAPI lifespan) validates the
selection, applies migrations and runs `SELECT 1`. If any step fails, the
process exits before serving traffic, so a misconfigured deploy fails visibly
instead of silently writing to an ephemeral SQLite file.

SQLite on a hosted ephemeral filesystem is lost on restart/redeploy. A
restart check with SQLite `:memory:` was used as a negative control and
correctly reported the records as missing (see §7).

### Connection handling

- One pooled engine per process (cached per URL), shared by all requests.
  Earlier versions created and disposed an engine on every call.
- PostgreSQL defaults: `pool_size=5`, `max_overflow=5`, `pool_timeout=10s`,
  `pool_recycle=1800s`, `pool_pre_ping`, `connect_timeout=10s`,
  `statement_timeout=15s`, `idle_in_transaction_session_timeout=30s`,
  `application_name=vitalguard-api`. All are overridable via the
  `VITALGUARD_DB_*` variables listed in `.env.example`.
- With the defaults, one instance opens at most 10 connections. Check the
  provider plan's connection limit before raising the pool or running more instances.
- SQLite: WAL journal, `synchronous=NORMAL`, 15 s busy timeout.
- Engines use `hide_parameters=True`, so bound values never appear in errors or logs.
- Pools are disposed on application shutdown.

## 2. Write and event semantics

`POST /api/v1/risk/predict` and `POST /api/v1/demo/observations` share one path
(`backend/app/observation_service.py`):

1. Score the observation in memory.
2. In **one transaction**, insert the observation. For `/risk/predict` with a
   score of 65 or more, also insert its alert and the alert's `created` audit row.
3. Commit.
4. Only after the commit, broadcast `observation.created` (and `alert.created`).

If any insert or the commit fails, nothing is stored, no WebSocket event is
sent, and the client receives **HTTP 503** with
`{"error": "database_unavailable", "detail": "Database unavailable; the request was not saved."}`.
Before this change, a failed alert insert could leave a committed observation
whose event had already been broadcast, and the response was an unhandled 500.

The simulator endpoint still does not raise alerts. That is unchanged behaviour,
kept on purpose.

Alert transitions use conditional updates (`WHERE status = 'open'` for
acknowledge, `WHERE status <> 'resolved'` for resolve). Concurrent requests
therefore produce exactly one state change and one audit row. They now also set
`acknowledged_at` and `resolved_at`, which were previously always NULL.

Every SQLAlchemy error from any endpoint becomes a 503 with the same body. The
response never contains connection details; the server log records only the
exception class.

## 3. Bounded queries and pagination

| Endpoint | Bound | Cursor |
| --- | --- | --- |
| `GET /api/v1/observations` | `limit` 1–100 | `before_id` → `next_before_id` |
| `GET /api/v1/alerts` | `limit` 1–100 | `before_id` → `next_before_id` (new) |
| `GET /api/v1/alerts/{id}/audit` | `limit` 1–500, default 100 (new) | — |
| `GET /api/v1/patients/{id}/timeline` | `limit` 1–100; audit rows fetched in one bounded query (was one query per alert) | — |
| `GET /api/v1/observations/trends`, `/quality` | `limit` ≤ 100 | — |

The audit endpoint's 404 check now looks up the alert directly. Previously it
scanned only the 100 newest alerts, so older alerts were reported as missing.

## 4. Schema and migrations

Tables live in `backend/app/storage_schema.py`: `observations` (inputs and
prediction JSON, plus the stream session and sequence for live-demo records),
`alerts`, `audit_events`, `stream_sessions` (live-demo producer sessions; only a
SHA-256 hash of the producer token is stored), and `patients` (reserved, not
yet written by the API). The `schema_migrations` ledger is in
`backend/app/migrations.py`.

| Version | Name | Change |
| --- | --- | --- |
| 1 | `baseline_tables` | Create the tables (checkfirst; existing tables are kept). |
| 2 | `history_indexes` | `(patient_id, id DESC)` on observations and alerts, `(status, id DESC)` on alerts, `(entity_type, entity_id, id)` on audit_events. |
| 3 | `backfill_alert_timestamps` | Fill NULL `acknowledged_at`/`resolved_at` from the earliest matching audit event. |
| 4 | `live_stream_sessions` | `stream_sessions` table (with a unique `active_slot` allowing one active producer) and nullable `session_id`/`sequence` columns on observations, unique together, so a stream sequence is stored at most once. |

- Each version runs in its own transaction together with its ledger row.
- Every step is idempotent. On PostgreSQL, a session advisory lock serializes
  concurrent startups.
- After the versioned steps, any missing table or index is recreated as a repair.
- Databases written by the previous release (ledger at v1, no `name` column)
  and databases from before the ledger existed are both upgraded in place
  without data loss.
- **Backward compatible:** v2 and v3 only add indexes, a nullable ledger column
  and timestamp values. The previous release was run against a migrated
  PostgreSQL database and served health, predictions and alerts normally, so
  rolling back the code needs no schema rollback.
- Manual run: `cd backend && python -m app.db_tools migrate`. Show the version
  and row counts with `python -m app.db_tools status`.

New session metadata: this branch has no session table to migrate, because
authentication is not implemented on the deployed backend. Add one as a new
numbered step when identity work lands.

## 5. Health check

`GET /health` → `database`:

```json
{"status": "ok", "backend": "postgresql", "durable_backend": true, "postgres_required": true,
 "server_version": "17.x", "schema_version": 3, "latest_schema_version": 3, "latency_ms": 1.4}
```

The check is read-only: it runs `SELECT 1`, reads the ledger and the server
version, and makes no DDL or writes. `status` is `degraded` when the schema is
behind. The response never includes the URL, host, database name, user or
password. `backend` is read from the live connection's dialect, not inferred
from environment variable names.

## 6. Backup and restore

### Primary mechanism (hosted PostgreSQL)

Use the provider's managed backups, or `pg_dump`/`pg_restore`, run from a
machine allowed to reach the database. Do **not** widen the database's network
allowlist (for example to `0.0.0.0/0`) to do this. Check what the current Render
plan includes, such as backup frequency, retention and point-in-time recovery,
in the Render dashboard; this repository makes no claim about it.

```bash
# DATABASE_URL is exported from a private secret store; never pasted into a committed file.
pg_dump --format=custom --no-owner --dbname="$DATABASE_URL" --file=vitalguard-$(date +%F).dump
pg_restore --no-owner --dbname="$RESTORE_TARGET_URL" vitalguard-YYYY-MM-DD.dump   # EMPTY non-production DB only
```

### Restore verification drill (repeatable)

`backend/app/db_tools.py` creates a checksummed logical snapshot and verifies a
restore. It works across SQLite and PostgreSQL, reads database URLs **only from
environment variables**, and refuses to restore into a database that has rows.

```bash
cd backend
export SOURCE_DB=...   # database to back up (read-only for this tool)
export DRILL_DB=...    # EMPTY, non-production database
python -m app.db_tools export  --url-env SOURCE_DB --out /secure/path/drill.snapshot.json   # file mode 0600
python -m app.db_tools restore --url-env DRILL_DB  --in  /secure/path/drill.snapshot.json   # restores + verifies checksums
python -m app.db_tools verify  --url-env DRILL_DB  --in  /secure/path/drill.snapshot.json   # exit 0 only if every table matches
```

You can also verify a `pg_restore`d database against a snapshot taken at the
same moment, which proves the native dump is complete. Then start the API
against the restored database and run the restart check (§7) with the state
file from the source. The snapshot holds every stored record in plain JSON:
keep it private, delete it after the drill, and never commit it (`.gitignore`
excludes `*.snapshot.json`, `*.dump` and `*.sqlite3`).

## 7. Restart / redeploy survival check

```bash
python backend/scripts/persistence_check.py write  --base-url "$API" --state persist-state.json
# restart or redeploy the backend
python backend/scripts/persistence_check.py verify --state persist-state.json
```

`write` creates one synthetic elevated-risk observation (patient id
`PERSIST-CHECK-<epoch>`), which raises an alert, then acknowledges and resolves
it. `verify` checks that the same observation, alert status, timestamps and
audit row IDs are still there, and exits non-zero otherwise.

## 8. Verification performed (local, 2026-10-14)

Environment: macOS, Python 3.14.7, PostgreSQL 17.11 (disposable local cluster),
SQLite. **No hosted database was accessed.**

- `pytest backend/tests` with `VITALGUARD_TEST_POSTGRES_URL` set: **114 passed**.
  Without PostgreSQL: 99 passed, 15 skipped (the PostgreSQL variants).
- The concurrency tests passed in 5 of 5 repeated runs on PostgreSQL.
- Real uvicorn process restart: PostgreSQL ✔, SQLite file ✔, SQLite `:memory:`
  ✘ (expected negative control: "observation 1 missing", "alert 1 missing").
- `VITALGUARD_REQUIRE_POSTGRES=true` with SQLite: uvicorn exited with
  "Application startup failed".
- Database written by the deployed release (`phase-3-risk-engine` @ `dad2f95`) on
  PostgreSQL, then started with this release: migrations 2 and 3 applied,
  indexes created, alert timestamps backfilled, records intact. The old release
  then ran normally against the migrated database.
- Backup/restore on PostgreSQL: the logical snapshot restore verified;
  `pg_dump -Fc` → `pg_restore` matched the snapshot checksums for all four
  tables. The API on each restored database passed the restart check, and new
  inserts continued from id 2 without collisions.

## 9. Not yet verified (hosted)

- That the Render backend's `DATABASE_URL` points at the intended managed
  PostgreSQL instance. The live smoke test reports `postgresql`, but the
  instance itself was not inspected.
- Record survival across a **hosted** restart/redeploy. Run §7 against the
  hosted API after this change is deployed.
- A hosted backup/restore drill, which must target a separate, empty,
  non-production database.
- Setting `VITALGUARD_REQUIRE_POSTGRES=true` on the Render backend service.

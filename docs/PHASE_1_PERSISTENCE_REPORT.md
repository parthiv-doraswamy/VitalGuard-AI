# Phase 1 — Database persistence and migrations: report

**Date:** 2026-10-15 · **Branch:** `feature/phase-1-persistence` (from `origin/phase-3-risk-engine` @ `f85b280`) · **Target:** pull request into `phase-3-risk-engine` (not merged, not deployed)

> Synthetic-data demonstration only. Not clinically validated and not for clinical use.

## 1. Starting state (verified 2026-10-15)

| Item | Evidence |
| --- | --- |
| Backend deploy branch | `phase-3-risk-engine` @ `f85b280` (merge of PR #94). It already contains the persistence-hardening, outbox and push work (migrations v1–v6). |
| `main` vs backend branch | `git merge-base origin/main origin/phase-3-risk-engine` returns nothing (no common ancestor). Neither branch was modified. |
| Open PRs touching this area | #93 `phase-1-livebase-persistence-test` → `phase-3-risk-engine` (adds one SQLite reinitialisation test and a CI trigger for its own branch name; no storage code). #81 changes simulator alert behaviour (out of Phase 1 scope). Neither was modified. |
| **Live `/health`** (read-only GET, 2026-10-15) | `database.backend = postgresql`, `server_version = 18.6`, `durable_backend = true`, `schema_version = 6 / 6`, `postgres_required = false`; event broker `mode = postgres`, `listener_connected = true`; web push `configured = false`. |
| Hosted data across a redeploy (read-only) | Hosted observation #1 was created at `2026-10-14T07:24:49Z`, before PR #94 was merged (`2026-10-14T16:53:46Z`). That deploy migrated production from schema v1 to v6, and record #1 is still readable from a later process. This is evidence of survival across one real redeploy and migration, **not** a controlled restart test. |

**Acceptance criterion "active backend verified from the deployed health response": PASS.** The live backend uses PostgreSQL 18.6 at schema 6.

## 2. Root causes found

1. **Silent ephemeral SQLite on a hosted platform.** With no `DATABASE_URL`, `storage._database_url()` falls back to a SQLite file on the instance disk. Unless `VITALGUARD_REQUIRE_POSTGRES=true` is set (it is not), a hosted instance with a missing or deleted `DATABASE_URL` would run on storage that is wiped on restart, while `/health` still reported `status: ok`. Reproduced with `RENDER=true` and no `DATABASE_URL`: health returned `{status: ok, backend: sqlite, durable_backend: false}`.
2. **Unactionable startup failure on a malformed `DATABASE_URL`.** A typo (missing `:`), surrounding quotes from copy/paste, or a non-numeric port raised SQLAlchemy's raw `ArgumentError: Could not parse SQLAlchemy URL from given URL string`. No secret leaked, but the error did not say which setting was wrong or what format is expected.

No defects were found in transaction boundaries or migration ordering; the new tests below confirm the existing behaviour.

## 3. Changes (`backend/app/storage.py` plus tests and docs)

- `_backend_name()` parses the URL once, and turns parse failures into `StorageConfigurationError("DATABASE_URL could not be parsed. Expected postgresql://USER:PASSWORD@HOST:PORT/DBNAME … (the configured value is not shown)")`, raised `from None` so the value never appears in tracebacks.
- `hosted_platform()` returns `render` when `RENDER=true` (set by Render) or `configured` when `VITALGUARD_HOSTED=true`.
- With a hosted platform plus SQLite, startup logs `ERROR Storage misconfiguration: …`, and `/health` reports `database.status = degraded` (so the top-level status is `degraded`). The response includes `hosted_platform` and `warnings` naming the fix: set `DATABASE_URL`, verify `/health`, then set `VITALGUARD_REQUIRE_POSTGRES=true`. This **does not** block startup unless `VITALGUARD_REQUIRE_POSTGRES` is set, so behaviour is unchanged for the current, correctly configured deployment.
- A schema behind the application also produces an explicit warning (previously just `degraded`).
- `/health` adds two fields, `hosted_platform` and `warnings`. All existing fields are unchanged.

No schema change, no new migration, no change to alert, frontend, auth, push or ML behaviour.

## 4. Behaviour before and after

| Situation | Before | After |
| --- | --- | --- |
| Hosted (Render), `DATABASE_URL` missing, require flag off | Starts on ephemeral SQLite; health `ok` | Starts; logs ERROR; health `degraded` with an actionable warning |
| Hosted, `VITALGUARD_REQUIRE_POSTGRES=true`, no PostgreSQL | Refuses to start | Unchanged (refuses) |
| Hosted with PostgreSQL (current production) | Health `ok` | Health `ok`, `warnings: []`, `hosted_platform: render` |
| Malformed or quoted `DATABASE_URL` | Raw `ArgumentError`, no guidance | `StorageConfigurationError` with the expected format; value never shown |
| Database unreachable at startup | Startup fails | Unchanged |
| Database lost after startup | 503 `database_unavailable`; `/health` and `/health/ready` 503 | Unchanged (now tested) |
| Upgrade from schema v1–v5 | Upgraded (production went v1 → v6) | Unchanged; now tested from every version on both databases |

## 5. Tests

Added `backend/tests/test_phase1_persistence.py` (16 tests, 28 runs across SQLite and PostgreSQL):
- **Upgrade from every previous version 1–5 → 6.** Each historical schema is built from the pre-PR #94 v1 DDL plus the real migration steps, and seeded with version-appropriate synthetic data. The test checks that data is preserved, the alert timestamps are backfilled from v1/v2, a second startup is a no-op, and the upgraded database accepts new transactional writes.
- **Fresh initialisation** and repeated restarts with new engines.
- **Concurrent startup** of 6 independent engines (PostgreSQL advisory lock): each version is applied exactly once.
- **Persistence across connections and restart.** An observation, alert, audit records, outbox events and a stream session are read back through an independent connection pool, then through a restarted app.
- **Rollback.** A failure while queueing push deliveries leaves no observation, alert, audit or outbox rows. A failure writing a stream event leaves no observation, and the session's next sequence is unchanged.
- **Configuration.** Three malformed URL forms (the secret and host never appear, even in the traceback); hosted SQLite is reported as degraded; local SQLite is not flagged; hosted PostgreSQL is healthy; the require flag refuses hosted SQLite; a database lost after startup gives 503s with no secret in responses, while liveness stays 200.
- The configuration tests were also run against the **unfixed** `storage.py`: 5 of 6 failed there, and all pass with the fix.

Commands and results (2026-10-15, macOS, Python 3.12.12, disposable local PostgreSQL 17.11):

| Command | Result |
| --- | --- |
| `VITALGUARD_TEST_POSTGRES_URL=… VITALGUARD_TEST_REQUIRE_POSTGRES=true PYTHONPATH=backend pytest backend/tests -q` | **283 passed** |
| `PYTHONPATH=backend pytest backend/tests -q` (SQLite only, as CI without PostgreSQL) | 208 passed, 75 skipped (the PostgreSQL variants) |
| `PYTHONPATH=backend pytest ml/tests -q` | 46 passed |
| `pytest backend/tests/test_phase1_persistence.py` (SQLite + PostgreSQL) | 28 passed |

**Backup/restore drill on schema v6** (local disposable PostgreSQL 17 databases, never production): a source populated through the API (5 observations, 5 alerts, 6 audit rows, 1 stream session, 13 outbox events) was exported with `python -m app.db_tools export`. Restoring into an empty database verified every table checksum. `pg_dump -Fc` → `pg_restore` into another empty database matched the snapshot for all 8 tables. Restoring over a non-empty database was refused.

## 6. Acceptance criteria

| Criterion | Status |
| --- | --- |
| Active database backend verified from the deployed health response | **PASS**: PostgreSQL 18.6, schema 6/6 |
| PostgreSQL selected when intended; SQLite not silently used when hosted | **PASS** in code and tests. Production uses PostgreSQL. Hosted SQLite is now loud (ERROR log and `degraded`) and is refused when `VITALGUARD_REQUIRE_POSTGRES=true`. |
| Migrations safely upgrade supported schemas without data loss | **PASS** (v1–v5 → v6 on SQLite and PostgreSQL 17; production itself upgraded v1 → v6 on 18.6 without loss) |
| Related records persist transactionally; failures return honest errors | **PASS** (tests above) |
| Tests cover migration, rollback, persistence, database-unavailable behaviour | **PASS** |
| Restart durability and backup/restore verified or marked blocked | **Partial.** Backup/restore was verified locally on schema v6 (non-production). Hosted survival across one redeploy is shown by read-only evidence. A **controlled hosted restart test and a hosted backup/restore drill are BLOCKED**: there is no Render API/dashboard access in this session, and the database network is private (by design). |
| No production data deleted or reset; no secrets committed or exposed | **PASS**: only read-only GET requests were made to production; the diff contains no credentials |

## 7. Not verified / follow-ups

- No local PostgreSQL 18 run. A local PostgreSQL 18 install was declined, so tests ran on 17.11; production on 18.6 has already applied migrations 1–6.
- Controlled restart of the hosted backend with a marked synthetic record, and a hosted backup/restore into a separate empty database (needs Render access; never restore over production).
- `VITALGUARD_REQUIRE_POSTGRES=true` is now justified by the verified health response. **Recommended**, but it is a Render environment change for the owner to make after this PR is reviewed. It was not changed here.
- PR #93's SQLite reinitialisation test overlaps with the persistence tests here. It is harmless; consider closing it or merging it separately. Its CI trigger change only adds its own branch name.
- No deployment occurred.

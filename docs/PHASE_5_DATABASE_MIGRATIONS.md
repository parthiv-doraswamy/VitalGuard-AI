# Phase 5 — Durable Database and Migrations

**Status:** Migration implementation in progress. Managed PostgreSQL provisioning/configuration, live persistence verification, and backup/restore evidence are still outstanding.

## Current implementation

- SQLAlchemy storage selects `DATABASE_URL` when present and supports PostgreSQL through `psycopg`; otherwise it falls back to SQLite for local/test demo use.
- `backend/app/migrations.py` applies ordered migration versions and records them in `schema_migrations`.
- Version 1 establishes the existing synthetic demo tables: observations, patients, alerts and audit events.
- Version 2 adds `idx_alerts_patient_status_created` for patient alert worklist filtering.
- The migration runner is idempotent for repeated startup and upgrades a database that has the previous version-1 ledger.
- Tests cover fresh initialization, repeat application, v1-to-v2 upgrade, required tables/indexes and SQLite health.

## Deployment status and required operator action

A hosted PostgreSQL database has **not** been provisioned or confirmed for this project. Do not assume the service is using PostgreSQL: the health endpoint reports the active database dialect.

Before switching the deployed service:
1. Provision a managed PostgreSQL instance in the intended private environment and confirm its cost/plan with the project owner.
2. Set the backend's `DATABASE_URL` privately in Render; never commit it or expose it to the browser.
3. Deploy and confirm `/health` reports `database.backend = postgresql`.
4. Create a synthetic observation, restart/redeploy, and confirm it persists.
5. Configure backups and retention, then perform a restore drill and record measured recovery time/data loss.
6. Decide whether existing SQLite demo records should be discarded or explicitly migrated. Never automatically promote them to real-patient records.

## Limitations

- SQLite remains the test/local fallback; its local filesystem is not a substitute for durable managed storage on an ephemeral host.
- The migration runner is a small SQLAlchemy version ledger, not Alembic. Migration changes must be append-only and tested against both SQLite and PostgreSQL before production use.
- This schema and demo are synthetic-only. No real patient data, clinical use, or clinical readiness is authorized by this phase.
- Retention, deletion, encryption-at-rest verification, backup schedule, restore objectives and managed database credentials remain release gates.

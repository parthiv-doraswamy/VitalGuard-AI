# Phase 2 — Durable storage foundation

## Implemented in this phase branch

- Versioned schema ledger in `schema_migrations`.
- Existing observation/prediction table remains supported.
- Additional durable tables for patient metadata, alerts, and audit events.
- Startup schema initialization and a database connectivity check at `GET /health`.
- SQLite remains the local/test default; PostgreSQL is selected by private `DATABASE_URL`.
- Automated tests verify idempotent schema initialization and database health.

## Hosted Render setup

1. Provision a PostgreSQL database in the same Render workspace and region as the backend.
2. Copy its **internal** connection string from the database dashboard.
3. In the backend service's Environment settings, add `DATABASE_URL` with that connection string. Never commit it or expose it in frontend variables.
4. Deploy this phase branch to a staging service first, then inspect `GET /health` for `database.backend = postgresql`.
5. Submit a synthetic demo observation and confirm it appears in `GET /api/v1/observations`.
6. Restart/redeploy the backend and confirm the observation remains.
7. Keep backups and restore procedures documented before storing any sensitive data.

Do not set `DATABASE_URL` to an expired or public URL. Render PostgreSQL plan/retention varies; verify the current plan and expiration terms in the dashboard before provisioning.

## Current limits

- Patient, alert, and audit tables are schema foundations; this phase does not yet provide a full CRUD/alert workflow.
- The migration ledger is intentionally minimal for this prototype. Use Alembic for more complex production schema evolution.
- SQLite files on ephemeral hosts are not durable across redeploys; durable hosted PostgreSQL must be configured to meet the persistence acceptance criteria.
- This is a synthetic demo, not a clinical record system.

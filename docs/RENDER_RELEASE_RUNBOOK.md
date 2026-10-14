# Render release runbook

## Current Render services

- Frontend static site: `https://vitalguard-ai-g215.onrender.com`
  - Service ID: `srv-db56ekijnfac739dg5d0`
  - Repository branch: `main`
  - Build: `npm ci && npm run build`
  - Publish directory: `dist`
- Backend FastAPI service: `https://vitalguard-risk-api.onrender.com`
  - Service ID: `srv-db56gvm7bikc7394de0g`
  - Repository branch: `phase-3-risk-engine`
  - Build: `pip install -r backend/requirements.txt`
  - Start: `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`

## Coordinated release steps

1. Merge frontend work to `main`; merge backend work to `phase-3-risk-engine` when the API changes.
2. Wait until the matching Render deploy shows **Live** for the expected commit SHA. The API and UI may deploy at different times.
3. Check `/health` and `/api/v1/model/info`.
4. Run GitHub Actions → **Live API smoke test** → Run workflow. Do not interpret an earlier smoke failure as a code regression until confirming whether the required backend commit was deployed.
5. Open the frontend, check the live channel, alert inbox, data quality, history and Settings model panels.
6. Inspect Render logs if the deploy fails; do not report deployment complete based only on a GitHub merge.
7. After a backend deploy that touches storage, confirm `/health` → `database.backend = postgresql`, `durable_backend = true`, and `schema_version = latest_schema_version`. Then run `python backend/scripts/persistence_check.py write`, restart the backend service, and run `verify` with the same state file.

## Persistence settings (backend service, private environment)

- `DATABASE_URL`: the managed PostgreSQL **internal** connection string. Never commit it or put it in a `VITE_` variable.
- `VITALGUARD_REQUIRE_POSTGRES=true`: makes the service fail to start rather than fall back to ephemeral SQLite. Set it only after confirming `DATABASE_URL` is correct, because a wrong value will block the deploy.
- Backup/restore drills target a separate, empty, non-production database. Do not open the database to `0.0.0.0/0`.

The live smoke workflow is intentionally manual for release verification so it does not race the separately deployed backend whenever frontend files change.

## Current limitations

- Hosted PostgreSQL is not confirmed configured. SQLite remains the backend default unless `DATABASE_URL` is set. A local SQLite file on a hosted ephemeral filesystem is not durable across all redeploy/restart scenarios.
- The current WebSocket event hub is in-process and single-instance.
- The frontend still has local synthetic cohort data alongside backend-backed alerts and history.
- The public demo has no authenticated identity or role-based access control.
- Never use real patient data. This is not for clinical use.

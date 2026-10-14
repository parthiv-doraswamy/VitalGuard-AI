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
3. Check `/health` and `/api/v1/model/info`. The health response must report database status `ok` and identify the backend type.
4. Run GitHub Actions → **Live API smoke test** → Run workflow. Keep the expected database backend set to `postgresql` for a release verification. Choose `sqlite` only for an intentional temporary/local demo. Do not interpret an earlier smoke failure as a code regression until confirming whether the required backend commit was deployed.
5. Open the frontend, check the live channel, alert inbox, data quality, history and Settings model panels.
6. Inspect Render logs if the deploy fails; do not report deployment complete based only on a GitHub merge.

The live smoke workflow is intentionally manual for release verification so it does not race the separately deployed backend whenever frontend files change.

## Current limitations

- A Render PostgreSQL instance named `vitalguard-postgres` exists (free plan, currently scheduled to expire 2026-11-10), but its use by the backend is not yet verified. The backend uses SQLite unless `DATABASE_URL` is set. Set `DATABASE_URL` on the backend service to the database's **internal** connection URL in the Render Dashboard; do not put the URL in source control or frontend variables. Then redeploy and run the live smoke workflow with expected backend `postgresql`. The external database query tool could not connect because the database IP allowlist is empty; do not open it broadly just to enable that tool.
- The current WebSocket event hub is in-process and single-instance.
- The frontend still has local synthetic cohort data alongside backend-backed alerts and history.
- The public demo has no authenticated identity or role-based access control.
- Never use real patient data. This is not for clinical use.

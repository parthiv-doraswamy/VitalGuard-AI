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

The live smoke workflow is intentionally manual for release verification so it does not race the separately deployed backend whenever frontend files change.

## Current limitations

- Hosted PostgreSQL is not confirmed configured. SQLite remains the backend default unless `DATABASE_URL` is set. A local SQLite file on a hosted ephemeral filesystem is not durable across all redeploy/restart scenarios.
- The current WebSocket event hub is in-process and single-instance.
- The frontend still has local synthetic cohort data alongside backend-backed alerts and history.
- The public demo has no authenticated identity or role-based access control.
- Never use real patient data. This is not for clinical use.

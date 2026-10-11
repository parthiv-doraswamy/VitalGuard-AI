# Phase 16 — Authenticated release smoke tests

## Changes

- Live API smoke tests now authenticate through `POST /api/v1/auth/login` and send the short-lived bearer token to protected endpoints.
- The workflow is manual-only so a source push cannot accidentally hit a backend deployment that has not yet been updated.
- GitHub Actions secrets `VITALGUARD_SMOKE_USERNAME` and `VITALGUARD_SMOKE_PASSWORD` are required; they must match the operator credentials configured in Render. Never commit credentials to the repository or print the token in logs.
- The release runbook now calls out backend branch drift and requires checking the deployed commit before interpreting smoke results.

## Release sequence

1. Confirm Render is configured to deploy the intended backend branch and the deployment is Live.
2. Confirm the Render deployment commit contains the expected API routes/migrations.
3. Add the smoke username and password as repository Actions secrets.
4. Run **Actions → Live API smoke test → Run workflow**.
5. Review output for health, login, model metadata, synthetic prediction, persistence/history, data quality, alert lifecycle/audit, timeline and validation gates.

## Limitations

- A successful smoke run verifies only the tested deployed demo paths; it does not establish clinical validity or production security.
- The test creates synthetic records with `SMOKE-` identifiers.
- Database persistence across deploy/restart still requires separate hosted PostgreSQL verification.

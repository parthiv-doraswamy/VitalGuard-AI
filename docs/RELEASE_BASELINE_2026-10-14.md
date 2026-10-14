# Release Baseline — 2026-10-14

## Purpose

Record the verified starting point for the VitalGuard AI hackathon-readiness work before further implementation. This is a synthetic-data demonstration only, not a clinical system.

## Repository safety

- Repository: https://github.com/parthiv-doraswamy/VitalGuard-AI
- Default/release branch: `main`
- Main frontend release commit observed in Render: `e140d1b6b4ba5e9c99c5b2440b72ddb403ba8e47` — “Add demo role quick login”.
- Existing safety branches confirmed in GitHub:
  - `backup/pre-restore-main-2026-10-14`
  - `backup/pre-restore-backend-2026-10-14`
- No application code was changed as part of this baseline record. This document is being prepared on `phase-1-release-baseline`, not directly on `main`.

## Render services observed

| Service | URL | Configured branch | Latest observed deploy | Result |
|---|---|---|---|---|
| Frontend static site `vitalguard-ai` | https://vitalguard-ai-g215.onrender.com | `main` | `e140d1b6b4ba5e9c99c5b2440b72ddb403ba8e47` | Render reports Live; build and deploy events succeeded on 2026-10-14. |
| Backend API `vitalguard-risk-api` | https://vitalguard-risk-api.onrender.com | `phase-3-risk-engine` | `9cb83bde68148586adb6edcad8e5cd4b811a2353` | Render reports Live; deploy event succeeded on 2026-10-14. |
| Login preview `vitalguard-login-preview` | https://vitalguard-login-preview.onrender.com | `feature/demo-role-login-clean` | `81507b1c6ef7fc90875a20ee33985248b9a18e8d` | Separate preview service is Live; main frontend is also on the newer login commit. |

Frontend and backend intentionally deploy from different branches per `docs/RENDER_RELEASE_RUNBOOK.md`. Treat them as a coordinated release pair and verify compatibility before merging API changes.

## Verification evidence

### Verified

- Render frontend build completed successfully for the current `main` commit. Build output includes a warning that a minified JavaScript chunk exceeds 500 kB; this is a performance/polish item, not a failed build.
- Render backend is reported Live.
- Recent backend Render logs show `GET /health` and `GET /api/v1/model/info` returning HTTP 200.
- Recent backend logs show successful requests for model evaluation, prediction/explanation, observation history/trends/quality, alert acknowledgement/resolution, audit history, and patient timeline. Some negative-case requests correctly returned 422.
- Local backend tests from the uploaded repository snapshot: `PYTHONPATH=backend python -m pytest backend/tests -q` — **17 passed**.
- Backup branches listed above are present.

### Not yet verified / blocked

- Local frontend `npm ci` did not finish within the available 120-second execution window. The subsequent local lint attempt failed because the interrupted install left `vite/client` and `vitest/globals` type definitions unavailable. This is an incomplete local environment, **not evidence of a source-code test failure**.
- A current GitHub Actions run summary for the exact release commit was not available through the checks queried in this baseline.
- Direct browser/HTTP verification of the public URLs could not be completed from this execution environment. Render service state and logs are used as evidence instead; a human browser check remains required.
- Hosted PostgreSQL configuration and persistence across restart/redeploy remain unconfirmed. Do not claim durable hosted persistence until the backend's database configuration is verified without exposing its secret value and a write/read/restart test passes.
- End-to-end browser behavior has not been independently exercised in this baseline.

## Current release risks

1. The frontend deploys from `main`; the backend deploys from `phase-3-risk-engine`. API changes must be coordinated across both branches.
2. Login is a demo persona selector; do not describe it as real authentication or security enforcement.
3. The README documents local synthetic fixtures alongside backend-backed history/alerts/timeline. These sources must be visibly distinguished in the UI.
4. The backend WebSocket event hub is in-process and single-instance.
5. Risk-model and NEWS2 outputs are demonstrations using synthetic data and are not clinically validated.
6. The frontend build has a large-chunk warning.

## Next actions

1. Run or retrieve the current GitHub Actions frontend/backend results for the release commit.
2. Complete a real browser smoke check of the frontend login, dashboard, patient timeline and alert workflow.
3. Verify database configuration and persistence behavior before changing storage or deployment settings.
4. Continue with the golden end-to-end synthetic scenario on a dedicated working branch; keep `main` protected until changes are tested and reviewed.

## Safety statement

Use fictional patient IDs and synthetic observations only. Do not use this prototype to diagnose, triage, or make treatment decisions.

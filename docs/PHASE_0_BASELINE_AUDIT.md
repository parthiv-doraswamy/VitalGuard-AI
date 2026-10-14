# VitalGuard AI — Phase 0 Baseline Audit

**Audit date:** 2026-10-14  
**Status:** Phase 0 source/configuration audit completed; runtime and database verification partially blocked.  
**Purpose:** Establish a factual baseline for Claude Code before Phase 1. This file is an audit, not evidence that the full product workflow is production-ready.

> **Safety boundary:** VitalGuard AI is a synthetic-data demonstration, not clinically validated and not for clinical use. Do not enter real patient data or use it for diagnosis, triage, or treatment decisions.

## 1. Repository and deployment baseline

Repository: [parthiv-doraswamy/VitalGuard-AI](https://github.com/parthiv-doraswamy/VitalGuard-AI)

| Component | Verified configuration at audit time |
| --- | --- |
| Default/main source | `main` |
| Latest observed `main` commit | `66dffb9668afb2dd9fc326b9b2f7458331eb5c5e` — merge PR #96, backend feature stack into main |
| Frontend | [https://vitalguard-ai-g215.onrender.com](https://vitalguard-ai-g215.onrender.com) |
| Frontend Render service | `srv-db56ekijnfac739dg5d0`, branch `main`, auto-deploy on commit |
| Frontend live deployment | `66dffb9668afb2dd9fc326b9b2f7458331eb5c5e`; Render reports status `live` |
| Backend | [https://vitalguard-risk-api.onrender.com](https://vitalguard-risk-api.onrender.com) |
| Backend Render service | `srv-db56gvm7bikc7394de0g`, branch `phase-3-risk-engine`, auto-deploy on commit |
| Backend live deployment | `f85b2808396545cc1220dea4dd90132c5571dc38`; Render reports status `live` |
| Hosted database resource | `vitalguard-postgres`, PostgreSQL 18, resource `dpg-db5mdtqd0e5s73fvh9gg-a`, status `available`, free plan expiration shown as 2026-11-10 |

### Critical branch warning

GitHub's compare API returned **“No common ancestor between main and phase-3-risk-engine.”** Do not merge, rebase, reset, force-push, or synchronize these branches blindly. They currently serve different deployment roles. Any backend change must be developed and reviewed against the actual backend deployment branch and tested before release. Keep both existing production branches intact.

The Render frontend build log for the live deployment reports a successful Vite/PWA build and “Your site is live.” Recent backend logs show successful HTTP 200 responses for API requests including alerts, model metadata/evaluation, observations and live-demo session status, and an accepted WebSocket connection. These log entries are not a full end-to-end test.

## 2. Audit scope and evidence limits

Reviewed remotely:
- GitHub branch refs and recent commit history.
- Render service configuration and recent deployment metadata.
- Render application logs for the current deployment window.
- `README.md`, `docs/REALTIME_DEMO_ROADMAP.md`, `docs/RENDER_RELEASE_RUNBOOK.md`.
- `backend/app/main.py`, `backend/app/storage.py`, `backend/app/migrations.py`, `backend/app/simulator_routes.py`, `backend/app/stream_service.py`, `backend/app/observation_service.py`, `backend/app/alert_routes.py`, `backend/app/notification_routes.py`.
- `src/store/SimulationContext.tsx`, `src/pages/AlertsPage.tsx`, `src/components/alerts/BackendAlertInbox.tsx`, `package.json` and `.github/workflows/ci.yml`.

Not verified during this audit:
- Local test suites were **not run**; this was a remote source/configuration audit, not a checked-out local test run.
- A fresh live `/health` response could not be retrieved through the available web/runtime route in this audit.
- Direct read-only SQL against Render PostgreSQL was blocked because its IP allowlist is empty. Do **not** open it broadly just to make this audit pass.
- The Render environment variable values/presence could not be independently inspected here. Never expose secret values.
- A controlled hosted restart/redeploy persistence test and a hosted backup/restore drill were not performed.
- No current full browser end-to-end run was performed as part of Phase 0.

The GitHub combined-status endpoint returned no status entries for the two observed live commits. That is not proof of failure or success. The repository does define CI; run it during implementation.

## 3. Current technical architecture

### Backend and storage
- FastAPI app version in `backend/app/main.py` is `0.8.0`.
- App startup calls `initialize_storage()`, loads the active model, starts the event broker and starts the notification worker.
- `backend/app/storage.py` uses SQLAlchemy and supports PostgreSQL via private `DATABASE_URL`; otherwise it defaults to local SQLite. `VITALGUARD_REQUIRE_POSTGRES=true` can make startup refuse non-PostgreSQL storage.
- `backend/app/migrations.py` defines migrations through schema version **6**.
- The existence/availability of a hosted PostgreSQL resource does not prove the deployed backend is using it. The active runtime selection, current schema and restart durability must be verified.
- Documentation is inconsistent: the README and Render runbook say hosted PostgreSQL is not confirmed, while a later roadmap entry says a live health check reported PostgreSQL active. Resolve this by checking the current deployed `/health` response and performing a safe persistence test; do not rely on either stale statement alone.

### Producer, observations and event delivery
- The deterministic simulator supports stable, worsening and recovering synthetic scenarios.
- `POST /api/v1/demo/observations` in `backend/app/simulator_routes.py` calls `record_observation(..., raise_alert=False)`. This legacy one-observation endpoint persists a score but deliberately does **not** create an alert.
- The dedicated stream path in `backend/app/stream_service.py` calls `persist_observation(..., True, ...)`, so it can create a threshold alert. It also has a producer session token, sequence idempotency, and an optional `VITALGUARD_STREAM_PRODUCER_KEY`.
- Do not assume the legacy simulator endpoint and the live stream path have equivalent alert behavior. Phase 1 should not change alert behavior unless needed for storage correctness; the later alert phase must deliberately unify the workflow.
- The event broker/outbox and stream session code exist in the repository. However, the README describes WebSocket fan-out as in-process/single-instance, while later roadmap sections describe PostgreSQL outbox/notification behavior. Verify the deployed broker's actual cross-instance status before claiming scale-out support.

### Alerts and frontend consistency
- `src/store/SimulationContext.tsx` maintains local synthetic patient state, generates local alerts and persists local alert state in `localStorage` under `vg-alerts`.
- `src/pages/AlertsPage.tsx` renders both `BackendAlertInbox` and a separate local alert list/counts. The backend inbox reads persisted API alerts, while the page's other cards/tabs use local demo alerts. This is a confirmed source of duplicate-looking and inconsistent alert views.
- `backend/app/alert_routes.py` exposes list, acknowledge, resolve and audit routes. The current code shown here does not enforce staff identity or role-based access; the actor field defaults to `demo-operator`.
- Phase 1 should preserve existing alert data and focus on storage. Consolidating alert sources belongs in later workflow phases.

### Authentication and notifications
- `docs/WEB_PUSH.md` states that the deployed backend has no user accounts or staff roles; the demo login is client-side. Push subscriptions are device-scoped and use management tokens, not doctor identity.
- Some endpoints use capability tokens (producer/session or subscription tokens), but that is not equivalent to full staff authentication and role-based authorization.
- Push support exists in source. Actual VAPID configuration and current physical-device delivery were not independently verified in this audit. Do not claim phone delivery from a queued/accepted status alone.
- Do not expose patient identifiers, vitals, secrets or free-text patient data in logs or lock-screen push payloads.

### ML
- The active model is a synthetic-data Logistic Regression baseline using generated observations and heuristic labels.
- Evaluation metrics describe agreement with synthetic labels, not clinical performance.
- Coefficient contributions are not SHAP values or causal explanations.
- The source includes model evaluation/registry support, but no approved clinical dataset or clinically validated model was verified. Keep the synthetic model as fallback and label all outputs as demo-only.

## 4. CI and verification entry points

The current `.github/workflows/ci.yml` defines:
- Frontend: `npm ci`, `npm run lint`, `npm test`, `npm run build`, `npm run verify:pwa`.
- Backend: install `backend/requirements.txt`, then `PYTHONPATH=backend pytest backend/tests -q`.
- Workflow triggers on pushes and pull requests targeting `main` and `phase-3-risk-engine`.

The README also documents `npm run smoke:api`; it writes synthetic records to the configured demo database. Only run it against an intended demo/test environment or after confirming the write effects. Do not send real patient data.

## 5. Phase 0 findings and priority

| Priority | Finding | Evidence / implication |
| --- | --- | --- |
| P0 | Main and deployed backend branches have no common ancestor according to GitHub compare | Highest risk for branch/merge mistakes. Preserve both and avoid blind synchronization. |
| P0 | Active hosted database selection and durability are not independently verified | PostgreSQL exists, but SQL inspection was blocked; SQLite remains the code default when `DATABASE_URL` is absent. |
| P1 | Documentation disagrees about live PostgreSQL status | README/runbook and roadmap conflict; verify current runtime rather than trusting stale documentation. |
| P1 | Local and backend alert views are separate | Alerts page renders both sources and calculates local counts separately, explaining inconsistent/duplicate-looking inbox content. |
| P1 | Legacy observation endpoint explicitly suppresses alerts | `/api/v1/demo/observations` uses `raise_alert=False`; dedicated live stream uses alert evaluation. |
| P1 | No server-side staff identity/RBAC | Public demo is not suitable for real patient data or production clinical use. |
| P1 | Cross-instance event delivery claims need live verification | README and roadmap differ; test before claiming horizontal scalability. |
| P2 | Push readiness/device delivery is not confirmed here | VAPID presence and actual delivery need a controlled check. |
| P2 | Full current test and browser E2E suite was not run during this audit | Existing CI definitions are present; run them for each implementation phase. |

## 6. Required Phase 1 — Database persistence and migration plan

**Do this next; do not start the UI redesign, alert rewrite or ML training before completing the database foundation.**

1. Work from a new feature branch based on the **backend deployment branch** `phase-3-risk-engine` for backend changes. Do not commit directly to that live auto-deploy branch. Do not merge `main` into it.
2. Verify the exact deployed backend commit and current `/health` output. Confirm the reported database backend, durability flag, schema version and event-broker status.
3. Verify whether the backend service has `DATABASE_URL` configured without exposing its value. If it is absent or points to the wrong database, document the fix required; do not change secrets blindly.
4. Use a disposable/local test database first. Inspect existing data and migration behavior before any hosted migration.
5. Review migration history and ensure all six current migration steps are repeatable and compatible with the deployed database schema.
6. Add or update tests for migration upgrades, legacy schema compatibility, transaction rollback, concurrent startup, observation persistence and database failure handling.
7. If hosted persistence needs to be tested, use a clearly identified synthetic record and a reviewed non-destructive procedure. Verify the same record after a controlled restart only when safe. Do not reset production data.
8. Keep the Render PostgreSQL network private. Do not add a broad public IP allowlist to enable an external SQL tool.
9. Perform backup/restore against a separate non-production database; never restore over production as part of Phase 1.
10. Do not set `VITALGUARD_REQUIRE_POSTGRES=true` until the correct `DATABASE_URL` and successful PostgreSQL connection have been verified.
11. Run backend tests, frontend CI where affected, and the appropriate persistence smoke checks. Report actual output and limitations.
12. Open a reviewed pull request targeting `phase-3-risk-engine`. Because this branch auto-deploys, do not merge/deploy until the changes and migration plan are reviewed.

### Phase 1 acceptance criteria
- The active database backend is verified from the deployed health response.
- Hosted PostgreSQL is selected when intended, and SQLite is not silently used in the hosted environment when PostgreSQL is required.
- Current migrations can safely upgrade the supported schema without losing existing data.
- Observations and related records persist transactionally; failures return honest errors, not fake success.
- Tests cover migration, rollback, persistence and database-unavailable behavior.
- Restart durability and backup/restore are either verified in a safe environment or explicitly marked blocked.
- No production data was deleted or reset; no secrets were committed or exposed.

## 7. Rules for the next Claude Code session

- Read this file and `docs/RENDER_RELEASE_RUNBOOK.md` before editing.
- Re-check the live commit/branch mapping because deployments can change after this audit.
- Implement **Phase 1 only**. Do not proceed to Phase 2 until Phase 1 acceptance criteria are reported PASS or clearly BLOCKED.
- Preserve `main` and the deployed backend branch. Use a feature branch and a pull request.
- Do not blindly merge the unrelated branch histories.
- Do not claim tests, runtime status, persistence durability, notification delivery or deployment unless verified.
- Keep all data synthetic and keep the not-for-clinical-use disclaimer.

# VitalGuard AI — Delivery roadmap and verified scope

> Synthetic data only. This is a software prototype, not a clinically validated medical device or clinical decision-support system.

## Delivered phases

### Phase 1 — Synthetic observation ingestion
- Deterministic stable, worsening, and recovering fictional scenarios.
- Validated ingestion endpoint: `POST /api/v1/demo/observations`.
- Persists the generated observation and synthetic model result.

### Phase 2 — Storage adapter
- SQLAlchemy adapter supports local SQLite and PostgreSQL via private `DATABASE_URL`.
- Schema creation/migration helpers and history indexes.
- **Hosted status (2026-10-14):** the live `/health` smoke check reports PostgreSQL as the active backend. This confirms runtime backend selection/reachability, but not survival across restart/redeploy or a tested backup/restore.

### Phase 3 — Live event delivery
- WebSocket endpoint: `/api/v1/live`.
- Observation and alert events broadcast after persistence.
- Frontend connection state, heartbeat and reconnect backoff.
- The event hub is in-process and intended for a single backend instance.

### Phase 4 — Alert lifecycle
- Persistent synthetic alerts with deduplication keys.
- Open, acknowledged and resolved states.
- Audit trail for creation and state transitions.

### Phase 5 — Live dashboard alert operations
- Backend alert inbox in Alert Center.
- Refresh, status filters, acknowledge and resolve controls.
- Connection state visible in the app shell.

### Phase 6 — Observation data quality
- `GET /api/v1/observations/quality` classifies recent records as fresh, stale, incomplete or unknown.
- Dashboard panel displays observation age and missing required fields.
- Scope is limited to a bounded history page; it cannot detect devices that never sent a reading.

### Phase 7 — Model evaluation transparency
- `GET /api/v1/model/evaluation` returns deterministic stratified synthetic holdout metrics and a confusion matrix.
- `POST /api/v1/risk/explain` returns standardized logistic-regression coefficient contributions.
- These metrics only measure agreement with generated heuristic labels. Contributions are not SHAP or causal explanations.

### Phase 8 — Explainability workbench
- Settings form sends fictional vitals to the contribution endpoint without saving a prediction.
- Displays the synthetic score and signed coefficient contributions.

### Phase 9 — Persisted history UI
- Dashboard shows recent backend predictions, model versions, timestamps, scores and a patient filter.

### Phase 10 — Release smoke checks
- `npm run smoke:api` exercises health, model metadata, CORS, prediction persistence, synthetic evaluation, explanations, quality status, NEWS2 demo scoring, alert lifecycle/audit, and the unified timeline.

### Phase 14 — NEWS2 scoring demonstration
- `POST /api/v1/scores/news2` returns parameter points for respiratory rate, SpO₂, systolic blood pressure, pulse, consciousness, temperature and supplemental oxygen.
- SpO₂ Scale 2 is restricted by an explicit authorization assertion and defaults off.
- Based on the RCP NEWS2 chart, but the software implementation is not clinically validated or approved.

### Phase 15 — NEWS2 UI workbench
- Settings contains a synthetic-input calculator showing parameter points and total.
- Scale 2 submissions are blocked until acknowledgement is checked; the checkbox is not proof of authorization.

### Phase 16–17 — NEWS2 verification
- Live API smoke test covers default scoring and the Scale 2 API gate.
- Frontend regression tests cover score rendering and the UI acknowledgement gate.

### Phase 18–19 — Maintenance and request reliability
- Weekly Dependabot updates configured for npm and Python packages.
- Alert inbox avoids unnecessary CORS preflights on GET requests.

### Phase 20 — Unified patient timeline API
- `GET /api/v1/patients/{patient_id}/timeline` combines persisted synthetic observations, alerts and alert audit events.

### Phase 21 — End-to-end workflow smoke
- Live smoke verifies prediction → persistent alert → acknowledge → resolve → audit → unified timeline.

### Phase 22 — Patient detail timeline
- Patient detail includes backend timeline events, with clear distinction from local synthetic fixtures.

### Phase 23 — Descriptive observation trends
- `GET /api/v1/observations/trends?patient_id=...` summarizes persisted series with OLS slope and insufficient-data states.
- This is descriptive history, not a forecast or clinical inference.

### Phase 24 — Trend UI
- Patient detail displays first/latest values, change and direction for backend observations.

### Phase 25–27 — Release workflow and integration
- CI runs for pull requests targeting both `main` and `phase-3-risk-engine`.
- Smoke tests cover the trend endpoint and insufficient-history state.
- Patient detail combines timeline and trend panels.

### Phase 28–31 — Integration hardening
- Continued integration and release checks across the dashboard, backend-backed history and alert workflows.
- Changes are covered by the repository's current frontend/backend CI and live API smoke workflow; consult the linked workflow runs for the exact commit tested.

### Phase 32 — Patient navigation regression
- Patient-detail Back navigation remains usable when decorative overlays are present; overlay hit-testing no longer blocks the link.

### Phase 33 — Protected-route browser coverage
- Browser end-to-end coverage authenticates the demo Admin before asserting protected-route behavior.

### Phase 34 — Browser test reliability
- Removed TypeScript-only syntax from the JavaScript Playwright test so the E2E runner can parse the test file reliably.

### Phase 35–40 — API release and CORS regression coverage
- Backend CORS preflight permits the frontend origin and the `Accept`, `Authorization`, and `Content-Type` headers.
- Live API smoke explicitly sends an authorization/content-type preflight and asserts both headers are allowed.
- Latest verified main commit for this coverage: `e1a0a2b18fbc2f418fa4b25631c331cc389d7e6a`.
- Latest verified CI run: [Validate VitalGuard AI](https://github.com/parthiv-doraswamy/VitalGuard-AI/actions/runs/38550484939) — success.
- Latest verified live API smoke: [Live API smoke test](https://github.com/parthiv-doraswamy/VitalGuard-AI/actions/runs/38550484982) — success. This confirms the tested live API behavior at the time of that run, not PostgreSQL durability.

### Phase 41 — Hosted persistence readiness (open)
- Verify the backend Render service uses the private PostgreSQL connection string through its `DATABASE_URL` environment variable.
- Run a synthetic observation workflow, confirm the record is available from history/timeline, then verify it survives a backend restart or redeploy.
- Do not claim hosted persistence complete until the database target and survival test are both verified.
- The live API smoke now reports PostgreSQL as active. Direct SQL verification through the hosted Render connector is blocked because the database has no external IP allowlist entry; do not open it broadly to `0.0.0.0/0`. Restart/redeploy survival remains unverified.

### Phase 42 — Roadmap reconciliation
- Documented integration hardening, patient navigation, protected-route browser coverage, test reliability and CORS/live-smoke work.
- Verified CI and live API smoke run links are recorded; hosted PostgreSQL durability remains an explicit open gate.

### Phase 43 — Persistence diagnostics in live smoke tests
- Live smoke asserts that health reports a reachable database and identifies its backend as SQLite or PostgreSQL.
- SQLite deployments produce a clear warning that hosted restart/redeploy durability is not established.
- PostgreSQL being active is reported as a configuration check only; restart/redeploy survival must still be tested independently.
- This diagnostic intentionally warns rather than failing the entire demo smoke while the known hosted PostgreSQL configuration remains outstanding.

### Phase 44 — API security-header regression coverage
- Live API smoke checks `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and `Cache-Control` values on an API response.
- The smoke test also requires a server-generated `X-Request-ID` for basic request correlation.
- These checks validate baseline headers only; they do not replace a security review or authentication/authorization controls.

## Remaining work before any real-world use

1. Verify that the active managed PostgreSQL connection survives a controlled backend restart/redeploy using the same synthetic record ID; define and test retention, backup, restore, and migration procedures. Do not widen database network access to work around restricted external SQL access.
2. Implement proper identity and role-based authorization before any sensitive or multi-user workflow. The current demo actor is not authentication.
3. Add durable cross-instance event delivery if scaling beyond one backend instance.
4. Remediate outstanding dependency advisories in controlled batches, then add production-grade observability, request limits, security review, and operational incident procedures.
5. Keep local synthetic patient lists/charts/analytics visibly separate from backend-persisted observations. Not all dashboard views consume the backend API.
6. Do not claim clinical NEWS2 compliance, SHAP, clinical accuracy, or patient deterioration prediction until independently verified against reviewed specifications and evaluated on appropriately authorized, representative data with suitable governance.

## Safety boundary

Never use real patient data. Missing or stale observations are unknown, not normal. Synthetic model metrics do not establish clinical performance, calibration, or safety. This prototype must not be used for diagnosis, triage, or treatment decisions.


### Phase 45 — Persistence status reconciliation
- Updated the roadmap to reflect the latest successful live API smoke: PostgreSQL is reported as the active backend.
- This is not a durability claim. The same synthetic record must still be queried after a controlled restart/redeploy before persistence readiness can be marked complete.
- External SQL inspection remains blocked by the database network policy; keep the database private rather than adding a broad allowlist.

# VitalGuard AI — Real-time Demo Roadmap

> Fictional synthetic data only. This project is a software prototype, not a clinically validated medical device or clinical decision-support system.

## Product objective

Deliver a polished end-to-end demonstration of how timestamped patient observations could flow through ingestion, validation, risk-signal processing, alert management, and a live dashboard. Do not present simulated data as device data or model output as a clinically validated deterioration probability.

## Phase 1 — Observation simulator and ingestion API

- Deterministic stable, worsening, and recovering scenarios.
- Validated endpoint that generates one fictional observation, runs the current demo model, and saves the observation/prediction.
- Bounded step values and strict request schema.
- Automated tests for repeatability, trend direction, persistence, and invalid input.
- Endpoint: `POST /api/v1/demo/observations`.
- This phase is an API-level simulator. It does not yet continuously emit events or update the frontend in real time.

Acceptance: a request returns a prediction and observation ID; the record appears in the existing history endpoint; invalid request bodies are rejected.

## Phase 2 — Durable database and schema

- Provision hosted PostgreSQL and configure private `DATABASE_URL`.
- Store patient metadata, observations, predictions, alerts, and audit events with migrations and indexes.
- Preserve the SQLite developer workflow.
- Verify history survives restart and redeploy; document migration and backup strategy.

## Phase 3 — Live event delivery

- Add WebSocket updates for newly persisted observations and alerts.
- Broadcast only after successful persistence.
- Add reconnect/backoff, connection state, heartbeat, and REST catch-up after reconnect.
- Test multiple subscribers, disconnected clients, and event ordering.

## Phase 4 — Alert lifecycle

- Separate threshold/rule signals from ML estimates.
- Add stable alert IDs, deduplication, acknowledgement, assignment, notes, resolution, and an audit timeline.
- Make alert generation independent of an open browser session.
- Add demo-only escalation simulation with visible labels.

## Phase 5 — Patient timeline and data quality

- Unified patient timeline for observation, prediction, alert, acknowledgement, and resolution.
- Trend charts and visible last-observed timestamps.
- Flag stale, missing, malformed, and out-of-order observations.
- Never represent stale data as live.

## Phase 6 — Clinical scoring and model evaluation

- Implement NEWS2 only from an authoritative, reviewed specification, including required inputs and oxygen-supplementation/context rules.
- Keep deterministic score separate from ML output.
- Define prediction target and time horizon before training.
- Use patient-separated evaluation, leakage controls, calibration and sensitivity/false-alarm analysis.
- Keep synthetic model clearly labelled until real, appropriately authorized data and evaluation support stronger claims.

## Phase 7 — Explainability and trend analysis

- Add SHAP only for a compatible trained model.
- Persist model version and exact input snapshot with each prediction.
- Compare temporal approaches against a documented baseline; do not imply causality from feature explanations.

## Phase 8 — Access controls and operational safety

- Authentication, role-based authorization, audit logs, secrets management, request limits, monitoring and backup/restore drills.
- No real patient information in demo fixtures, screenshots, logs, or test runs.

## Phase 9 — End-to-end demo readiness

- Test full scenario from observation to alert to acknowledgement and resolution.
- Test reload, reconnect, restart, duplicate submission, stale feed, and database/API outage.
- Run CI and production smoke tests against the deployed branch.
- Keep explicit synthetic-data and non-clinical-use disclosures visible.

## Current known limitation

The current dashboard still uses local synthetic data for patient lists, vital charts, alerts and analytics. Phase 1 creates an API ingestion path but does not connect those dashboard views to the backend yet.

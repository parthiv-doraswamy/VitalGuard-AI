# VitalGuard AI — Real-time Demo Roadmap

> Synthetic demonstration only. Not clinically validated and not for clinical use.

## Phase 1 — Synthetic observation ingestion
- Deterministic stable, worsening and recovering scenarios.
- `POST /api/v1/demo/observations` generates one fictional observation, scores it with the existing demo model, and persists it.
- Request schema rejects unknown fields and bounds scenario/step.
- Each POST creates a new observation; no continuous stream or idempotency yet.
- Acceptance: returned observation ID appears in observation history and invalid requests are rejected.

## Phase 2 — Durable storage
Provision PostgreSQL, add schema migrations for patients, observations, predictions, alerts and audit events; verify restart/redeploy persistence.

## Phase 3 — Live event delivery
WebSocket updates after successful persistence, reconnect/backoff, health state and REST catch-up after reconnect.

## Phase 4 — Alert lifecycle
Rule signals separate from ML estimates; stable alert IDs, deduplication, assignment, acknowledgement, notes, resolution and audit events.

## Phase 5 — Patient timeline and data quality
Unified timeline, vital trends, timestamps, stale/missing/out-of-order reading indicators. Never present stale data as live.

## Phase 6 — Clinical scoring and ML evaluation
Implement NEWS2 only from a reviewed authoritative specification; define prediction target and horizon; evaluate models with patient-level leakage controls, calibration and false-alarm analysis.

## Phase 7 — Explainability and trend analysis
SHAP for compatible evaluated models, exact input/model snapshots, and validated comparison of temporal methods against a baseline.

## Phase 8 — Security and operations
Authentication, role-based access, audit logs, secrets management, monitoring, backup/restore and failure recovery.

## Phase 9 — End-to-end demo readiness
Test observation → risk output → alert → acknowledgement/resolution, including reconnects, stale feeds, duplicate submissions and backend outages.

## Current limitation
The frontend patient board, charts, alerts and analytics still use local synthetic data. Phase 1 is an API-level simulator, not full frontend real-time integration.

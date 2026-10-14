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

## Persistence hardening (delivered on `feature/persistence-hardening`)
PostgreSQL required on hosted deployments (`VITALGUARD_REQUIRE_POSTGRES`), pooled connections with timeouts, atomic observation + alert writes with events published only after commit, controlled 503s on database failure, versioned repeatable migrations (v1–v3) with legacy upgrade, cursor-paginated alerts, a secret-free health check, and a backup/restore and restart-survival procedure. Verified locally against SQLite and PostgreSQL 17; hosted verification is still outstanding. See [PERSISTENCE.md](PERSISTENCE.md).

## Synchronized two-laptop streaming (delivered on `feature/live-demo-backend`)
Backend stream sessions, with producer ownership tokens and a single active producer. Laptop A requests observations by sequence; the backend generates them with the existing simulator, scores and persists them, and broadcasts each one after commit. Sequences are idempotent, and missed events can be caught up through `/api/v1/live-demo/events`. Requires migration v4. The frontend is on `feature/live-demo-frontend`. See the backend README and the main-branch roadmap.

## Reproducible ML pipeline (delivered on `feature/ml-pipeline`)
The API now loads a versioned, verified artifact instead of training at import. `ml/` contains dataset preparation (MIMIC-IV format, leakage-safe as-of features, patient-level and temporal splits), baseline training with validation-only model and threshold selection, held-out evaluation, and tests. **Real-dataset training is blocked: there is no approved MIMIC-IV/eICU access.** Every result so far comes from synthetic or fictional fixture data and is not a clinical performance claim. See [ml/README.md](../ml/README.md) and [ml/data/README.md](../ml/data/README.md).

## Model benchmarking and selection (delivered on `feature/model-benchmark`)
Common model interface (load, validated predict, metadata, validate), a registry with automatic fallback to the previous artifact and manual promote/rollback, and a benchmark of logistic regression vs Random Forest vs XGBoost under identical splits. Predefined gates (deployability, latency, size, sensitivity, calibration) and a baseline-first selection rule, frozen before test evaluation. Run only on the fictional fixture, where the baseline was kept; the API stays in explicit synthetic-demo mode. See [ml/README.md](../ml/README.md).

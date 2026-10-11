# VitalGuard AI — Master Delivery Plan

**Last updated:** 2026-10-11  
**Current delivery phase:** Phase 5 in progress — versioned database migration implementation  
**Current system status:** Synthetic-data prototype; not approved for clinical use.

## Delivery rule

Work in order. For each phase: inspect current repository and deployed state; implement the smallest coherent change; add/update tests and documentation; commit to the correct GitHub branch; allow configured Render auto-deploy to run when relevant; verify the exact deployed commit and behavior; record evidence and limitations. Do not mark a phase complete merely because a commit or deployment exists. Do not break known-good functionality or claim unverified test results.

## Phases

| Phase | Goal | Exit evidence |
|---|---|---|
| 0 | Repository/deployment audit and baseline | Audit report, service/branch inventory, gaps and unverified checks documented |
| 1 | Requirements and safety boundaries | Product requirements, role needs, data policy, edge cases, clinical/model safety boundaries |
| 2 | Architecture, API contracts and data model | **Documentation baseline committed**: topology/trust boundaries, source-verified endpoint inventory, target error/observation contracts, current-vs-target data model. Runtime contract tests and physical migrations remain later work. |
| 3 | Authentication and secure identity | Secure login/session lifecycle, account disablement, secrets and session tests |
| 4 | Authorization and audit | Server-enforced roles/resource scope, deny-by-default, immutable security-relevant audit events |
| 5 | Durable database and migrations | Managed PostgreSQL configured privately, migrations, indexes, backup/restore and retention evidence |
| 6 | Validated data ingestion | Manual/import APIs, schema/unit/time validation, provenance, idempotency, partial failure handling |
| 7 | Dataset acquisition and governance | Authorized dataset manifests, terms/licensing, reproducible preprocessing and data splits |
| 8 | Time-aware feature engineering | Trends, freshness, missingness, source quality and leakage-resistant feature generation |
| 9 | Risk engine and model validation | Separate rule scoring from ML; reproducible baselines, independent evaluation, calibration and subgroup reports |
| 10 | Risk explanation and presentation | Accurate model/version/input provenance, limitations, no unsupported SHAP or clinical claims |
| 11 | Alert engine and escalation | Deduplication, acknowledgement/resolution, assignment, escalation, retry/cooldown and audit |
| 12 | Reliable real-time infrastructure | Reconnect, replay, ordering, backpressure and durable multi-instance delivery if required |
| 13 | Integrated dashboard and workflows | Authorized patient worklist, detail/timeline, data quality, alerts, trends and visible stale/degraded states |
| 14 | Notifications and operations | In-app delivery status, retry/failure visibility, approved channels and handover workflow |
| 15 | Security/privacy hardening | Threat model closure, least privilege, input/rate limits, CORS/CSRF review, privacy-safe logs and secrets checks |
| 16 | Automated testing and CI/CD | Frontend/backend/contract/authz/migration/E2E tests and dependency/security scanning |
| 17 | Observability and recovery | Health/readiness, structured logs, metrics/alerts, backup restore drill and incident runbooks |
| 18 | Staging/production release | Environment separation, configuration validation, exact-commit deploy evidence and rollback rehearsal |
| 19 | Real-time integration and resilience | Authorized source integration, duplicate/out-of-order/reconnect tests, load and failure recovery |
| 20 | Independent clinical/safety/privacy review | Signed evidence, controlled-pilot go/no-go; no automatic approval for clinical use |

## Release gates

A phase is not done until its exit evidence is recorded in the repository. A production-like software release additionally requires:
- Functional: supported workflows pass automated and manual checks.
- Data integrity: validation, provenance, timestamps, deduplication and correction paths are verified.
- Security: authentication and server-side authorization tests pass; no real data before this gate.
- Reliability: stale/unknown/degraded states, retries, reconnect and recovery are tested.
- Model evidence: target, dataset rights, leakage controls, independent validation and calibration are documented before predictive claims.
- Deployment: correct service branch, build, deployed commit, health and smoke checks are verified.
- Clinical readiness: independent clinical, privacy, security, usability and applicable regulatory reviews approve the specific intended use.

## Current baseline and known blockers

- Frontend: https://vitalguard-ai-g215.onrender.com (Render branch `main`).
- Backend: https://vitalguard-risk-api.onrender.com (Render branch `phase-3-risk-engine`).
- Source-level Phase 0 audit: [PHASE_0_AUDIT.md](PHASE_0_AUDIT.md).
- Phase 1 requirements: [PHASE_1_REQUIREMENTS.md](PHASE_1_REQUIREMENTS.md).
- Phase 2 architecture: [PHASE_2_ARCHITECTURE.md](PHASE_2_ARCHITECTURE.md).
- Phase 2 API contracts: [PHASE_2_API_CONTRACTS.md](PHASE_2_API_CONTRACTS.md).
- Phase 2 data model: [PHASE_2_DATA_MODEL.md](PHASE_2_DATA_MODEL.md).
- Existing feature roadmap: [REALTIME_DEMO_ROADMAP.md](REALTIME_DEMO_ROADMAP.md).
- Release runbook: [RENDER_RELEASE_RUNBOOK.md](RENDER_RELEASE_RUNBOOK.md).
- The model is synthetic-data LogisticRegression and is not clinically validated.
- Hosted PostgreSQL configuration, persistence-after-redeploy, and backup/restore evidence remain unverified.
- Phase 3/4 code is merged to `main` and `phase-3-risk-engine`; backend CI passed and Render reports the authorization commit live. Full browser-to-live API verification is still pending, and operator auth environment variables must be configured privately.
- The WebSocket event hub is in-process/single-instance; some frontend data remains synthetic fixture data.
- No real patient data is authorized for the current public demo.

## Phase 2 status and verification

- Architecture/trust-boundary, API-contract inventory and logical data-model documents are committed.
- Compared the documented current contracts with the inspected backend entry point, Pydantic schemas, simulator route, storage adapter and frontend API client.
- Documentation-only phase: application code and runtime behavior were not changed; application test suites and live smoke tests were not run as part of Phase 2.
- The target contract is a design baseline, not a claim that authentication, idempotency, standardized error envelopes, database migrations or durable event delivery already exist.
- Phase 2 documentation PR: [#44](https://github.com/parthiv-doraswamy/VitalGuard-AI/pull/44), merged as `523e8b22820a59afeb9ea15723e5aebb4b8be40c`.

## Data and clinical safety boundary

Historical research data is not a live feed. Live data must come from an authorized, governed source with secure identity, provenance, validation and monitoring. Do not enter identifiable patient data into the current deployment. Missing or stale observations must not be interpreted as normal. This plan does not itself confer clinical approval.


## Phase 3–4 status (2026-10-11)

- Phase 4 authorization PR #46 merged into `phase-3-risk-engine` as `c1eceda2d664f8a45fcb0d68ed46a3768e9c27d1`; backend and frontend CI passed on the final authorization branch commit.
- Main branch synchronization PR #49 merged as `872759be6d868d512ea36fb2f5b633e937838190`; frontend login PR #47 and the E2E login follow-up PR #50 are also merged.
- Render frontend is live on main commit `6edd0243a5c1a473c9e93e81274f1e18f578f8a4` before the E2E follow-up deploy; the follow-up commit is expected to deploy via the next frontend release.
- Render backend deployment for `c1eceda2d664f8a45fcb0d68ed46a3768e9c27d1` reported live on 2026-10-11. Startup logs show the FastAPI application started successfully.
- The login endpoint intentionally returns 503 until `VITALGUARD_AUTH_USERNAME`, `VITALGUARD_AUTH_PASSWORD`, and a 32+ character `VITALGUARD_AUTH_SECRET` are configured privately in Render. Do not send secrets through chat or commit them.
- Authorization is a single configured operator identity, not a managed identity provider or role-based access system. The WebSocket browser token currently travels in the query string; replace this before production because query strings can be logged.
- The application remains synthetic-only. No real patient data or clinical use is approved.

## Phase 5 status

- PR #48 merged into `phase-3-risk-engine` as `92d326153ccbc620a00878d45e2cf6b0a74b73a5`.
- Migration v2 adds `idx_alerts_patient_status_created`; tests verify fresh initialization, repeat application, and upgrade from schema migration v1. CI passed on the phase-5 migration PR.
- A managed PostgreSQL instance has not been provisioned or verified. Provisioning may incur cost and requires owner confirmation; keep `DATABASE_URL` private. Persistence, backup and restore checks remain exit criteria.

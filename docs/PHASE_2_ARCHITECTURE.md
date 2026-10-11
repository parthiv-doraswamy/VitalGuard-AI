# Phase 2 — Architecture and Trust Boundaries

**Date:** 2026-10-11  
**Status:** Architecture baseline documented; sensitive-data and clinical deployment remain blocked.

## 1. Current deployed topology

```text
Browser (React + TypeScript + Vite)
  | HTTPS REST requests / WebSocket
  v
Render FastAPI service (branch: phase-3-risk-engine)
  |-- risk/model functions (synthetic LogisticRegression)
  |-- observation/history functions
  |-- alert/timeline/trend routes
  |-- in-process WebSocket event hub
  |
  v
SQLAlchemy storage adapter
  |-- DATABASE_URL when configured
  |-- otherwise SQLite fallback
```

The frontend service is deployed from `main`; the backend service is deployed from `phase-3-risk-engine`. They are separate deployments. A change to `main` does not, by itself, update the backend branch.

## 2. Trust boundaries

1. **Untrusted browser:** all user input, identifiers, query parameters and client state are untrusted. Frontend checks are UX only.
2. **Public API boundary:** inspected backend routes currently do not demonstrate a complete authentication/authorization dependency. Treat data and mutation endpoints as public until route-by-route protection is implemented and tested.
3. **Application service boundary:** prediction, persistence, alert lifecycle and event publication must be separated enough to test transaction ordering and failure behavior.
4. **Persistence boundary:** secrets and database credentials belong only in private backend environment configuration. Never place them in Vite `VITE_*` variables or source control.
5. **Realtime boundary:** WebSocket messages must not be treated as authenticated merely because a client opened a socket. Future implementation must authenticate the connection and authorize each subscribed resource.
6. **External data boundary:** imports, devices, FHIR/HL7 and research datasets are untrusted sources; validate identity, schema, units, timestamps, provenance and replay/duplicate behavior.

## 3. Proposed logical modules

- **Identity and access:** principals, sessions/tokens, roles, resource scope and revocation.
- **Patient/resource registry:** internal identifiers, permitted team/ward assignment and external identifier mapping.
- **Observation ingestion:** schema validation, units, timestamps, source provenance, idempotency, correction/retraction.
- **Observation repository:** transactional persistence and indexed query paths.
- **Risk engine:** versioned rule score and ML output kept separate, each with explicit provenance.
- **Alert service:** idempotent alert lifecycle, assignment, escalation and audit.
- **Event delivery:** publish only after commit; replay/reconnect and durable fan-out when required.
- **Audit and operations:** security-relevant actions, request IDs, privacy-safe logs, readiness and recovery.
- **Frontend API layer:** typed response contracts, consistent error handling and visible loading/empty/stale/offline states.

These are target boundaries; this document does not claim all modules already exist as separate code packages.

## 4. Request lifecycle target

1. Validate request size, content type, schema and authentication.
2. Authorize the principal for the requested action and patient/resource scope.
3. Validate timestamps, units, ranges, provenance and duplicate key.
4. Persist observation and related audit/derived state transactionally.
5. Commit the transaction.
6. Publish an event carrying a stable event ID and schema version.
7. Return a typed response with request correlation ID and safe error semantics.

Do not broadcast an event for a write that failed to commit. Retries must not create duplicates when an idempotency key is supplied.

## 5. Failure semantics

- Invalid payload: structured 4xx response; no partial write.
- Missing/invalid credentials: 401; insufficient permissions: 403 (or a deliberate non-disclosing 404 policy).
- Unknown patient/resource: consistent not-found result; never leak cross-tenant existence.
- Duplicate source event: return documented duplicate outcome without a second observation.
- Database unavailable: 503 or documented retryable error; do not pretend the write succeeded.
- Event delivery unavailable after commit: record/retry delivery through an outbox or durable mechanism in a later phase; response semantics must not imply a failed observation was rolled back if it was committed.
- Missing/stale readings: explicitly represent unknown/stale, never synthesize normal readings.
- Model unavailable: expose a clear unavailable/degraded state, not a fabricated risk score.

## 6. Deployment boundaries

- Frontend service: Render static site, branch `main`, publish directory `dist`.
- Backend service: Render web service, branch `phase-3-risk-engine`, FastAPI app under `backend`.
- API base URL is currently configured in frontend code/environment; no credentials may be bundled into frontend assets.
- Current backend event hub is in-process and the service is configured for one instance.
- Database choice and durable hosted PostgreSQL configuration must be verified before sensitive use.
- Documentation-only commits on `main` may trigger a frontend rebuild because automatic deployment is enabled. They do not deploy backend code from its separate branch.

## 7. Architecture decisions

| Concern | Current evidence | Decision for subsequent phases |
|---|---|---|
| Frontend/backend split | Separate Render services | Keep split; version and test the contract |
| Backend framework | FastAPI | Retain unless evidence justifies change |
| Frontend framework | React/TypeScript/Vite | Retain; add shared typed contracts |
| Storage | SQLAlchemy; SQLite fallback; PostgreSQL URL supported | Phase 5: managed PostgreSQL, migrations, backup/restore |
| Authentication | Not established in inspected entry point | Phase 3: choose and implement identity after deployment constraints review |
| Authorization | Not established | Phase 4: server-side role and resource-scope checks |
| Realtime | In-process WebSocket hub | Phase 12: durability/replay and multi-instance decision |
| ML | Synthetic StandardScaler + LogisticRegression | Keep demo-only; Phase 9 defines validated evaluation before claims |
| Research/live data | No authorized operational source established | Separate historical dataset pipeline from live integration |

## 8. Security invariants

- Deny access by default for protected resources.
- Every resource read/write must enforce patient/team/ward scope server-side.
- Authentication must not be inferred from a patient ID, user-supplied role, frontend flag or acknowledgement checkbox.
- Never include secrets in browser bundles, logs or committed files.
- Audit records should be append-only to normal application roles.
- Events must carry only the minimum data required by authorized subscribers.
- Clinical outputs must carry algorithm/model version, observation provenance and limitations.
- The current public demo remains synthetic-only.

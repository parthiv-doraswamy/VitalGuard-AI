# Phase 14 — Operational readiness signal

## Endpoint

`GET /api/v1/ops/readiness` requires operator bearer-token authentication and returns a secret-free readiness snapshot.

It reports database reachability, whether the required operator-auth environment variables are configured, model import availability, the current storage backend, and the process-local/best-effort WebSocket transport limitation. It does not return environment values, tokens, connection strings, or credentials.

## Status semantics

- `ready`: database check succeeded and required operator-auth configuration is present.
- `degraded`: the database check failed or required auth configuration is missing.

The public `/health` route remains suitable for basic process/dependency health checks; the readiness endpoint is authenticated and provides more operational detail.

## Operational limits

- A successful readiness response does not validate the model or imply clinical readiness.
- WebSocket delivery remains process-local and best-effort.
- This endpoint does not check external notification providers, backups, migration drift, real-device connectivity, or clinical safety.
- Never place secrets in readiness output or frontend-visible environment variables.

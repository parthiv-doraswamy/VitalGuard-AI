# Phase 17 — Observability and recovery basics

## Implemented

- Add authenticated `GET /api/v1/ops/metrics` for in-process request counts, status counts, route-template counts, and aggregate latency.
- Keep metric labels bounded to matched route templates and status codes; never include query strings, patient identifiers, request bodies, credentials, or tokens.
- Reuse request IDs and baseline security headers already applied to HTTP responses.
- Add tests for authentication, aggregation, and privacy boundaries.

## Operational limits

- Metrics are in memory per worker/process and reset on restart. They are not durable, cross-instance, or a replacement for an external metrics backend.
- The metrics endpoint only describes requests handled by the current process.
- WebSocket fan-out is still process-local and best-effort.
- This phase does not add paging, email/SMS notifications, distributed tracing, log shipping, or a disaster-recovery guarantee.

## Recovery checklist

1. Check `/health` for database reachability.
2. Sign in and query `/api/v1/ops/readiness` and `/api/v1/ops/metrics`.
3. Inspect Render deploy events/logs and correlate with the response `X-Request-ID`; do not log tokens or sensitive payloads.
4. Confirm the intended backend commit is deployed before running the authenticated release smoke workflow.
5. After a database change or recovery, rerun synthetic prediction → history → alert lifecycle smoke checks and confirm persistence across a restart.

All evaluation and observations remain synthetic demo data. This is not clinical validation or production-grade monitoring.

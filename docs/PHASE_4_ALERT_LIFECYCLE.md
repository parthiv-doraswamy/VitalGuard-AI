# Phase 4 — Alert lifecycle

## What this phase adds

- Persistent alerts backed by the database schema from Phase 2.
- Idempotent creation using a unique source-event key.
- Alert listing and filtering by status or demo patient ID.
- Acknowledge and resolve actions.
- Audit events for creation, acknowledgement, and resolution.
- WebSocket `alert.created` events when an elevated-risk alert is generated from the manual prediction endpoint.

## API examples

List open alerts:

```bash
curl 'https://vitalguard-risk-api.onrender.com/api/v1/alerts?status=open&limit=50'
```

Acknowledge an alert:

```bash
curl -X POST 'https://vitalguard-risk-api.onrender.com/api/v1/alerts/1/acknowledge' \
  -H 'Content-Type: application/json' \
  -d '{"actor":"demo-operator"}'
```

Resolve an alert:

```bash
curl -X POST 'https://vitalguard-risk-api.onrender.com/api/v1/alerts/1/resolve' \
  -H 'Content-Type: application/json' \
  -d '{"actor":"demo-operator"}'
```

Audit history:

```bash
curl 'https://vitalguard-risk-api.onrender.com/api/v1/alerts/1/audit'
```

## Important limits

- The score threshold of 65 is a demonstration trigger only, not a validated clinical alarm threshold.
- Alerts are currently auto-created from `POST /api/v1/risk/predict`; simulator alert creation and frontend alert workflow are follow-up integration work.
- Actor identity is caller-supplied demo metadata, not authenticated identity. Do not use for real patient data or clinical operations.
- In-memory WebSocket fan-out supports a single backend process. Multi-instance deployments require shared event infrastructure.
- Synthetic demo only; not clinically validated and not for clinical use.

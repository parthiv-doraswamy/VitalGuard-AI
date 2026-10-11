# Phase 6 — Validated ingestion

## Endpoint

`POST /api/v1/ingestion/batch` accepts 1–100 records per request and requires the configured operator bearer token. Each item is independently validated so a malformed item does not discard other valid items.

## Validation and provenance

- Only `source_system: synthetic-demo` and patient IDs beginning with `DEMO-` are accepted in this public demo.
- Each record must include a unique source event ID, timezone-aware observation timestamp, the required vital fields, and explicit units.
- Values use the existing bounded `VitalInput` schema and blood-pressure consistency checks.
- Timestamps more than five minutes in the future or older than the 30-day demo window are rejected.
- Source event IDs are idempotent. Replaying the same event and payload returns the existing observation; reusing an event ID with a different payload returns a conflict.
- Observation and provenance rows are persisted in one database transaction.
- Batch responses report accepted, duplicate, conflict, and rejected records independently.
- Accepted records are broadcast to connected authenticated demo WebSocket clients.

## Database

Migration v3 creates the `ingestion_records` provenance ledger, a unique source/event constraint, and a patient/time index. Migration tests cover sequential application and existing v1-to-v3 upgrades.

## Limits and safety

- This is synthetic-demo ingestion, not an approved hospital, HL7, FHIR, or device integration.
- No identifiable patient data may be submitted. Production ingestion requires source authorization, identity/role controls, clinical data governance, privacy review, secure transport and secrets, retention policy, operational monitoring, and an approved clinical safety case.
- Unit labels are explicit but not a substitute for source-system mapping and calibration validation.
- This service and its model are not clinically validated and must not be used for diagnosis, triage, or treatment decisions.

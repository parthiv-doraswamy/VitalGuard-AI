# Phase 20 — Unified synthetic patient timeline

Endpoint: `GET /api/v1/patients/{patient_id}/timeline?limit=50`

Combines the newest persisted observation predictions, alerts, and alert audit events for a demo patient into one newest-first event list. Each event includes a stable event identifier, type, timestamp, summary, and relevant synthetic fields.

The response includes both the returned count and the available event count within the bounded source pages. It is an operational demonstration timeline, not a regulated medical record or complete audit guarantee. Data is synthetic only.

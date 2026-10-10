# Phase 22 — Patient detail timeline

The patient detail page now includes a separate backend-backed timeline showing persisted observations, alerts and alert audit events. It reads the unified `GET /api/v1/patients/{patient_id}/timeline` endpoint, offers manual refresh, and explicitly distinguishes backend records from the local synthetic dashboard fixtures.

If the endpoint is unavailable, the UI shows an error. If no records exist for the ID, it explains that local fixtures are separate from persisted backend records.

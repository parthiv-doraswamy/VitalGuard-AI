# Phase 9 — Persisted prediction history

The dashboard includes a backend-backed table of the most recent 25 stored prediction records. It shows record ID, demo patient ID, score, risk band, model version, and timestamp. An optional patient ID filter is applied server-side.

The panel reads `GET /api/v1/observations` and does not modify or create records. If the backend is unavailable, it displays an error rather than substituting local simulator data.

The current API history is bounded to 25 records in the UI. This is an operational demo history, not a regulated medical record, audit system, or clinical workflow.

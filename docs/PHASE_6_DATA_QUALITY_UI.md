# Phase 6 — Dashboard data quality panel

The dashboard now includes a backend data-quality panel that refreshes every 30 seconds and on manual refresh. It displays latest observed synthetic patient records, their freshness status, observation age, and missing required fields.

The panel requires the backend endpoint `GET /api/v1/observations/quality` from the Phase 6 backend PR.

If the endpoint is not deployed, the UI shows a clear warning rather than silently displaying stale/empty results as healthy.

Limitations: the panel only evaluates persisted synthetic records in the backend's bounded history page; it cannot verify device connectivity or detect a reading that was never sent. This is a prototype, not for clinical use.

# Phase 26 — Trend analytics smoke check

The live API smoke suite now verifies `GET /api/v1/observations/trends` for a newly created synthetic observation. With only one observation, the endpoint must return an explicit `insufficient_data` status for each trend instead of inventing a direction.

Run the live smoke workflow only after the backend deployment containing the trend endpoint is Live. The check writes a unique synthetic observation.

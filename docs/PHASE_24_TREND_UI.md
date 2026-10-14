# Phase 24 — Persisted trend summaries UI

Patient detail now includes a trend panel backed by `GET /api/v1/observations/trends`. It displays first/latest values, absolute change, descriptive direction, and observation count for persisted synthetic vital measurements and the synthetic model score.

The panel shows insufficient-data and API-unavailable states. It explicitly states that the direction is descriptive history, not a forecast or clinical interpretation.

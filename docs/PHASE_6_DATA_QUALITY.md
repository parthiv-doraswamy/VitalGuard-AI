# Phase 6 — Observation data quality

## Endpoint

`GET /api/v1/observations/quality?stale_after_seconds=300&limit=100`

Returns the latest stored observation per patient in the bounded history window and classifies its feed as:
- `fresh`: recent timestamp and required vital fields present
- `stale`: last stored observation is older than the configured threshold
- `incomplete`: required vital fields are missing
- `unknown`: timestamp cannot be parsed

Each item includes the latest observation ID, timestamp, age in seconds, and missing fields.

## Limits

- This endpoint checks persisted synthetic observations only; it does not know whether a device is connected or whether an expected reading was never sent.
- The result is bounded by the requested history page, so it cannot guarantee coverage of every patient in a large deployment.
- Timestamp freshness is not clinical interpretation. Missing or stale data must never be treated as normal.
- Synthetic demo only; not for clinical use.

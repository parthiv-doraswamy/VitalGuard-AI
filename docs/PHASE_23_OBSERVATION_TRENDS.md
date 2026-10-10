# Phase 23 — Descriptive observation trends

Endpoint: `GET /api/v1/observations/trends?patient_id=DEMO-001&limit=50`

Summarizes recent persisted observations for one demo patient, reporting sample count, first/latest values, absolute change, and ordinary least-squares slope over observation order for heart rate, SpO₂, systolic blood pressure, temperature, respiratory rate, and synthetic model score.

A direction label is based on a fixed per-metric slope threshold and is intended only to describe the stored series. Fewer than two values produces `insufficient_data`.

This endpoint does not forecast future values, estimate clinical deterioration, or infer medical significance. It is not clinically validated and must only use synthetic data.

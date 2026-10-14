# Phase 27 — Combined patient detail backend panels

Patient detail now shows both:
- A persisted timeline of synthetic observations, alerts and alert audit events.
- Descriptive trends computed from persisted observations.

These are separate from the local synthetic patient fixture, vitals charts and local alert cards. Each backend panel has its own loading, empty or unavailable state. Trends describe stored observations only and do not forecast clinical deterioration.

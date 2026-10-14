# Phase 15 — NEWS2 scoring workbench

Settings now contains an interactive form for synthetic adult observations. It submits to `POST /api/v1/scores/news2` and shows the per-parameter points and total returned by the backend.

The UI defaults to SpO2 Scale 1. Scale 2 requires an additional acknowledgement checkbox; that checkbox is only an assertion in the demo and does not establish clinical authorization. The API also rejects Scale 2 requests without the assertion.

No escalation or treatment recommendation is displayed. The score calculator is not clinically validated or approved for use in care.

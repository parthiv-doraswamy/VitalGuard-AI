# Phase 21 — End-to-end smoke verification

The live API smoke test now covers:
1. Health, model metadata and CORS.
2. Synthetic holdout evaluation and coefficient-contribution explanation.
3. NEWS2 Scale 1 default and Scale 2 authorization assertion.
4. Prediction persistence, history, and data-quality endpoint.
5. Elevated synthetic prediction, alert creation, acknowledgement, resolution and audit events.
6. Unified patient timeline containing observation, alert, and audit event types.
7. Invalid input rejection.

The smoke workflow runs when its workflow definition or smoke script changes, and can also be triggered manually from GitHub Actions. Run it only after the relevant backend Render deployment is live. It creates synthetic test records in the configured demo database.

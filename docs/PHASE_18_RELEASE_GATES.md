# Phase 18 — Release gates

VitalGuard AI remains a synthetic-data demo, not a clinical product. Never use real patient data or use its scores to guide care.

## Required checks before calling a deployment verified

- Confirm Render backend deploys the reviewed commit from `main` and record its SHA.
- Rotate any database credential shared outside the secret manager and update `DATABASE_URL` privately in Render.
- Confirm operator auth username/password and a high-entropy auth secret are configured privately.
- Confirm `/health` reports PostgreSQL, not local SQLite.
- Verify migrations and synthetic record persistence across a backend restart.
- Configure GitHub Actions secrets for the operator smoke-test account, then run the authenticated live API smoke workflow.
- Verify sign-in, protected REST requests, WebSocket authentication, alert lifecycle, audit history, and browser refresh.
- Review CORS, Render logs, database retention/expiry, backup/export, and restore procedures.

## Acceptance criteria

1. The deployed backend SHA matches the reviewed release.
2. Health and authenticated readiness checks pass.
3. The authenticated synthetic smoke workflow passes.
4. A synthetic observation remains available after a controlled restart.
5. Rollback to a known-good Render deploy is understood and tested.

## Rollback

Stop promotion if auth, migrations, health, or persistence fails. Roll back to the last known-good Render deployment, inspect logs using request IDs without exposing secrets or payloads, and rerun health and synthetic persistence checks.

These checks do not establish clinical validity, regulatory compliance, or production suitability. Clinical validation, clinician-supervised prospective evaluation, managed identity/MFA, durable distributed event delivery, and formal security/privacy review remain separate prerequisites.
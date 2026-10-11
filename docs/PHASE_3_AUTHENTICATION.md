# Phase 3 — Authentication and Secure Identity

**Status:** Minimal environment-configured bearer-token identity foundation implemented on the backend branch. This is not a complete production identity system and does not make the other API routes protected.

## Implemented in this phase

- `POST /api/v1/auth/login`: verifies one configured operator username/password using constant-time comparisons and returns a signed bearer token.
- `GET /api/v1/auth/me`: verifies the bearer token signature and expiry and returns the authenticated subject.
- Tokens expire after 900 seconds (15 minutes).
- Login request rejects unknown fields and bounds input lengths.
- If credentials or a signing secret are missing, login and identity validation fail closed with HTTP 503 rather than silently enabling a default account.
- Invalid credentials, missing tokens, forged tokens and expired tokens return HTTP 401.
- Signing secret must be at least 32 characters and is read only from the backend environment.

## Required private environment variables

Configure these only in the backend service's private environment settings, never in frontend `VITE_*` variables or Git:

- `VITALGUARD_AUTH_USERNAME`: one configured demo operator username.
- `VITALGUARD_AUTH_PASSWORD`: a strong, unique operator password.
- `VITALGUARD_AUTH_SECRET`: a cryptographically random signing secret of at least 32 characters.

Do not put real credentials in repository files, chat logs, test fixtures intended for deployment, URLs, or screenshots. Rotate any credential that has been exposed.

## Local verification

From repository root with backend dependencies installed:

```bash
PYTHONPATH=backend pytest backend/tests -q
```

Authentication tests cover missing configuration, successful login/identity lookup, wrong password, missing/forged token, and extra request fields. These tests must pass in CI before release.

## Critical limitations

- This is a single configured operator, not a managed identity provider, multi-user directory, password-reset system, MFA system or enterprise SSO.
- Tokens are short-lived but there is no server-side revocation/session registry yet.
- The authentication dependency is applied to `/api/v1/auth/me` only. Existing prediction, observation, alert, timeline, trend, simulator and WebSocket routes are not comprehensively protected by this phase.
- The current public deployment must remain synthetic-only. Do not configure real patient data or interpret this as sufficient protection for clinical use.
- Phase 4 must enforce authorization on every protected HTTP route and WebSocket connection, establish resource scope, and record security-relevant audit events.
- Before production use, review rate limiting, login abuse controls, credential rotation, secret management, session revocation, identity lifecycle and a managed identity provider with security stakeholders.

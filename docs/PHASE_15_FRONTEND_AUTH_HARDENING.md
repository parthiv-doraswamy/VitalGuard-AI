# Phase 15 — Frontend authentication and privacy hardening

## Changes in this phase

- Centralize operator-session token parsing and bearer-header attachment for raw REST fetches.
- Authenticate backend observation-quality, observation-history, and history-reconciliation requests.
- Supply the short-lived operator token to the WebSocket handshake because browser WebSocket APIs do not support custom Authorization headers.
- Keep the persistent alert inbox visible when the optional escalation-preview endpoint is not yet deployed.
- Expired or malformed session data is cleared rather than sent to the API.

## Security boundaries

- The frontend stores the short-lived bearer token in sessionStorage. This is a demo compromise and remains exposed to same-origin script execution; it is not equivalent to an HttpOnly cookie.
- WebSocket query tokens may appear in request telemetry. Keep tokens short-lived, avoid logging query strings, and consider a one-time WebSocket ticket in a future iteration.
- This remains single-operator demo authentication, without MFA, verified staff identities, per-role permissions, or token revocation.
- Do not enter real patient data. No clinical or production security certification is implied.

## Verification

- CI must pass frontend lint, tests and build, plus the backend test suite.
- After deployment, sign in and verify observation quality, prediction history, alert inbox, and live channel without 401/403 errors.
- Live verification depends on the Render backend deploying the same current code as the frontend. The backend is currently configured to deploy from `phase-3-risk-engine`; this branch mismatch must be resolved in Render before merged `main` backend features are live.

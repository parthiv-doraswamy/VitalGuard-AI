# Phase 13 — Alert review workflow in the dashboard

## Delivered

- The persistent alert inbox can display the backend's review-deadline preview, including the due count, overdue open alert summaries, and policy version.
- Preview loading is isolated from the primary alert-list request. A missing/invalid token or an unavailable Phase 11 endpoint shows a separate explanation instead of hiding the inbox.
- The UI only reads a bearer token from the short-lived `vitalguard.operator.session` session shape (`token`, `expiresAt`). Malformed or expired entries are removed.
- The browser must never receive a secret through a public `VITE_*` build variable. The current demo persona selector (`vg-demo-session`) is not server authentication and does not issue a backend bearer token, so the preview remains unavailable until a proper authenticated session supplies a token accepted by the backend.
- Existing alert filters, audit timeline, offline state, and acknowledge/resolve controls are preserved.

## Verification

1. Run frontend lint, unit tests, and production build.
2. With no operator token, verify the persistent inbox still loads and the preview shows an explicit unavailable state.
3. With an authorized test token in the documented short-lived session shape and a backend configured with the matching private `VITALGUARD_ALERT_ESCALATION_TOKEN`, verify the due count and empty state.
4. Verify a 401/503 from the preview does not turn a successful alert-list request into a full inbox failure.

## Boundaries and release dependency

The current login page is a UI-only demo persona selector. It is not identity verification. The preview's separate shared-token gate is not role-based authorization; do not use real patient data or treat the deadline values as clinical guidance. The backend must deploy Phase 11 before the preview can work.

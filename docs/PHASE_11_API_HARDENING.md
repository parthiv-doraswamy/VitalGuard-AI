# Phase 11 — Baseline API response hardening

The FastAPI app now adds:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- Restrictive `Permissions-Policy` disabling camera, microphone, and geolocation
- `Cache-Control: no-store` for API responses
- Server-generated `X-Request-ID` for request correlation

These are baseline headers, not a full security program. The demo API still has no user authentication or role-based authorization. Do not submit real patient information. Any public deployment intended for multiple users requires a security review, proper identity/authorization, rate limits at the edge, secrets management and operational monitoring.

# Phase 11 — Authenticated alert escalation preview

## Scope

Adds a deterministic, authenticated preview of review deadlines for existing synthetic alerts. The endpoint computes whether an alert remains open beyond an illustrative deadline; it never sends notifications or changes alert state.

## Demo policy

| Severity | Review deadline |
|---|---:|
| Critical | 5 minutes |
| High | 15 minutes |
| Medium / moderate | 60 minutes |
| Low | No deadline |

Only open alerts can be marked due. Acknowledged and resolved alerts are not due. Timestamps must include a timezone. Future timestamps have elapsed time clamped to zero.

## API and configuration

`GET /api/v1/alerts/escalation-preview?limit=100`

- Requires `Authorization: Bearer <token>`.
- Configure `VITALGUARD_ALERT_ESCALATION_TOKEN` as a private backend environment variable.
- If the token is missing from server configuration, the endpoint fails closed with HTTP 503. Missing or invalid request tokens receive HTTP 401.
- Responses include `notifications_sent: false`, `clinical_policy: false`, and a policy version.

## Safety and operational limits

No email, SMS, pager, webhook, push notification, or background escalation is sent. These deadlines are arbitrary engineering defaults, not clinical response standards. This demo token is endpoint-level access control, not user identity or role-based access control. Never use real patient data.

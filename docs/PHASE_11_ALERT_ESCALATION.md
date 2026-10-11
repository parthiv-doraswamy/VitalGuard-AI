# Phase 11 — Alert escalation preview

## Scope

Adds a deterministic, authenticated preview of review deadlines for existing synthetic demo alerts. It is a workflow aid for demonstrations, not a clinical escalation policy.

## Demo rules

| Severity | Review deadline |
|---|---:|
| Critical | 5 minutes |
| High | 15 minutes |
| Medium | 60 minutes |
| Low | No deadline |

Only alerts still in the `open` state can be marked due. Acknowledged and resolved alerts are not marked due. Naive timestamps are rejected; timestamps must include a timezone. Elapsed time is clamped to zero if the alert timestamp is in the future.

## API

`GET /api/v1/alerts/escalation-preview?limit=100`

Requires the existing bearer-token authentication. Returns the computed deadline, elapsed time, due state, policy version, and explicit `notifications_sent: false` / `clinical_policy: false` flags.

## Boundaries and next steps

- No email, SMS, pager, webhook, background worker, or real notification is sent.
- These demo deadlines are arbitrary engineering defaults, not recommended clinical response times.
- No real patient data or external clinical systems are supported.
- Before any real operational use, a responsible clinical and safety team must define and approve escalation rules, ownership, acknowledgement SLAs, downtime handling, audit retention, and validation.

# Phase 13 — Alert review workflow in the dashboard

## Delivered in this phase

- The persistent alert inbox requests the backend's deterministic escalation preview and surfaces the number of open alerts whose illustrative review deadline has elapsed.
- Due alerts are listed by ID, severity, and approximate overdue minutes.
- The component now attaches the current operator bearer token to protected alert, audit, acknowledgement, resolution, and escalation requests. Expired or malformed browser session data is cleared.
- Existing audit trail and acknowledge/resolve controls remain available.

## Verification expectations

1. Sign in to the deployed dashboard.
2. Open Alert Center and confirm persistent alerts load without 401 responses.
3. Confirm the review deadline preview displays a due count or the empty state.
4. Acknowledge a synthetic open alert and verify it disappears from the due preview after refresh.
5. Open its audit trail and verify the action is recorded.

## Boundaries

All data is synthetic. The deadline preview is a workflow demonstration, not clinical guidance. It sends no notifications and does not authenticate a real staff identity. The backend must deploy the corresponding Phase 11 endpoint for this UI feature to work.

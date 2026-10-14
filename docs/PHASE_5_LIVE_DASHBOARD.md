# Phase 5 — Live dashboard integration

## Included
- WebSocket client connects to `/api/v1/live`, sends a ping heartbeat, and reconnects with bounded exponential backoff.
- Connection state is visible in the application shell on every page.
- Live event client handles observation and alert event envelopes.
- Alert Center includes a backend-backed persistent alert inbox, status filters, refresh, acknowledgement and resolution.
- Alert inbox reloads from the backend after live events and after actions.
- REST observation history reconciliation helper is available for recovery flows.

## Expected backend
The backend must expose:
- `GET /api/v1/observations?limit=100`
- `GET /api/v1/alerts?limit=100`
- `POST /api/v1/alerts/{id}/acknowledge`
- `POST /api/v1/alerts/{id}/resolve`
- `WS /api/v1/live`

Set `VITE_API_BASE_URL` to the API base URL at frontend build time if not using the configured Render URL.

## Verification checklist
1. Run `npm ci`, `npm run lint`, `npm test`, and `npm run build`.
2. Open the deployed dashboard and check that the backend connection state is visible.
3. Trigger a synthetic prediction that crosses the demo threshold from the API docs.
4. Confirm the event counter changes and the backend alert appears in Alert Center.
5. Acknowledge, refresh, and resolve the alert; confirm the status persists.
6. Disconnect/reconnect the backend and verify the inbox can reload from REST.

## Known limitations
- The React dashboard's existing patient cards and vital charts still use the local simulation state; this phase adds live event visibility and backend alert operations but does not replace the entire patient dataset with API-driven data.
- The WebSocket backend uses in-process fan-out, so a multi-instance backend requires shared event infrastructure.
- The UI uses a demo actor label and is not authenticated. Do not use real patient information.
- Synthetic demo only; not clinically validated and not for clinical use.

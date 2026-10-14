# Phase 12 — WebSocket delivery resilience

## Behavior

- Every client send has a finite, positive timeout controlled by `VITALGUARD_WEBSOCKET_SEND_TIMEOUT_SECONDS` (default: 2 seconds).
- Invalid, non-finite, zero, or negative timeout configuration fails fast instead of silently turning every send into a timeout.
- Sends run concurrently. A slow, disconnected, or broken client is removed without blocking delivery to healthy clients.
- `dropped_clients` counts clients removed after a send failure or timeout. It is an in-process diagnostic, not a durable metric.
- A disconnected client can miss events. Reconnect and recover via the persisted REST history/event replay endpoints; WebSocket delivery itself is best effort.

## Verification

Run the backend suite, including `backend/tests/test_live_events_resilience.py`. It covers invalid configuration, timeout removal, broken clients, healthy-client delivery, and empty fan-out.

## Limits

The socket hub is per process. Cross-instance delivery depends on the event broker, and this change does not provide exactly-once delivery or guarantee that a client received an event. Synthetic demo only; not clinical alarm infrastructure.

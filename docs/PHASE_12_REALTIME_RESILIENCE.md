# Phase 12 — Real-time delivery resilience

## Changes

The in-process WebSocket hub now places a finite timeout on each client's event send. A client that times out or raises during delivery is removed from the active client set, so one slow or disconnected dashboard cannot indefinitely block event fan-out to the rest.

## Contract

- Events are persisted before the API broadcasts them.
- The WebSocket channel is a best-effort live signal, not the source of truth.
- Clients should recover missed events by refreshing the authenticated REST observation/alert history.
- Client messages are restricted to the existing heartbeat/control behavior; they do not write data.
- A two-second send timeout is a demo default and may need tuning under load.

## Limits

The hub remains process-local and does not provide cross-instance fan-out, durable replay, delivery acknowledgements, or guaranteed ordering across multiple workers. Those require a shared broker/event log and explicit cursor/replay semantics. Do not treat this demo transport as production-grade clinical infrastructure.

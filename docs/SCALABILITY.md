# Scaling the backend across instances

> Synthetic demonstration data only. These measurements describe software
> behaviour on one development laptop. They are not production capacity figures.

## 1. Architecture

```
POST (any instance) ──► one DB transaction:  data rows  +  event_outbox row(s)  +  pg_notify(seq)
                                                   │ commit
                         ┌─────────────────────────┴──────────────────────────┐
                 instance A dispatcher                               instance B dispatcher
       (fast path after its own commit; NOTIFY; 2 s poll)          (NOTIFY wake-up; 2 s poll)
                         │                                                    │
                 A's WebSocket clients                               B's WebSocket clients
```

- **PostgreSQL stays the source of truth.** Observations, alerts, audit and stream sessions live in their own tables. Every live event is also a row in `event_outbox` (migration v5), written **in the same transaction** as the change it describes. If the write fails or rolls back, no event exists and none is sent.
- **Broker = PostgreSQL `LISTEN/NOTIFY`,** using the database the deployment already has (`backend/app/event_broker.py`). No new service, credential or secret is needed. PostgreSQL delivers a notification only when its transaction commits. The notification is only a wake-up: dispatchers read the outbox, and they also poll every `VITALGUARD_EVENT_POLL_SECONDS`, so a notification missed during a listener reconnect is still delivered.
- **Why not Redis?** The deployment has no Redis. Redis Pub/Sub also does not keep messages, so recovery would need the outbox anyway. Adding Redis would only make sense if PostgreSQL notification throughput became the bottleneck, and the measurements below show it was not.
- **Single-instance fallback:** with SQLite, or `VITALGUARD_EVENT_BROKER=memory`, events reach only the clients of the instance that committed them. `/health` then reports `event_broker.mode: "memory"`, `cross_instance_delivery: false` and a note saying so. The PostgreSQL broker cannot be selected on SQLite; startup refuses.

## 2. Event contract and ordering

Every event carries:
- `event_seq`, the outbox ID: a global sequence that only increases (SQLite uses `AUTOINCREMENT` so IDs are never reused after pruning);
- `event_uuid`, `type`, `schema_version` (1), `emitted_at` (UTC, at write time) and `origin_instance`;
- `session_id` where relevant;
- `published_at`, stamped by each instance when it pushes the event to its own clients. This is the only field that differs between instances.

Existing fields such as `event_id` (the observation or alert ID) are unchanged. Event types are `observation.created`, `alert.created`, `alert.updated` (new: acknowledge/resolve) and `stream.state`.

Ordering and delivery guarantees:
- Within one transaction, events are delivered in sequence order. Across transactions, each instance delivers in the order commits become visible.
- Sequence numbers are assigned at insert time, so a transaction that started earlier can commit later. The dispatcher records the skipped number as a *gap*, delivers the event when it appears (`late_deliveries` in health), and treats gaps older than `VITALGUARD_EVENT_GAP_TIMEOUT_SECONDS` (60 s) as rolled back.
- Each instance delivers an event at most once. Clients deduplicate by `event_id`/`event_seq`, as the dashboard already does.
- Concurrent dispatch requests are coalesced: one outbox scan covers every commit made before it started. A write request still returns only after its own events have been pushed to that instance's clients.

## 3. Reconnection and recovery

- `GET /api/v1/events?after_seq=N[&session_id=…]&limit≤500` returns committed events oldest-first, in the same contract, from any instance.
- `history_truncated: true` means older events were pruned (`VITALGUARD_EVENT_RETENTION_HOURS`, default 168 h); the client should then reload state through the normal REST endpoints.
- The dashboard already deduplicates and catches up after every reconnect using `/api/v1/live-demo/events`, which rebuilds observation events (with their alerts) from the observations table, and refreshes the stream session. Clients that also need `alert.updated` or `stream.state` history should use `/api/v1/events`; the dashboard has not been switched to it yet.
- A new instance starts delivering from the newest sequence at startup. Events committed before its start, including transactions still in flight at that moment on other instances, are recovered by clients through REST, not pushed.

## 4. Bounded resources

| Resource | Bound | Setting |
| --- | --- | --- |
| DB connections per instance | `pool_size + max_overflow` (5 + 5), plus 1 listener connection | `VITALGUARD_DB_POOL_SIZE`, `VITALGUARD_DB_MAX_OVERFLOW` |
| Statement / idle-in-transaction time | 15 s / 30 s | `VITALGUARD_DB_STATEMENT_TIMEOUT_MS`, `VITALGUARD_DB_IDLE_TX_TIMEOUT_MS` |
| HTTP request time | 30 s, then 504 | `VITALGUARD_REQUEST_TIMEOUT_SECONDS` |
| WebSocket connections per instance | 1000; extra connections get an error frame and close code 1013 | `VITALGUARD_MAX_WEBSOCKETS` |
| Slow WebSocket client | 2 s per send, then dropped (it reconnects and recovers through REST); others are not delayed | `VITALGUARD_WEBSOCKET_SEND_TIMEOUT_SECONDS` |
| List endpoints | limits of 100 (events: 500), with cursors (`before_id`, `after_id`, `after_seq`) | — |
| Outbox growth | rows older than the retention window are pruned hourly by each instance | `VITALGUARD_EVENT_RETENTION_HOURS` |
| Dispatcher batch | 500 rows per scan; at most 10,000 tracked gaps | — |

**Capacity rule:** instances × (pool_size + max_overflow + 1) + migration/admin headroom must stay below PostgreSQL `max_connections`. With the defaults that is 11 per instance, so a database with 100 connections fits about 8 instances, minus headroom. Check the Render PostgreSQL plan's connection limit before adding instances.

## 5. Health

- `GET /health`: `components.api`, `components.database` (backend, schema, latency) and `components.event_broker` (mode, `cross_instance_delivery`, `listener_connected`, reconnects, sequence position, pending gaps, late deliveries, WebSocket clients). The status is `ok`, or `degraded` when the broker cannot currently deliver across instances. Data is still committed and recoverable while degraded. 503 if the database is unreachable.
- `GET /health/live`: the process is up (liveness).
- `GET /health/ready`: the database is reachable (readiness). Use this for load-balancer checks.
- At startup, an instance waits up to 5 s for its listener (`VITALGUARD_EVENT_LISTENER_STARTUP_TIMEOUT_SECONDS`), so healthy instances don't briefly report degraded.

## 6. Scale-out requirements

1. All instances use the same PostgreSQL `DATABASE_URL`, with `VITALGUARD_REQUIRE_POSTGRES=true` and `VITALGUARD_EVENT_BROKER=auto` (or `postgres`).
2. **Session-level connections:** connect directly or through a session-pooling proxy. Transaction-pooling proxies (for example PgBouncer in transaction mode) break `LISTEN`.
3. Give each instance a unique `VITALGUARD_INSTANCE_ID` (default: hostname-pid). It appears in events, health and the listener's `application_name`.
4. The load balancer must support WebSockets. Sticky sessions are **not** required, because any instance delivers every event.
5. Migrations run at startup under a PostgreSQL advisory lock, so simultaneous startups are safe.
6. Known limits:
   - The live-demo emit rate limit (`MIN_EMIT_GAP_SECONDS`) is per process. Sequence uniqueness, which is what prevents duplicates, is enforced by the database.
   - The current Render backend is a single instance. Running several requires a Render plan and service configuration that allow it. This has **not** been tested on Render.

## 7. Verification (local, 2026-10-14)

Environment: Apple M2 (8 cores, 8 GB), macOS, Python 3.12, PostgreSQL 17.11 (local, `max_connections` 100). All server processes, load generators and the database ran on **the same laptop**.

Automated tests (`backend/tests/test_live_events.py`, `backend/tests/test_multi_instance.py`):
- **Two real uvicorn processes** on one PostgreSQL database:
  - clients on different instances receive the same event (identical `event_seq`/`event_uuid`);
  - 40 concurrent writes split across both instances reach every client exactly once;
  - the same stream sequence sent to both instances at once is stored once;
  - terminating an instance's listener connection: an event committed on the other instance during the outage is still delivered, the listener reconnects, and health returns to `ok`;
  - a disconnected client recovers the exact missed events from the *other* instance;
  - neither instance logged a traceback.
  - These passed 4 runs out of 4.
- **In-process:**
  - outbox rows commit atomically with the data, and a failed write leaves no event;
  - repeated wake-ups deliver an event once;
  - out-of-order commits are delivered late, and rolled-back sequence IDs expire;
  - recovery covers every event type, in order, and reports pruned history;
  - retried stream sequences return the original envelope;
  - alert transitions are broadcast;
  - health is split by component in both modes;
  - the WebSocket cap and the slow-client timeout work.
- Full backend suite: 213 tests passed with PostgreSQL required.
- **Real dashboard across instances** (two frontend builds, one per instance; browser network log confirmed Laptop A used only instance A and Laptop B only instance B):
  - a stream started on A appeared on B's normal dashboard with the same event ID (#20) and score (99);
  - pause and stop propagated across instances, and B stayed connected in receiver mode;
  - no server tracebacks.
- The existing Playwright suite (5/5, including the two-browser live demo) also passes against this backend.

Bugs these tests and load runs found, and that were fixed:
- SQLite reused outbox IDs after pruning, which would silently break `after_seq` recovery.
- Timestamps were rendered in the PostgreSQL session time zone, so the same event looked different on different instances.
- Health reported `degraded` for the first moments after startup.
- The gap timeout setting was read at import time and ignored.

### Load tests (`backend/scripts/load_test.py`)

Mix: 70% `POST /api/v1/risk/predict` (writes the observation plus outbox events), 30% `GET /api/v1/observations?limit=50`. 15 s per level. WebSocket listeners on every instance measure submit-to-delivery latency (same clock) and whether every committed observation reached every listener. Raw results: [load-tests/2026-10-14/](load-tests/2026-10-14/).

**Two instances, one generator process** (after dispatch coalescing):

| Users | Throughput (req/s) | Error rate | Predict p50 / p95 / p99 ms | Delivery p50 / p95 ms | Delivered to all 4 listeners | Max RSS MB per instance | Max DB conns |
|---|---|---|---|---|---|---|---|
| 1 | 283.4 | 0.00% | 3.4 / 3.7 / 4.0 | 2.9 / 3.2 | 2954/2954 | 197 / 197 | 7 |
| 5 | 576.9 | 0.00% | 9.5 / 15.6 / 18.7 | 7.1 / 12.5 | 6032/6032 | 198 / 198 | 13 |
| 10 | 624.9 | 0.00% | 15.5 / 33.0 / 43.3 | 12.8 / 26.6 | 6572/6572 | 198 / 198 | 13 |
| 25 | 357.4 | 0.00% | 53.7 / 183.3 / 295.7 | 48.4 / 179.3 | 3794/3794 | 178 / 179 | 13 |
| 50 | 277.5 | 0.00% | 120.4 / 546.5 / 902.2 | 108.6 / 531.0 | 2994/2994 | 179 / 181 | 14 |
| 100 | 193.5 | 0.00% | 318.8 / 1702.2 / 3083.3 | 280.7 / 1658.2 | 2065/2065 | 180 / 181 | 13 |

**Four instances, one generator process:** throughput peaked at 570 req/s (10 users), with 450.7 / 297.6 / 224.2 req/s at 25 / 50 / 100 users. Errors were 0%, except one client-side `ReadError` at 100 users (0.03%) with no matching server error. Every one of 24,679 committed observations reached every listener.

**Diagnosis of the throughput drop at higher concurrency:**
- PostgreSQL was nearly idle during a 50-user run: at most one active backend and no lock waits. Server CPU *fell* as users increased (about 83% → 46% per process), and database connections stayed flat. So neither the database nor `NOTIFY` was the limit.
- Adding instances (2 → 4) did not raise peak throughput.
- Splitting the same load across **4 generator processes** raised throughput to **730.5 req/s** at 24 users (0 errors, p95 about 86 ms) and **548.1 req/s** at 100 users (0 errors, p95 about 410–445 ms). The single generator managed 224 req/s at 100 users.
- **Conclusion:** at high concurrency the single-process load generator was a major limit, and everything shared one 8-core laptop. These numbers are a lower bound on what the server code can sustain; they are **not** a server capacity figure. Measuring true per-instance capacity needs the generator on separate hardware and the target deployment environment.
- An earlier two-instance run, before dispatch coalescing, measured 276 / 591 / 653 / 340 / 279 / 255 req/s at the same levels. Coalescing safely cut per-instance database queries (about 32,000 coalesced dispatch requests per instance) but made **no measurable throughput difference**.

Across all three full runs: **74,341 committed observations, 100% delivered to every listener on every instance, 0 duplicate deliveries**, and no `ERROR` or `Traceback` lines in any instance log. Memory stayed at about 170–200 MB per instance; at most 26 database connections were open with 4 instances.

Reproduce:
```bash
# instances (each with the same DATABASE_URL, a unique VITALGUARD_INSTANCE_ID)
LOADTEST_DATABASE_URL=postgresql+psycopg://... python backend/scripts/load_test.py \
  --targets http://127.0.0.1:8801,http://127.0.0.1:8802 --levels 1,5,10,25,50,100 --duration 15 \
  --listeners 2 --pids <pid1>,<pid2> --out results.json
```

# Phase 19 — Synthetic resilience and recovery checks

## Added checks

- Exercise a deterministic burst of 25 synthetic predictions and verify unique persisted observation IDs.
- Verify history pagination remains bounded under a larger record set.
- Verify a synthetic observation remains readable after a fresh application lifespan starts against the same SQLite file.
- Verify invalid payload bursts return validation errors and do not create observations.

## Scope and limitations

These are repeatable integration/regression checks, not a production load benchmark. They do not establish throughput capacity, PostgreSQL availability under failure, cross-worker WebSocket delivery, disaster recovery, or clinical reliability. They run only with generated demo records and local test storage.

Before release, separately run the authenticated live API smoke workflow against the intended Render commit and confirm PostgreSQL persistence there. Do not point load tests at a production deployment or use real patient data.

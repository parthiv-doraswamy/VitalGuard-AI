# Phase 2 — Data Model and Lifecycle

**Status:** Target logical model documented; physical schema and migrations are future work. Current storage remains a demo observation/prediction table and must not be used as a production patient-record store.

## 1. Current physical storage

The inspected `backend/app/storage.py` defines an `observations` table with:
- `id`: generated primary key.
- `patient_id`: string reference as provided by the caller.
- `created_at`: database-generated timestamp.
- `input_json`: serialized model input.
- `prediction_json`: serialized model output.
- `model_version`: model version string.

A descending composite index covers patient ID, creation timestamp and ID. The adapter uses `DATABASE_URL` when configured and otherwise falls back to SQLite. Tables are currently initialized using SQLAlchemy `create_all`; a versioned migration system is not established by this file.

This physical schema is suitable only for the current synthetic prototype and does not itself provide identity, patient tenancy, provenance, source-event idempotency, correction history, or clinical-grade audit guarantees.

## 2. Target logical entities

| Entity | Purpose | Core integrity requirements |
|---|---|---|
| User / Principal | Authenticated identity | Unique subject, enabled/disabled state, credential/session lifecycle |
| Role Assignment | Role plus scope | Server-enforced permissions, effective dates and revocation |
| Patient Reference | Internal patient/resource mapping | Scoped access; external identifiers protected and separately mapped |
| Care Team / Unit | Resource scope | Explicit membership/assignment and audit of changes |
| Observation | A measured value or coded finding | Type, value, unit, observed time, received time, source, validation state |
| Source Event | Ingestion source and idempotency | Unique source key in a defined scope; payload fingerprint for conflict detection |
| Observation Revision | Correction/retraction history | Append-only link to superseded record, actor and reason |
| Risk Assessment | Versioned score/model output | Inputs/observation references, algorithm/model version, output, missingness and provenance |
| Alert | Work item for review | State machine, dedup key, severity, owner/scope and timestamps |
| Alert Event / Audit Event | Who did what and when | Append-only event history; actor, action, target, outcome, request ID |
| Outbox Event | Reliable downstream publication | Transactional event record, attempts, published time and error classification |
| Import Batch | Bulk-ingestion tracking | Source, uploader, manifest, row outcomes, checksum and completion status |

These are target logical concepts. This document does not claim that all tables or relationships exist in the repository.

## 3. Observation lifecycle

```text
Received
  -> schema/type validation
  -> unit and timestamp validation
  -> source identity / patient mapping
  -> duplicate and correction checks
  -> accepted + persisted
  -> assessment generated (if enabled)
  -> alert state evaluated
  -> committed event published
  -> visible with provenance and quality status
```

Rejected rows should receive a safe, actionable validation result and should not partially alter patient state. Bulk import should preserve row-level outcomes and allow operators to identify failures without logging sensitive payloads.

## 4. Timestamp rules

- Store the source's observation time separately from server receipt time.
- Require explicit timezone/offset for external timestamps; normalize storage to UTC while preserving source representation where needed for audit.
- Reject or quarantine implausibly future-dated records according to a documented policy.
- Accept late observations without silently reordering history by arrival time; order clinical timelines by observation time with deterministic tie-breakers.
- Keep stale/fresh thresholds configurable and distinguish unknown from normal.
- Do not use local wall-clock time from the browser as the authoritative receipt time.

## 5. Idempotency and correction

- Use a unique key scoped to source/integration, not just a caller-controlled patient ID.
- Repeating the same key and same canonical payload returns the original result or a documented duplicate result.
- Repeating a key with a different payload returns a conflict and creates no silent overwrite.
- Corrections/retractions create an auditable revision relation; never erase history as if the original observation never existed.
- If an upstream source supplies no stable event key, document a conservative deduplication policy and its false-positive/false-negative tradeoffs.

## 6. Transactions and event publication

The future ingestion transaction should commit the observation, related assessment/alert changes and an outbox event together where practical. A publisher can then deliver events with retry tracking. This avoids broadcasting an observation that failed to commit and avoids losing all evidence of an event if the process exits after a database commit.

A durable outbox is not implemented by the current in-process event hub and belongs to the later persistence/realtime phases.

## 7. Migration and retention plan

Phase 5 must:
- Provision and verify a managed PostgreSQL database in the correct private environment.
- Introduce versioned migrations and a repeatable upgrade path.
- Create indexes based on measured query patterns.
- Define retention, deletion, archival and audit-retention policy with the system owner.
- Document encrypted backup, restore tests and recovery objectives.
- Verify persistence across redeploy/restart.
- Keep secrets out of source control and frontend bundles.
- Decide how synthetic SQLite records will be discarded or migrated; never automatically promote them to real-patient records.

## 8. Privacy boundary

No real patient data is permitted in the current public demo. The future schema is a design target only and does not establish a lawful basis, data-use agreement, clinical governance approval or regulatory readiness.

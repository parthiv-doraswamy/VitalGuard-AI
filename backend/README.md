# VitalGuard AI — Risk Engine API

> **Prototype only. Synthetic data. Not for clinical use.**

This FastAPI service serves a small scikit-learn logistic-regression pipeline trained on generated synthetic observations with heuristic-generated labels. The model is loaded from a versioned, hash-verified artifact (`app/model_artifacts/synthetic-logreg-0.1.0/`, built by `python ml/train.py --experiment synthetic_demo`); nothing is trained at import or startup. If the artifact is missing or fails verification, the identical model is rebuilt in-process and `/api/v1/model/info` reports `model_source: "fallback-synthetic-training"`. Set `VITALGUARD_MODEL_REQUIRE_ARTIFACT=true` to fail instead. See [ml/README.md](../ml/README.md).

Which artifact is served comes from `app/model_artifacts/registry.json` (`active`, with `previous` used automatically if the active one fails verification), unless `VITALGUARD_MODEL_ARTIFACT` overrides it. `GET /api/v1/model/info` reports the serving model: `model_version`, `mode` (`synthetic-demo` unless an explicitly allowed research artifact is active), `model_source`, `algorithm`, artifact provenance (SHA-256, dataset, threshold, selection), `load_error`, and `supports_coefficient_contributions`. The prediction response contract is unchanged. `/api/v1/risk/explain` keeps its shape and returns no contributions for non-linear models. It stores submitted demo predictions in PostgreSQL when `DATABASE_URL` is set (hosted) or SQLite (local development). No real patient dataset is included or loaded.

## Run locally

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

- Health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs
- Model information: http://127.0.0.1:8000/api/v1/model/info
- Saved demo history: http://127.0.0.1:8000/api/v1/observations

## Example prediction

```bash
curl -X POST http://127.0.0.1:8000/api/v1/risk/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "patient_id": "DEMO-001",
    "age": 58,
    "heart_rate": 82,
    "spo2": 98,
    "systolic_bp": 122,
    "diastolic_bp": 78,
    "temperature": 37.0,
    "respiratory_rate": 16
  }'
```

## Endpoints

- `GET /health` — service health, model version and database diagnostics (backend, durability, schema version; never the URL).
- `GET /api/v1/model/info` — algorithm, features and limitations.
- `POST /api/v1/risk/predict` — validates vital observations, predicts a demo risk band, and persists the record.
- `GET /api/v1/observations?limit=10` — list recent demo predictions (limit 1–100).
- `GET /api/v1/observations?patient_id=DEMO-001` — filter by demo patient ID.
- `GET /api/v1/observations?before_id=25&limit=10` — page toward older records using the returned `next_before_id` cursor.
- `GET /api/v1/alerts?limit=50&before_id=…` — cursor-paginated synthetic alerts.
- `GET /api/v1/observations?after_id=…&session_id=…` — oldest-first records after an id, for catching up.

### Synchronized live demo (`/api/v1/live-demo`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/config` | Producer-key requirement, limits, active session |
| GET | `/sessions/current`, `/sessions/{id}` | Public session state (never the token) |
| POST | `/sessions` | Start the single active stream (`scenario`, `interval_ms`, `takeover`). Returns the producer token once. 409 `producer_active` if another stream is active |
| POST | `/sessions/{id}/pause` · `/resume` · `/stop` | Owner only (`X-Producer-Token`) |
| POST | `/sessions/{id}/observations` | Owner asks for `{"sequence": n}`; the backend generates (existing simulator), scores, persists, then broadcasts. Retrying a committed sequence returns the same event with `duplicate: true` |
| GET | `/events?after_id=…` | Committed events in the WebSocket contract, oldest first, for reconnect catch-up |

Live events are written to a transactional outbox and delivered to clients on every backend instance through PostgreSQL `LISTEN/NOTIFY`. With SQLite the API runs in explicit single-instance mode. `GET /api/v1/events?after_seq=…` recovers missed events; `/health` reports API, database and event broker separately (`/health/live`, `/health/ready` for orchestration). See [docs/SCALABILITY.md](../docs/SCALABILITY.md).

WebSocket `/api/v1/live` events: `observation.created` (event_id, session_id, sequence, timestamp, observation, model_version, prediction, alert, server_received_at, published_at, `demo_only`, `data_origin: "synthetic"`), `alert.created`, and `stream.state` (started/paused/resumed/stopped). Sending `{"type":"ping","client_time":<ms>}` returns a pong with `server_time` so clients can estimate clock offset.

Optional settings: `VITALGUARD_STREAM_PRODUCER_KEY` requires a matching `X-Demo-Producer-Key` header to start a stream; `VITALGUARD_STREAM_IDLE_TIMEOUT_SECONDS` (default 120) lets an abandoned stream be replaced without takeover.

Database failures return HTTP 503 `{"error": "database_unavailable"}`; nothing is saved and no live event is sent.

## Storage and deployment

- Hosted: set `DATABASE_URL` to the managed PostgreSQL connection string in the backend service's private environment, and set `VITALGUARD_REQUIRE_POSTGRES=true` so the service refuses to start on anything else.
- Local: with `DATABASE_URL` unset, SQLite is used at `backend/vitalguard_demo.sqlite3` (override with `VITALGUARD_DB_PATH`). SQLite on an ephemeral host is lost on restart/redeploy.
- Migrations run automatically at startup; `python -m app.db_tools status|migrate` (from `backend/`) shows or applies them.
- Backup/restore drill: `python -m app.db_tools export|restore|verify`. Restart check: `python backend/scripts/persistence_check.py write|verify`.

See [docs/PERSISTENCE.md](../docs/PERSISTENCE.md) for transaction semantics, migrations, pool and timeout settings, backup/restore and verification status. Do not treat this store as a patient-record system.

Set `CORS_ORIGINS` to a comma-separated list of exact permitted browser origins. The deployed frontend origin is allowed by default.

## Tests

```bash
python -m pip install -r backend/requirements.txt
PYTHONPATH=backend pytest backend/tests -q
```

The tests isolate SQLite in temporary directories. To also run the PostgreSQL variants, point `VITALGUARD_TEST_POSTGRES_URL` at a **disposable** database (its `public` schema is dropped before each test), e.g. `postgresql+psycopg://user@127.0.0.1:5432/vitalguard_test`. CI does this with a PostgreSQL service container and fails if those tests are skipped.

## Important limitations

- The classifier is trained on generated synthetic data, not real clinical records.
- Labels are generated from a transparent heuristic. Outputs demonstrate software integration; they are not validated estimates of deterioration probability.
- Feature indicators are threshold flags, not causal explanations.
- Do not use this service for diagnosis, triage, treatment, or real patient monitoring.

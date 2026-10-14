# VitalGuard AI — Risk Engine API

> **Prototype only. Synthetic data. Not for clinical use.**

This FastAPI service trains a small scikit-learn logistic-regression pipeline at process startup using generated synthetic observations and heuristic-generated labels. It stores submitted demo predictions in PostgreSQL when `DATABASE_URL` is set (hosted) or SQLite (local development). No real patient dataset is included or loaded.

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

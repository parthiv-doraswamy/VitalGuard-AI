# VitalGuard AI — Risk Engine API

> **Prototype only. Synthetic data. Not for clinical use.**

This FastAPI service introduces the Phase 3 risk-prediction API. It trains a small scikit-learn logistic-regression pipeline at process startup using generated synthetic observations and heuristic-generated labels. No real patient dataset is included or loaded.

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

## Tests

```bash
python -m pip install -r backend/requirements.txt
PYTHONPATH=backend pytest backend/tests -q
```

## API

- `GET /health` — service health and model version.
- `GET /api/v1/model/info` — algorithm, features and demo limitations.
- `POST /api/v1/risk/predict` — validates vital observations and returns a demo risk score, band and threshold indicators.

Set `CORS_ORIGINS` to a comma-separated list of permitted browser origins when deploying. The deployed frontend origin is allowed by default.

## Important limitations

- The classifier is trained on generated synthetic data, not on real clinical records.
- Labels are generated from a transparent heuristic. Model outputs are demonstrations of an ML integration workflow, not validated estimates of deterioration probability.
- The feature indicators are threshold flags, not causal explanations.
- Do not use this service for diagnosis, triage, treatment, or real patient monitoring.

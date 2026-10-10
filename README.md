# VitalGuard AI — Patient Deterioration Early-Warning Prototype

> **DEMO ONLY · SYNTHETIC DATA · NOT FOR CLINICAL USE**
>
> VitalGuard AI is a software prototype for exploring patient-observation monitoring, risk-signal visualisation and alert workflows. The included patients and observations are synthetic. The current risk model is trained on generated data and is not clinically validated.

## Requirements

- Node.js 20 or newer (Node.js 22 LTS recommended)
- npm 10 or newer
- Python 3.11+ recommended for the FastAPI backend

## Quick start

Frontend:
```bash
npm ci
cp .env.example .env
npm run dev
```

Backend (from the repository root):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload
```

The frontend normally runs at `http://localhost:5173`; the backend at `http://localhost:8000`. API docs are at `http://localhost:8000/docs`.

## Verification commands

Run from the project root:
```bash
npm run lint
npm test
npm run build
```

Run backend tests from `backend/`:
```bash
pytest -q
```

Only describe a command as passing after it has been run successfully against the current source.

## Environment configuration

Copy `.env.example` to `.env` for local development. Vite variables prefixed with `VITE_` are bundled into browser code, so never store secrets in them.

| Variable | Purpose |
| --- | --- |
| `VITE_DEMO_MODE` | Starts in synthetic demo mode unless explicitly set to `false`. |
| `VITE_API_BASE_URL` | Optional FastAPI base URL; local default is normally `http://localhost:8000`. |
| `VITE_APP_VERSION` | Frontend version label. |
| `DATABASE_URL` | Optional backend database URL; SQLite is used by default. |
| `VITALGUARD_DB_PATH` | Optional local SQLite file path for tests/development. |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins. |

## Current implementation

- React, TypeScript, Vite and Tailwind frontend with dashboard, patient directory/detail, alerts, analytics and settings.
- Existing synthetic patient records, demo simulation controls and local UI persistence.
- FastAPI risk endpoint, model metadata endpoint, bounded observation history and synthetic Logistic Regression model.
- SQLAlchemy storage adapter supporting local SQLite and PostgreSQL when `DATABASE_URL` is configured.
- Phase 1 adds a deterministic backend simulator for stable, worsening, and recovering fictional observation scenarios.

### Phase 1 API: synthetic observation ingestion

Endpoint:
`POST /api/v1/demo/observations`

Example request:
```json
{
  "patient_id": "DEMO-LIVE-001",
  "scenario": "worsening",
  "step": 3
}
```

Supported scenarios: `stable`, `worsening`, `recovering`. Step must be between 0 and 1000. The endpoint generates one deterministic observation for the requested scenario and step, runs the current synthetic risk model, and persists the resulting observation/prediction using the configured storage adapter.

Example local request:
```bash
curl -X POST http://localhost:8000/api/v1/demo/observations \
  -H 'Content-Type: application/json' \
  -d '{"patient_id":"DEMO-LIVE-001","scenario":"worsening","step":3}'
```

History can be inspected at:
`GET /api/v1/observations?patient_id=DEMO-LIVE-001`

This is an API-level simulator, not a continuous streaming feed yet. Each request creates a new observation; requests are not idempotent. WebSocket delivery, frontend integration, and durable hosted PostgreSQL configuration are future phases.

## Important limitations

- The default frontend still uses local synthetic data for the patient directory, vital charts, alerts and analytics. Those views are not yet fully connected to the backend event stream.
- The model is a StandardScaler + LogisticRegression classifier trained on generated synthetic observations. Its output is a demo signal, not a validated probability of clinical deterioration.
- Feature explanations are illustrative threshold indicators, not SHAP explanations or causal attributions.
- The existing NEWS2-like display is not a validated NEWS2 implementation.
- No clinical performance, safety, regulatory or real-device integration is claimed.
- Do not use real patient data or use this prototype to diagnose, triage, or make treatment decisions.

## Project layout

```text
backend/app/
  main.py              FastAPI application
  model.py             Synthetic demo classifier
  schemas.py           Validated API request/response schemas
  simulator.py         Deterministic fictional observation scenarios
  simulator_routes.py  Demo observation ingestion endpoint
  storage.py           SQLite/PostgreSQL storage adapter
backend/tests/
  test_api.py
  test_simulator.py
src/
  data/                Synthetic frontend fixtures
  pages/               Dashboard and feature pages
  services/            API and demo data services
  store/               Frontend state
  test/                Frontend tests
docs/
  REALTIME_DEMO_ROADMAP.md
```

## Database configuration

- Local development defaults to SQLite.
- Hosted deployments can set `DATABASE_URL` to a PostgreSQL connection string. The adapter normalizes common `postgres://` and `postgresql://` URLs to psycopg 3.
- Configure credentials only in the backend service's private environment settings; do not commit them.
- Provision the hosted database separately. Existing SQLite records are not automatically migrated.
- This storage adapter currently supports synthetic demonstration data only; it is not a production patient-record system.

## Live API smoke test

A manually triggered GitHub Actions workflow checks the deployed API's health endpoint, model metadata, frontend CORS preflight, synthetic prediction response, persisted observation history, and invalid-input rejection.

- Workflow: `.github/workflows/live-api-smoke.yml`
- Script: `scripts/smoke-test.mjs`
- Run via GitHub Actions → Live API smoke test → Run workflow.
- The workflow creates synthetic demo records; never send real patient data.

## Roadmap

See [docs/REALTIME_DEMO_ROADMAP.md](docs/REALTIME_DEMO_ROADMAP.md) for phases, acceptance criteria, and current limitations. The planned sequence is durable data storage → WebSocket event delivery → alert lifecycle → patient timeline/data quality → clinical scoring and evaluated ML → explainability → access controls → end-to-end demo hardening.

# VitalGuard AI — Patient Deterioration Early-Warning Prototype

> **DEMO ONLY · SYNTHETIC DATA · NOT FOR CLINICAL USE**
>
> VitalGuard AI is a software prototype for exploring patient-observation monitoring, risk-signal visualisation and alert workflows. The included patients and observations are synthetic. The risk model is a logistic regression trained on the public PhysioNet/CinC 2019 sepsis dataset (seven vital signs); it is a research benchmark, not clinically validated.

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
| `VITALGUARD_AUTH_SECRET` | Backend only. Signs sign-in tokens; set it so sessions survive restarts and work across instances. |
| `VITALGUARD_DEMO_PASSWORD` | Backend only. Shared password of the demo accounts (default `demo-access`). |
| `VITALGUARD_VAPID_PRIVATE_KEY`, `VITALGUARD_VAPID_SUBJECT` | Backend only. Enable Web Push so doctors are notified with the app closed. |

## Current implementation

- React, TypeScript, Vite and Tailwind frontend with dashboard, patient directory/detail, alerts, analytics and settings.
- Existing synthetic patient records, demo simulation controls and local UI persistence.
- FastAPI risk endpoint serving the PhysioNet-trained model, model metadata, held-out test evaluation, coefficient-contribution explanation, bounded observation history and observation quality endpoint.
- SQLAlchemy storage adapter supports local SQLite and PostgreSQL when `DATABASE_URL` is configured. A hosted PostgreSQL instance is not yet confirmed in the live deployment.
- WebSocket event delivery for persisted observations and alerts, with a reconnecting frontend client.
- Persistent demo alert lifecycle (open, acknowledged, resolved) with audit trail.
- Dashboard, patient directory, patient charts, ward board and alerts are driven by the backend cohort stream when it runs (local simulation offline). Patient detail also includes the backend observation/alert/audit timeline and descriptive trends.
- Interactive model evaluation and coefficient-contribution workbench in Settings.
- Source-documented NEWS2 parameter scoring demo endpoint (`POST /api/v1/scores/news2`) and Settings calculator; this is not a clinically validated or approved implementation.
- Unified persisted patient timeline (`GET /api/v1/patients/{patient_id}/timeline`) and descriptive trend endpoint (`GET /api/v1/observations/trends?patient_id=...`).
- Deterministic simulator endpoint for stable, worsening, and recovering fictional observation scenarios.
- Synchronized two-laptop streaming demo (`/#/live-demo`): one producer starts a backend stream session; every signed-in dashboard receives the same committed, backend-scored fictional events, and catches up missed events after reconnecting. See the roadmap, Phase 47.

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

Supported scenarios: `stable`, `worsening`, `recovering`. Step must be between 0 and 1000. The endpoint generates one deterministic observation for the requested scenario and step, runs the active risk model, and persists the resulting observation/prediction using the configured storage adapter.

Example local request:
```bash
curl -X POST http://localhost:8000/api/v1/demo/observations \
  -H 'Content-Type: application/json' \
  -d '{"patient_id":"DEMO-LIVE-001","scenario":"worsening","step":3}'
```

History can be inspected at:
`GET /api/v1/observations?patient_id=DEMO-LIVE-001`

This is a one-observation-per-request simulator, not a continuous device feed. Each request creates a new observation; requests are not idempotent. The backend broadcasts saved observations and alerts over `/api/v1/live`, and every dashboard, patient chart and alert view updates from those events. Durable hosted PostgreSQL configuration remains outstanding.

## Roles, live cohort monitoring, doctor alerts and model benchmark

Full details, setup and results: [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md).

- **Roles.** Sign in as `admin.demo`, `nurse.demo` or a doctor (`doctor.demo` ICU, `dr.khan` Emergency, `dr.mehta` Cardiology, `dr.iyer` General Ward); demo password `demo-access`. The backend issues a signed token and enforces each role on every protected endpoint; the UI hides what a role cannot use.

  | | Admin | Nurse | Doctor |
  | --- | --- | --- | --- |
  | Patients and alerts | all | all | assigned patients only |
  | Start/stop live stream | ✓ | ✓ | – |
  | Acknowledge / resolve alerts | ✓ / ✓ | ✓ / – | ✓ / ✓ (own patients) |
  | Analytics, model performance, model tools | ✓ | – | ✓ |
  | System settings, staff directory | ✓ | – | – |
  | Alert push notifications | – | – | own patients |

- **Live monitoring.** 40 fictional patients (`backend/app/data/cohort.json`, shared by backend and frontend). Starting live monitoring runs a backend *cohort stream*: each tick the backend generates, scores and stores one observation per patient, and every signed-in device's charts, ward board, risk scores and alerts update in real time. A patient raises an alert only when its risk rises into high or critical.
- **Doctor notifications.** Alerts are pushed only to devices registered by the patient's assigned doctor (Web Push, works with the installed app closed when VAPID keys are configured), and shown as a system notification while the app is open.
- **Model benchmark.** Logistic Regression, Random Forest, HistGradientBoosting and XGBoost trained on the open PhysioNet/CinC 2019 sepsis dataset; results in the app under *Model performance* and in `ml/reports/physionet2019_benchmark.json`.

## Progressive Web App

The production build is an installable PWA. It precaches the app shell and static assets and never caches API data. It shows offline and stale-data warnings, and asks before updating. Installation and offline behaviour vary by browser and OS; see [docs/PWA.md](docs/PWA.md) for what has and has not been verified.

## Important limitations

- Without a backend connection the app falls back to a local in-browser simulation that is not shared between devices.
- The served model (StandardScaler + LogisticRegression on seven vitals from a single hour) reaches AUROC 0.65 for sepsis within ~6 hours on held-out PhysioNet patients. Its score is a class-weighted probability, not a calibrated or clinically validated risk. Coefficient contributions are not SHAP explanations or causal attributions.
- The synthetic demo model remains in the registry as the automatic fallback (`previous`).
- WebSocket fan-out is in-process and designed for a single backend instance. Hosted PostgreSQL and production operational safeguards remain deployment work.
- Sign-in uses fictional demo accounts with a shared demo password. Role checks are real, but this is not production identity management (no per-user passwords, MFA or account lifecycle).
- The NEWS2 scoring endpoint follows parameter bands from the RCP chart for demonstration, but the implementation is not clinically validated or approved. The existing local NEWS2-like display also remains a separate synthetic fixture.
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
  timeline_routes.py   Persisted patient timeline
  trend_routes.py      Descriptive observation trends
  news2.py             NEWS2 parameter scoring demonstration
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

Run `npm run smoke:api` to check health, model metadata, frontend CORS preflight, synthetic prediction and persistence, model evaluation, coefficient contributions, NEWS2 scoring/Scale 2 guard, data quality, alert acknowledgement/resolution and audit trail. This writes fictional records to the configured demo database.

- Workflow: `.github/workflows/live-api-smoke.yml`
- Script: `scripts/smoke-test.mjs`
- Run via GitHub Actions → Live API smoke test → Run workflow.
- The workflow creates synthetic demo records; never send real patient data.

## Roadmap

See [docs/REALTIME_DEMO_ROADMAP.md](docs/REALTIME_DEMO_ROADMAP.md) for phases, acceptance criteria, and current limitations. See [docs/RENDER_RELEASE_RUNBOOK.md](docs/RENDER_RELEASE_RUNBOOK.md) for the actual Render service branches, deploy verification, and release smoke-test procedure. The delivered phase status and remaining deployment requirements are tracked in the roadmap. Hosted PostgreSQL, identity/access controls, cross-instance event delivery, and any clinically meaningful model remain outstanding.

# VitalGuard AI — Patient Deterioration Early-Warning Prototype

> **DEMO ONLY · SYNTHETIC DATA · NOT FOR CLINICAL USE**
>
> VitalGuard AI is a software prototype for exploring patient-observation monitoring, risk-signal visualisation and alert workflows. The included patients and observations are synthetic. The current risk signals and NEWS2-like display are demo logic, not a clinically validated prediction system or a substitute for professional judgement.

## Requirements

- Node.js 20 or newer (Node.js 22 LTS recommended)
- npm 10 or newer

## Quick start

```bash
npm ci
cp .env.example .env
npm run dev
```

Vite prints the local URL (normally `http://localhost:5173`).

## Verification commands

Run these from the project root:

```bash
npm run lint    # TypeScript check
npm test        # Vitest suite
npm run build   # TypeScript project build + Vite production bundle
npm run preview # Serve the generated dist/ bundle locally
```

A command should be described as passing only after it has been run successfully against the current source and dependency environment. Previously generated build files are not proof that the current source builds.

## Environment configuration

Copy `.env.example` to `.env` for local development. Vite variables prefixed with `VITE_` are bundled into browser code, so **never store API keys, passwords, tokens, or other secrets in them**.

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_DEMO_MODE` | `true` | Starts in synthetic demo mode unless explicitly set to `false`. |
| `VITE_API_BASE_URL` | production: deployed Render API; local: `http://localhost:8000` | Optional override for the FastAPI risk service. |
| `VITE_APP_VERSION` | `0.1.0-demo` | Version label displayed by the app. |

## Current implementation status

- React, TypeScript, Vite and Tailwind-based frontend.
- Dashboard, patient directory, patient detail, alerts, analytics, settings and not-found pages.
- Eight synthetic patients with sample vital histories, risk signals and alerts.
- Demo simulation controls and local browser persistence for theme and alert status.
- Typed API client for the synthetic risk-prediction and observation-history endpoints.
- Settings → Synthetic risk engine panel to check API health, submit a fixed fictional observation, view model output and browse saved demo predictions.

### Important limitations

- The default experience uses local synthetic data.
- Simulation changes and risk scores are scenario-driven demo values; they are not produced by a trained ML model.
- The prediction demo is integrated with the FastAPI risk service, but the dashboard's patient directory, vitals, alerts and analytics still use local synthetic data. This is a partial integration, not a complete backend-backed application.
- Risk contributors are illustrative. The current NEWS2-like value is not a validated independent NEWS2 calculation.
- No clinical performance, safety, or regulatory validation is claimed.

## Project layout

```text
src/
  data/       Synthetic patients, observations, risk signals and alerts
  pages/      Dashboard, patients, patient detail, alerts, analytics, settings
  services/   Configuration, API client, demo data provider and simulation logic
  store/      React simulation context and initial snapshots
  test/       Vitest and React Testing Library tests
  theme/      Shared risk and chart tokens
  types/      Shared TypeScript data types
  utils/      Formatting helpers
```

## Demo scenarios

The synthetic dataset includes stable, worsening and recovering scenarios. These scenarios are provided to demonstrate the interface and alert flow only; they do not represent clinical advice or validated patient trajectories.

## Development hygiene

- `node_modules/`, `dist/`, local `.env` files and TypeScript build metadata are ignored by Git.
- Commit `.env.example`, not a developer's `.env` file.
- Keep test data synthetic and do not add identifiable patient information.
- Before deployment, verify the build, tests, environment configuration, API failure handling and all key browser workflows.

## Planned next steps

1. Establish a clean, reproducible frontend build and test baseline.
2. Verify core user journeys and responsive layouts.
3. Define the prediction target and dataset for an evaluated ML baseline.
4. Add the FastAPI synthetic risk service with validated request/response contracts.
5. Persist demo predictions in SQLite and expose bounded, filterable observation history.
6. Integrate the Settings risk-engine panel with API health, prediction and history workflows.
7. Complete end-to-end tests and configure persistent storage before treating history as durable.

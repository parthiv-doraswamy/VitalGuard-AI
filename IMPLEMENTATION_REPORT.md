# Implementation report: live cohort monitoring, model training, role-based access, doctor alerts

Branch: `feature/realtime-ml-rbac-push` (based on `main`, which already contains the PWA work)
Date: 15 October 2026

> All patients, vitals and alerts in VitalGuard are fictional. The risk model is trained on
> public research data and is **not clinically validated**. Not for diagnosis, triage or treatment.

## Summary

| Request | What was built | Status |
| --- | --- | --- |
| 1. More patients; live demo changes existing patients' vitals in real time with graphs and alerts | 40-patient shared cohort; backend **cohort stream** updates every patient each tick; all charts, ward board, risk scores and alerts update live on every signed-in device | Done, verified in browser |
| 2. Train on a dataset with XGBoost and other algorithms, show accuracy | PhysioNet/CinC 2019 sepsis dataset; Logistic Regression, Random Forest, HistGradientBoosting, XGBoost (+ NEWS2 and majority baselines); new **Model performance** page; trained model now serves the API | Done (see data coverage note) |
| 3. Roles access only their part of the project | Signed-token sign-in; one permission table drives backend checks, routes, navigation and actions | Done, backend-enforced |
| 4. The installed app notifies the specific doctor in real time | Alerts are pushed only to the assigned doctor's devices (Web Push), plus system notifications while the app is open | Done; push needs VAPID keys on the server |
| Follow-up: remove History tab and dashboard "Synchronized backend stream" / "Phases 5–7" panels | Removed, along with two unused dashboard components | Done |

## 1. Patient cohort and real-time live demo

**Cohort.** `backend/app/data/cohort.json` is the single source of truth, read by both the backend and the
frontend: 40 fictional patients (up from 20) across ICU, Emergency, Cardiology and General Ward, each with a
name, bed, scenario (20 stable, 11 worsening, 9 recovering), baseline vitals and an **assigned doctor**.

**How the live demo works now.**
1. An admin or nurse presses **Start simulation** (top bar) or **Start stream** (Live demo page).
2. The backend starts a *cohort stream session*. Every tick (1–5 s) it generates the next vital signs for
   **every existing patient** (`backend/app/cohort.py`, deterministic per patient and tick), scores each with
   the risk model, stores them and the resulting alerts in one database transaction, and broadcasts them over
   the WebSocket.
3. Every signed-in device applies the events to the shared patient state in one batched render per tick:
   dashboard tables, the patient's vital-sign charts, risk trajectory, NEWS2 (computed from the vitals), the
   new **live ward board** on the Live demo page, and the alert lists.
4. Worsening patients deteriorate at staggered times. A patient raises an alert only when its risk level
   *rises* into high or critical and it has no unresolved alert of that severity, so you get one alert on
   reaching high and at most one more on reaching critical, not one per tick.

A device that opens mid-stream loads the latest committed vitals and alerts first, and a device that
reconnects catches up on missed ticks. Without a backend the app falls back to the local in-browser simulation.

Verified in the browser with the trained model: after starting, deteriorating patients reached HR 139,
SpO₂ 85%, risk 85 (critical); 18 alerts were raised hospital-wide.

## 2. Model training and evaluation

**Dataset.** PhysioNet/Computing in Cardiology Challenge 2019, *Early Prediction of Sepsis from Clinical Data*
(Reyna et al., Crit Care Med 2020), open access, CC BY 4.0. Hourly ICU records; its columns map exactly onto
the seven inputs the VitalGuard API accepts (age, heart rate, SpO₂, systolic/diastolic BP, temperature,
respiratory rate).

**Task.** One prediction per patient-hour. Label `SepsisLabel` = 1 from six hours before clinical sepsis
onset, so a positive means "sepsis within ~6 hours".

**Protocol (fixed before looking at test results).**
- Vitals forward-filled within each patient (past values only); diastolic BP derived from MAP when missing.
- Split **by patient** (no patient in two splits): 70% train / 15% validation / 15% test.
- Each model's decision threshold is chosen on validation (Youden's J); the model is selected by validation
  AUPRC; test results are reported once, afterwards.
- Two feature sets: **7 API vitals** (deployable today) and **vitals + 6-hour trends** (adds trend deltas,
  rolling min/max, MAP, hours in ICU, sex, hospital-to-ICU delay).

**Data coverage.** 25,089 of the 40,336 patient files were downloaded (all of hospital A, ~24% of hospital B)
before PhysioNet began throttling and cutting off downloads. After cleaning: **24,531 patients, 869,341
patient-hours, 1,904 patients with sepsis, 1.98% positive hours.** Test set: 3,651 patients, 130,028 hours.
`ml/download_physionet2019.py` resumes the download; rerun the benchmark afterwards to use the full set.

**Results on held-out test patients**

7 API vitals (deployable):

| Model | Accuracy | Balanced acc. | Sensitivity | Specificity | AUROC (95% CI) | AUPRC |
| --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression (**selected, served**) | 59.8% | 60.8% | 61.9% | 59.7% | 0.651 (0.621–0.678) | 0.038 |
| Random Forest | 59.2% | 60.5% | 61.9% | 59.1% | 0.649 (0.624–0.669) | 0.042 |
| HistGradientBoosting | 60.1% | 61.2% | 62.3% | 60.0% | 0.653 (0.628–0.675) | 0.044 |
| XGBoost | 66.5% | 61.9% | 57.0% | 66.7% | 0.663 (0.640–0.686) | 0.044 |

Vitals + 6-hour trends:

| Model | Accuracy | Balanced acc. | Sensitivity | Specificity | AUROC | AUPRC |
| --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | 75.7% | 67.7% | 59.3% | 76.1% | 0.728 | 0.077 |
| Random Forest (selected for this set) | 72.2% | 71.2% | 70.2% | 72.2% | 0.777 | 0.103 |
| HistGradientBoosting | 69.7% | 69.7% | 69.8% | 69.7% | 0.766 | 0.089 |
| XGBoost | 72.4% | 70.5% | 68.6% | 72.4% | 0.775 | 0.102 |

Baselines: NEWS2 rule (no training) AUROC 0.626; "always no sepsis" **98.0% accuracy with 0% sensitivity**.

**How to read this.**
- **Accuracy alone is misleading.** Only 2% of hours are positive, so predicting "no sepsis" for everyone is
  98% accurate and useless. The app therefore shows balanced accuracy, sensitivity, specificity, AUROC and
  AUPRC next to accuracy.
- **With only seven single-hour vitals, all four algorithms perform alike** (AUROC 0.65–0.66, all above the
  NEWS2 rule). XGBoost is best on test, but the predefined selection rule (validation AUPRC) chose Logistic
  Regression, and it was kept rather than re-picked after seeing test results.
- **Temporal context matters more than the algorithm:** adding 6-hour trends lifts AUROC to ~0.78, where the
  tree models (Random Forest, XGBoost) clearly beat Logistic Regression. Serving that model would need an API
  that accepts observation history, which is a possible next step.

**Integration into the app.**
- The selected model is saved as a verified artifact (`backend/app/model_artifacts/physionet2019-logistic-regression-1.0.0`:
  model, manifest with SHA-256 and provenance, `evaluation.json` with the test metrics) and **promoted to active**
  in the model registry. The synthetic demo model stays as `previous` and is served automatically if the new
  artifact ever fails verification.
- `GET /api/v1/model/info` and `/api/v1/model/evaluation` report the served model and its held-out results;
  Settings → Model evaluation shows them; `/api/v1/risk/explain` coefficient contributions work with it.
- On the live cohort it behaves as intended: stable patients score 31–43, worsening patients rise to 82–85,
  recovering patients fall from ~70 to ~40, so alerts come from genuinely deteriorating vitals.
- The **Model performance** page (admin and doctor) shows the dataset, the tiles for the selected model, the full
  metrics table, ROC curves, AUROC by feature set and XGBoost feature importance.
- Reproducible: `python ml/benchmark_physionet.py --save-artifact` (fixed seeds; two runs gave identical numbers).

## 3. Role-based access

Demo accounts (password `demo-access`):

| Account | Role | Scope |
| --- | --- | --- |
| `admin.demo` | Admin | Everything |
| `nurse.demo` | Nurse | All wards |
| `doctor.demo` (Dr. Asha Rao) | Doctor | ICU patients |
| `dr.khan` (Dr. Imran Khan) | Doctor | Emergency patients |
| `dr.mehta` (Dr. Neha Mehta) | Doctor | Cardiology patients |
| `dr.iyer` (Dr. Karthik Iyer) | Doctor | General Ward patients |

| Capability | Admin | Nurse | Doctor |
| --- | --- | --- | --- |
| Dashboard, patients, alerts | all | all | assigned patients only |
| Live demo page, start/stop stream | ✓ | ✓ | – |
| Acknowledge alert | ✓ | ✓ | own patients |
| Resolve alert | ✓ | – | own patients |
| Analytics, Model performance, model tools in Settings | ✓ | – | ✓ |
| System settings, staff directory | ✓ | – | – |
| Alert push notifications | – | – | own patients |

**Enforcement is on the server**, not just hidden buttons: `POST /api/v1/auth/login` returns an HMAC-signed
token; alerts, patients, staff, stream start and push registration check the role (and, for doctors, the
patient assignment) on every request. The audit trail records the signed-in user, not a name sent by the
browser. The UI uses the same permission table (`src/services/auth.ts`) for routes, navigation, settings panels
and buttons; opening a forbidden page shows "Not available for your role".

## 4. Real-time alert notifications for the assigned doctor

- Every push subscription is registered by a signed-in user. When an alert is created, delivery rows are queued
  **only for devices registered by that patient's assigned doctor**, in the same transaction as the alert.
- With the installed app **closed**, the doctor receives a Web Push notification (requires VAPID keys on the
  server). With the app **open**, the doctor also gets a toast and a system notification over the live
  WebSocket, even without VAPID keys. Both use the same tag, so the doctor never sees the same alert twice.
- Notifications show severity, ward and bed only (no names or vitals, as they can appear on a lock screen).
  Tapping one opens the alert in the app.
- Signing out unregisters the device so the next user does not receive the previous doctor's alerts.

Verified in the browser: across 22 alerts raised hospital-wide, the ICU doctor received exactly the 10
notifications for their own 5 deteriorating ICU patients and none for other wards.

**Doctor setup:** sign in as the doctor on the phone or laptop → install the app (on iPhone: Share → Add to Home
Screen) → Settings → **Enable notifications on this device**.

## 5. Cleanup requested on review

- **History tab removed** entirely (page, route, navigation entry, permission).
- **Dashboard:** removed the "Synchronized backend stream" panel and the "Phases 5–7 · Backend-backed
  monitoring / Operations & model transparency / Phase 7 Model evaluation transparency" block. The model
  evaluation remains available in Settings and on the Model performance page.
- Removed two dashboard components that were no longer used anywhere.

## Configuration

Backend (private environment, never `VITE_` variables):

| Variable | Purpose |
| --- | --- |
| `VITALGUARD_AUTH_SECRET` | Signs sign-in tokens. **Set it in production**, otherwise sessions end on every restart. |
| `VITALGUARD_DEMO_PASSWORD` | Shared demo password (default `demo-access`). |
| `VITALGUARD_VAPID_PRIVATE_KEY`, `VITALGUARD_VAPID_SUBJECT` | Enable Web Push. Generate with `python backend/scripts/generate_vapid_keys.py`. |

The database migrates itself on startup (new migration v7). Restart any running backend to load the new model.

## Verification

| Check | Result |
| --- | --- |
| Backend tests (`cd backend && pytest -q`) | 234 passed, 64 skipped (PostgreSQL-only) |
| ML pipeline tests (`PYTHONPATH=backend pytest ml/tests`) | 46 passed |
| Frontend lint, tests, production build | lint clean, 84 tests passed, build OK |
| API smoke test against a local backend (`npm run smoke:api`) | all checks passed, including sign-in and the active model's evaluation |
| Manual browser walk-through (admin, nurse, doctor) | dashboard, patients, live stream, alerts, model performance, settings, role restrictions and doctor notifications confirmed |

New tests cover sign-in and token tampering, doctor patient scoping, nurse/doctor alert permissions, cohort
stream idempotency and alert de-duplication, push targeting to the assigned doctor, live-event ingestion,
NEWS2 from vitals and the login/route guards.

**Not run locally:** the Playwright end-to-end suite (`@playwright/test` is installed by CI, not in this
project's dependencies). Its live-demo spec was updated for the new stream modes and gained a cohort test.

## Known limitations and next steps

- Demo accounts share one password. Roles are enforced, but this is not production identity management.
- The session is per browser: signing in as a doctor in one tab signs every tab of that browser in as that
  doctor. Demo two roles with two browsers, a private window, or two devices.
- Web Push needs HTTPS, VAPID keys and, on iPhone/iPad, the app added to the Home Screen.
- Model training used about 62% of the PhysioNet patient files (download throttling); rerun after completing the download.
- The served model sees one hour of vitals; trend-aware models (AUROC ~0.78) would need an API that accepts history.

## Commits on this branch

`git log --oneline main..feature/realtime-ml-rbac-push` lists them; the main ones are the backend
(auth, cohort stream, push targeting), the frontend (roles, live monitoring, notifications), the model
benchmark and integration, and the History/dashboard cleanup.

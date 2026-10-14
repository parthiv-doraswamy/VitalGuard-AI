# Datasets, target definition and field mapping

> **Status (2026-10-14): real-dataset training is BLOCKED.** This repository has no
> approved access to MIMIC-IV, eICU or any other clinical dataset. No clinical data
> has been downloaded, used or committed. Every model and metric produced so far
> comes from generated data, and none of it is a clinical performance claim.

## 1. Prediction task (defined before choosing data)

| Item | Definition (`ml/config.yaml`, `target.id: inhospital-death-within-24h-v1`) |
| --- | --- |
| Population | Adult (age ≥ 18) ICU stays. |
| Prediction time | Every 4 h during the ICU stay, starting 4 h after ICU admission. At most 42 per stay. None at or after death or ICU discharge. |
| Inputs | The 7 API features: age, heart rate, SpO₂, systolic BP, diastolic BP, temperature, respiratory rate. Each uses the most recent valid value that was **stored** (`max(charttime, storetime)`) at or before the prediction time, within a lookback of 4 h (8 h for temperature). Nothing recorded after the prediction time is used. |
| Outcome | 1 if in-hospital death (`admissions.deathtime`) occurs **after** the prediction time and **≤ 24 h** after it, otherwise 0. |
| Inclusion | All 7 features valid at the prediction time (complete case). Missingness and the label rate of excluded rows are reported. |
| Known limitations | Deaths after hospital discharge are not observed (labelled 0). Death is a narrow proxy for deterioration: unplanned ICU transfer, rapid-response calls and vasopressor start are not captured. Complete-case exclusion can bias towards well-monitored patients. Prediction times within one stay are correlated, which the patient-level bootstrap accounts for. |

Before any real training, a clinical reviewer should approve these definitions. Change `target.id` and `config_version` whenever they change.

## 2. Candidate datasets

| Dataset | Access | Fit | Status here |
| --- | --- | --- | --- |
| **MIMIC-IV** (v3.x, PhysioNet) | Credentialed PhysioNet account, CITI "Data or Specimens Only Research" training, signed data use agreement. No sharing of records; use only for permitted research. | ICU vitals in `icu/chartevents`, death times in `hosp/admissions`. `anchor_year_group` gives an approximate period for temporal splits. | **Blocked: no access.** Adapter implemented (`mimic_iv` experiment). |
| MIMIC-IV Clinical Database Demo (PhysioNet) | Openly downloadable, Open Database License. 100 patients. | Same schema; useful only for checking the adapter against real-format files. Far too small for performance estimates. | Not downloaded. Adapter would accept it (`mimic_iv_demo`). |
| eICU-CRD (PhysioNet) | Credentialed access, same as MIMIC. | Multi-centre ICU; vitals in `vitalPeriodic`/`vitalAperiodic`, mortality in `patient`. Would allow hospital-level external validation. | Not implemented; needs its own adapter (mapping below). |

The pipeline never downloads data. To run on an approved copy:

```bash
export MIMIC_IV_DIR=/secure/path/mimic-iv-3.1      # contains hosp/ and icu/ (.csv or .csv.gz)
python ml/prepare_dataset.py --experiment mimic_iv --confirm-approved-access
python ml/train.py --experiment mimic_iv --check-reproducible
python ml/evaluate.py --artifact ml/artifacts/<printed model_version>
```

`--confirm-approved-access` is an operator attestation that is recorded in the dataset manifest. It does not prove access. Keep the dataset, the prepared rows (`ml/runs/`) and the artifacts (`ml/artifacts/`) inside the approved environment; all three are git-ignored. Do not upload them to this repository, CI or hosted services.

## 3. Field mapping (MIMIC-IV → API feature schema)

| API feature | MIMIC-IV source | Unit handling | Valid range (else dropped) |
| --- | --- | --- | --- |
| `age` | `patients.anchor_age + (year(admittime) − anchor_year)` | years | 18–110 |
| `heart_rate` | chartevents itemid 220045 | bpm | 20–250 |
| `spo2` | 220277 (O₂ saturation pulse oximetry) | % | 50–100 |
| `systolic_bp` | 220179 (NIBP) or 220050 (arterial), latest wins | mmHg | 50–280 |
| `diastolic_bp` | 220180 (NIBP) or 220051 (arterial), latest wins | mmHg | 20–180 |
| `temperature` | 223762 (°C); 223761 (°F → (°F−32)×5/9; values < 50 under the °F item are treated as already °C and counted) | °C | 30–45 |
| `respiratory_rate` | 220210 | breaths/min | 3–70 |

eICU-CRD equivalents (adapter not built): `vitalPeriodic.heartrate`, `sao2`, `respiration`, `temperature`; `systemicsystolic`/`systemicdiastolic` plus `vitalAperiodic.noninvasivesystolic`/`noninvasivediastolic`; `patient.age` ("> 89" needs handling); death from `patient.unitdischargestatus`/`hospitaldischargestatus` with offsets.

Validation applied by `prepare_dataset.py`, with every count written to `data_quality.json`:
- Required tables and columns must exist; timestamps must parse.
- Exact duplicate events are removed.
- Non-numeric values and implausible values are dropped.
- Diastolic ≥ systolic invalidates both BP values for that row.
- The missing rate for each feature is reported before complete-case exclusion, together with the label prevalence of the excluded rows. A different prevalence there indicates selection bias.

## 4. Splits and leakage controls

- **By patient:** all rows of a patient are in exactly one of train, validation or test (`patient_hash`, SHA-256 of `seed:patient_id`). The training and evaluation scripts re-check this and fail on any overlap.
- **By time (MIMIC-IV):** the `mimic_iv` experiment holds out the `2017 - 2019` `anchor_year_group` as the test set (`patient_group`). MIMIC-IV shifts dates per patient, so calendar dates cannot be compared across patients; the year group is the only usable period signal.
- **Features:** as-of joins on availability time, with lookback windows (§1).
- **Model selection:** C and the decision threshold are chosen on validation only. Evaluation uses the stored threshold and refuses to run if the dataset hash or the train/validation patient sets differ from training.

## 5. Synthetic data in this repository

| Name | What it is | Allowed use |
| --- | --- | --- |
| `synthetic_demo` | `backend/app/synthetic_data.py`: generated vitals with labels from a hand-written heuristic. No patients or time. | Training the demo API's model only. |
| `mimic_format_fixture` | `ml/fixtures.py`: fictional patients written in MIMIC-IV table layout, with injected data problems. Marked with `SYNTHETIC_FIXTURE.txt`. | Testing the real-data code path. **Its metrics are meaningless.** The pipeline refuses to label it as anything but `synthetic-fixture`, and refuses fixture experiments on unmarked directories. |

# VitalGuard AI — ML training pipeline

> No clinical model has been trained. Real-dataset training is **blocked** pending
> approved data access (see [data/README.md](data/README.md)). The API serves a
> synthetic demo model, which is not clinically validated.

## Layout

| File | Purpose |
| --- | --- |
| `config.yaml` | Versioned definitions: features, target, prediction times, inclusion, split, model search, threshold policy, evaluation, and experiments. |
| `prepare_dataset.py` | MIMIC-IV-format tables → validated, leakage-safe prediction rows, plus a dataset manifest and quality report. |
| `train.py` | Baseline training (StandardScaler + LogisticRegression, as in the API) and the synthetic demo artifact. |
| `evaluate.py` | One-time held-out test evaluation with the stored threshold. |
| `fixtures.py` | Fictional MIMIC-format fixture generator (for testing only). |
| `tests/` | Leakage, missingness, invalid data, feature order, reproducibility and serialization tests. |

Setup: `pip install -r ml/requirements.txt` (adds pandas and PyYAML to the backend requirements; the deployed API does not need them).

## Commands

```bash
# Rebuild the committed demo API artifact (synthetic data only).
python ml/train.py --experiment synthetic_demo

# Exercise the real-data path end to end on fictional MIMIC-format data.
python ml/prepare_dataset.py --experiment mimic_format_fixture --generate-fixture
python ml/train.py --experiment mimic_format_fixture --check-reproducible
python ml/evaluate.py --artifact ml/artifacts/<model_version printed by train.py>

# Approved MIMIC-IV access only (blocked here).
MIMIC_IV_DIR=... python ml/prepare_dataset.py --experiment mimic_iv --confirm-approved-access

# Tests (from the repository root).
PYTHONPATH=backend pytest ml/tests -q
```

## Versioning

- **Dataset version:** `<experiment>-<first 12 hex of SHA-256(dataset.csv)>`. The manifest records the config hash, target, feature definitions, split settings, per-split counts and patient-set hashes, the source directory name (not its path), the git commit, and whether access was confirmed.
- **Model version:** `logreg-baseline-<experiment>-<dataset hash[:8]>-<config hash[:8]>`. The same data and config give the same version.
- **Run:** a unique `run_id`, seed, `random_state`, selected C, the full validation search, coefficients and git commit.
- **Reproducibility:** `--check-reproducible` trains twice and fails unless coefficients, intercept, scaler and threshold agree within `reproducibility.abs_tolerance` (1e-9). Logistic regression with lbfgs is deterministic, so in practice the results are identical.

## Model artifacts

An artifact directory contains `model.joblib` (the whole fitted Pipeline, so preprocessing travels with the model), `manifest.json`, and `evaluation.json` / `evaluation.md`. The backend loader (`backend/app/model_artifact.py`) checks the following before use:

1. format version;
2. exact feature names **and order**;
3. the identical scikit-learn version (pickles are not portable across versions);
4. the SHA-256 of `model.joblib` against the manifest, and optionally against `VITALGUARD_MODEL_SHA256`;
5. that the loaded model reproduces the manifest's reference probabilities (tolerance 1e-9).

joblib uses pickle, which can execute code: load artifacts only from trusted locations.

**Committed:** only `backend/app/model_artifacts/synthetic-logreg-0.1.0/` (about 1.5 KB). It is identical to the model the API used to train at import; a regression test compares predictions to 1e-12.
**Never committed:** `ml/artifacts/`, `ml/runs/` and `ml/data/fixtures/`, which may hold record-level data.

## How the API uses a model

- The API loads `VITALGUARD_MODEL_ARTIFACT` (default: the committed demo artifact) at startup. It never trains at import.
- **Fallback:** if the artifact is missing or fails a check, the API rebuilds the identical synthetic demo model in-process and reports `model_source: "fallback-synthetic-training"` and `load_error` in `/api/v1/model/info`. `VITALGUARD_MODEL_REQUIRE_ARTIFACT=true` makes startup fail instead.
- **Promotion guard:** the API refuses artifacts whose dataset kind is not `synthetic-demo` unless `VITALGUARD_ALLOW_NON_DEMO_MODEL=true`. Research artifacts, including fixture ones, cannot be served by accident.
- Do not replace the deployed model unless all of these hold: the new artifact passes the backend loader, the API regression tests (`backend/tests`) and the live API smoke test; it has a reviewed evaluation report; and a clinical/governance sign-off exists for whatever use is claimed.

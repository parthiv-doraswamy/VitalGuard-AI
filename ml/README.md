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
| `model_registry.py` | Candidate catalogue (logistic regression, Random Forest, XGBoost) and the deployed-artifact registry (promote / rollback). |
| `metrics.py` | Shared validation/test metrics, calibration, and patient-level (paired) bootstraps. |
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

## Benchmarking candidate algorithms

```bash
python ml/train.py --experiment <experiment> --benchmark           # trains all candidates, freezes the selection
python ml/evaluate.py --benchmark ml/artifacts/benchmarks/<id>      # test evaluation + comparison report
```

**Protocol** (`candidates` and `selection` in `config.yaml`, fixed before training):
- Every candidate is fitted by the same function on the same rows, feature order and patient-level split.
- Hyperparameters, and the decision threshold (sensitivity ≥ 0.80), are chosen on the validation split only. The comparison checks that all candidates share the dataset hash, features, train/validation patient hashes and config hash.
- **Gates** (validation data and the deployed runtime):
  - the model can be loaded by the backend's pinned dependencies;
  - single-row p95 latency ≤ 25 ms;
  - artifact ≤ 5 MB;
  - validation sensitivity ≥ 0.75;
  - |calibration slope − 1| ≤ 0.5.
- **Rule:** keep the logistic-regression baseline unless a gated candidate improves validation PR-AUC by ≥ 0.02 **and** the patient-level paired-bootstrap 95% CI of that improvement excludes zero. Ties go to the simpler model. If the baseline itself fails a gate, the eligible candidate with the best validation PR-AUC is chosen. A model is never chosen for raw accuracy or complexity.
- `selection.json` is written (and hashed) **before** any test evaluation. `evaluate.py --benchmark` refuses to run if a candidate manifest changed after the freeze.
- Test metrics are computed from saved `test_predictions.csv` files, so every reported number can be recomputed.
- The chosen artifact's manifest gets a `selection` block, and the comparison report is copied next to it.

**XGBoost** is installed for benchmarking (`ml/requirements.txt`) but is **not** a dependency of the deployed API. The deployability gate therefore excludes it unless `xgboost` is deliberately added to `backend/requirements.txt` after review.

**Result so far (2026-10-14):** only the fictional fixture has been benchmarked, which demonstrates the procedure, not performance. The baseline was kept: Random Forest's validation PR-AUC gain was −0.058 (CI −0.164 to 0.000), and XGBoost failed the deployability gate. No algorithm has been selected for the real target, because real-dataset training is blocked.

## Deployed model registry and rollback

`backend/app/model_artifacts/registry.json` names the `active` artifact and the `previous` one.

```bash
python ml/model_registry.py status | candidates
python ml/model_registry.py promote <artifact_dir> [--allow-research-artifact]
python ml/model_registry.py rollback
```

- **Promote** verifies the artifact with the backend loader, copies it into the store, and keeps the old active version as `previous`.
- Fixture artifacts are never promotable. Research artifacts need `--allow-research-artifact` here **and** `VITALGUARD_ALLOW_NON_DEMO_MODEL=true` on the API.
- **Rollback** re-verifies `previous` and makes it active.
- At startup, if the active artifact fails verification, the API serves `previous` automatically (`model_source: "artifact-previous-after-active-failed"`), and only then falls back to rebuilding the synthetic model.
- Commit a registry change only after the backend tests and the live API smoke test pass on it.

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

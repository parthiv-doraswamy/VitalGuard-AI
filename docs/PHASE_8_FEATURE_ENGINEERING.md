# Phase 8 — Feature engineering contract

**Status:** Specification and release gate. No production or clinical feature set is claimed to be implemented by this document.

## Purpose

Define a reproducible, testable feature contract for the synthetic VitalGuard risk demo before changing the model input vector. This phase does not add real-patient data, external datasets, or a clinically deployable score.

## Current baseline

The current classifier in `backend/app/model.py` consumes seven direct input fields in this order:

1. `age`
2. `heart_rate`
3. `spo2`
4. `systolic_bp`
5. `diastolic_bp`
6. `temperature`
7. `respiratory_rate`

It uses `StandardScaler` followed by `LogisticRegression`, trained from generated observations and heuristic labels. The model version is `synthetic-logreg-0.1.0`. This is a software demonstration, not a validated probability of deterioration.

## Feature contract

Any future engineered feature must have a stable name, source fields, units, calculation, missing-data behavior, valid range, timestamp semantics, and test cases. The same transformation must be used for training, offline evaluation, and inference. Do not independently reimplement formulas in separate code paths.

| Feature family | Candidate for synthetic experiments | Contract / guardrail |
| --- | --- | --- |
| Current observation | Existing seven raw fields | Preserve schema units and existing validation; never silently reinterpret units. |
| Change from prior reading | Delta and elapsed time for a field | Require at least two valid readings for the same demo subject; sort by observation timestamp; reject negative elapsed time; define behavior for zero elapsed time. |
| Rolling summaries | Mean, minimum, maximum, and slope over a fixed window | Use only readings at or before prediction time; require a declared minimum count; return missing rather than inventing a value. |
| Missingness / freshness | Count of absent fields and age of latest reading | Keep data-quality indicators distinct from physiology; do not treat missing as normal. |
| Provenance / quality | Timestamp validity and source validation flags | Use for gating or quality reporting, not as hidden shortcuts to the target label. |

Candidate families are design options only; they are not yet model inputs.

## Temporal correctness and leakage prevention

- Define prediction time explicitly for every training example.
- A feature may use only observations available at or before that prediction time.
- Split synthetic evaluation data by subject/episode before generating overlapping windows; do not randomly distribute adjacent windows from the same episode across train and holdout.
- Fit scalers, imputers, selectors, and other learned transformations on training data only.
- Never use labels, future observations, alert outcomes, or post-event data as predictors.
- Record the source event IDs and time window used to produce each derived row.
- Keep feature generation deterministic and version it alongside the model.
- Test shuffled input order, duplicate timestamps, gaps, missing fields, invalid timestamps, and boundaries.

## Missing values and units

- Do not silently impute a missing vital sign to a normal-looking value.
- Any imputation policy must be explicit, fitted only on training data where applicable, and evaluated as part of the model pipeline.
- Normalize units only through explicit, tested conversions. Reject unknown or ambiguous units.
- Preserve both the observation timestamp and the time the system received it when source metadata is available; never assume delayed data was available at prediction time.
- Keep data-quality failures observable rather than hiding them in preprocessing.

## Proposed implementation sequence

1. Freeze the current seven-feature baseline and capture deterministic regression tests.
2. Implement a pure feature-builder function with an explicit input/output schema and feature-set version.
3. Add unit tests for formulas, temporal windows, missingness, ordering, duplicates, and leakage boundaries.
4. Add a reproducible synthetic dataset generator that groups observations by fictional subject and episode.
5. Add subject/episode-level train/validation/test splitting before any windowing or preprocessing.
6. Compare a candidate feature set to the unchanged baseline on the same held-out synthetic subjects; report class balance, confusion matrix, precision, recall, F1, ROC-AUC where defined, and calibration limitations.
7. Integrate a feature set only after tests and evaluation are reviewed; bump model and feature-set versions together.
8. Run backend CI and a live synthetic smoke test; verify database persistence independently.

## Acceptance criteria

- [ ] Feature names, order, units, and version are explicit.
- [ ] Training and inference share one transformation implementation.
- [ ] Tests prove no future observation contributes to a feature.
- [ ] Subject/episode splits prevent overlap leakage.
- [ ] Preprocessing is fitted on training data only.
- [ ] Missingness and unknown units fail safely.
- [ ] Evaluation results are reproducible and explicitly labeled synthetic.
- [ ] Existing API response shape remains backward-compatible or is versioned.
- [ ] CI passes and the deployed version is verified before declaring release.

## Safety and scope

All examples and test data must remain fictional and synthetic. No real patient information or external clinical dataset is to be imported as part of this phase. Any future clinical dataset use requires documented permissions, privacy/security review, governance approval, and appropriate expert oversight. Better synthetic metrics do not establish clinical validity or safety.

# Phase 9 — Risk engine and model validation

**Status:** Validation protocol and synthetic engineering evaluation are in progress. No clinical validation is claimed.

## Current model boundary

The serving model is `synthetic-logreg-0.1.0`: a `StandardScaler + LogisticRegression` pipeline trained on generated observations and heuristic-derived labels. The current response exposes a score and model probability for demonstration only. These values are not a clinically calibrated probability of deterioration.

The Phase 8 temporal feature builder and subject-grouped baseline-versus-candidate evaluator are separate from the serving model. Do not promote candidate features merely because synthetic metrics improve.

## Validation layers

### Layer A — Software correctness (required now)

- Deterministic training-data generation and evaluation seeds.
- Strict schema validation, finite numeric inputs, explicit model and feature-set versions.
- Unit tests for feature ordering, prediction-time cutoffs, missingness, timestamp boundaries and reproducibility.
- Model artifact/feature schema compatibility checks.
- API contract tests and authorization tests.
- Regression test that the live serving feature vector remains the seven existing raw features until a deliberate versioned promotion.

### Layer B — Synthetic engineering evaluation (demo only)

- Compare baseline and candidate feature sets on identical subject-disjoint splits.
- Split fictional subjects/episodes before building overlapping temporal windows.
- Fit preprocessing only on the training partition.
- Report sample counts, class prevalence, confusion matrix, accuracy, precision, recall, F1 and ROC-AUC.
- For probability outputs, report Brier score and calibration-bin counts/observed positive fractions; label them synthetic-only.
- Report exploratory subgroup metrics by age band and class counts; suppress or flag small groups rather than overinterpreting noisy estimates.
- Use fixed seeds and record the feature set, model version, split method and label-generation rule.
- Do not choose a threshold based on the holdout set. Threshold selection belongs to training/validation data and must be frozen before final testing.

### Implemented synthetic diagnostics

- Authenticated endpoint: `GET /api/v1/model/validation-diagnostics`.
- Reports Brier score, five calibration bins with counts and observed positive fractions, ROC-AUC, and age-band precision/recall with sample and positive-label counts.
- Uses a fixed subject-disjoint synthetic holdout; unavailable subgroup metrics include a reason when the sample is too small or only one label class is present.
- The fixed 0.5 threshold is a demo convention, not a selected or approved clinical threshold. This endpoint is a software diagnostic and does not alter the serving model.

### Layer C — Independent clinical validation (not possible from this repository alone)

Requires an approved intended use, prespecified outcome and prediction horizon, lawful and governed data access, representative patient-level data, independent site/time-based test cohort, clinician-adjudicated outcomes, subgroup analysis, calibration assessment, prospective workflow evaluation, safety monitoring and independent clinical/statistical review. This phase cannot fabricate these inputs or substitute synthetic metrics for them.

## Probability and threshold caveats

- Logistic regression output is a model score transformed to a probability under the synthetic training distribution; it is not automatically calibrated to a real population.
- The current displayed integer risk score is a rounded synthetic model output, not a validated clinical risk category.
- Thresholds for alert creation are engineering constants, not approved clinical thresholds.
- ROC-AUC and other metrics against heuristic labels quantify agreement with the label-generation process only.
- Synthetic data may encode the same assumptions used to generate labels, so even strong scores can be misleading.

## Subgroup reporting rules

- Predefine age bands and any other relevant groups before inspecting results.
- Always report group sample count and positive-label count alongside metrics.
- Do not report a metric when the group has too few examples or only one label class; return an explicit unavailable reason.
- Treat differences between synthetic subgroups as software diagnostics, not fairness or safety findings.
- Real-world fairness assessment requires authorized, representative data and a reviewed protocol; sensitive attributes must not be inferred or added casually.

## Model promotion gate

A new model/feature set may not replace the serving baseline until:
1. Feature schema and transformation versions are explicit and tested.
2. Baseline and candidate use the same subject-disjoint evaluation partition.
3. Preprocessing is fitted on training data only.
4. Leakage, missingness, timestamp, duplicate, and out-of-distribution tests pass.
5. Evaluation reports metrics, class balance, confusion matrix, calibration caveats, and subgroup counts.
6. The candidate's synthetic limitations and model version are documented.
7. API compatibility, CI and staged deployment checks pass.
8. For any intended clinical use, separate independent clinical, privacy, security, usability and regulatory approval is completed before use.

## Current decision

**Do not promote the temporal candidate into the live classifier.** The candidate evaluator is a synthetic engineering experiment. PostgreSQL persistence and deployed API verification also remain independent release blockers.

# Phase 7 — Reproducible model evaluation

## Endpoints
- `GET /api/v1/model/evaluation`: deterministic stratified 25% synthetic holdout report with accuracy, precision, recall, F1, ROC-AUC and confusion matrix.
- `POST /api/v1/risk/explain`: returns standardized logistic-regression coefficient contributions for the submitted synthetic vital-sign vector.

## Interpretation
The training labels are generated from a hand-crafted heuristic plus seeded noise. These metrics measure agreement with that synthetic label-generation process only. They are not clinical accuracy, sensitivity to deterioration, calibration, or evidence of safety.

Coefficient contributions are additive contributions to the model's linear log-odds before the logistic transformation. They are not SHAP values, causal effects, or medical explanations.

## Reproducibility
The generator seed, holdout split seed, sample count and evaluation method are fixed in code. Any change to the synthetic label-generation rule or model pipeline should increment the model version and rerun tests.

Synthetic demonstration only; not for diagnosis, triage, treatment, or real patient data.

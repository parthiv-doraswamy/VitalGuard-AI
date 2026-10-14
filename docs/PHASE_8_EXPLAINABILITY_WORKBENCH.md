# Phase 8 — Explainability workbench

Settings includes an interactive synthetic-vitals form that calls `POST /api/v1/risk/explain`. It displays the model score and signed standardized logistic-regression coefficient contributions, sorted by absolute magnitude.

The form validates the systolic/diastolic relationship before submitting. It does not create or persist a prediction record.

Contributions are components of the linear model's log-odds. They are not SHAP values, causal explanations, validated clinical indicators, or medical advice. This feature uses synthetic examples only.

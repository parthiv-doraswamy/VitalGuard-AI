# Phase 10 — Explainability quality and limits

**Status:** Additive explanation consistency checks implemented for the synthetic demo. No clinical validation is claimed.

## Existing explanation surface

- `GET /api/v1/model/info` identifies the serving model and its synthetic-only training boundary.
- `POST /api/v1/risk/explain` returns standardized logistic-regression coefficient contributions.
- These contributions describe how each standardized input contributes to the fitted model's log-odds relative to its intercept. They are not causal effects, feature importance validated in a clinical population, or clinical recommendations.

## Implemented quality gate

- `backend/app/explanation_validation.py` reconstructs model log-odds from the model intercept plus all seven additive contributions.
- It compares reconstructed log-odds with the log-odds implied by the model probability, with a configurable finite positive tolerance.
- Missing and non-finite inputs are rejected.
- Unit tests cover reconstruction, numerical tolerance, invalid inputs, and the explicit non-causal caveat.

## Interpretation rules

1. Keep explanation feature names, model version, and contribution units explicit.
2. Do not phrase associations as causes or treatment recommendations.
3. Do not claim that a large contribution is clinically important; it is a property of this fitted synthetic model.
4. The model probability is not a clinically calibrated probability of deterioration.
5. Do not change thresholds, alert behavior, or the serving model based on explanation output alone.

## Not yet addressed

This check validates additive arithmetic, not explanation faithfulness under perturbation, stability under measurement noise, clinician comprehension, workflow usability, or clinical validity. Those require separate tests and, for any intended clinical use, independently governed validation.

**Decision:** Keep the serving model unchanged and label all outputs as synthetic demonstration only.

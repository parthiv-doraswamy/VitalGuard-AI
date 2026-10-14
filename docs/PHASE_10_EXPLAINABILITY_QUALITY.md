# Phase 10 — Explainability consistency and quality

## Scope

The explanation endpoint now returns an additive reconstruction check for the currently serving model when it supports standardized logistic regression.

## Contract

- Reconstruct log-odds from the fitted intercept plus the sum of standardized feature contributions.
- Compare the result with log-odds derived from the same model's predicted probability using a finite, positive tolerance.
- Reject missing, non-numeric, and non-finite feature values and invalid tolerances.
- If the active model does not support this decomposition, report the check as unavailable rather than pretending it passed.
- The release smoke test verifies that a supported model passes the reconstruction tolerance.

## Limits

This validates arithmetic consistency only. It does not establish causal explanations, feature faithfulness, calibration, clinical validity, or safety. The serving model and risk thresholds are unchanged. Use synthetic examples only.

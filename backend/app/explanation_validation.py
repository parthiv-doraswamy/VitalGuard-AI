"""Quality checks for additive model explanations in the synthetic demo."""
from __future__ import annotations

import math
import numpy as np

from .model import FEATURES, MODEL, MODEL_VERSION


def validate_additive_explanation(values: dict[str, float], *, tolerance: float = 1e-6) -> dict[str, object]:
    """Check that standardized feature contributions reconstruct model log-odds.

    This verifies the mathematics of the fitted logistic-regression pipeline;
    it does not establish causal meaning, clinical validity, or correctness of
    the synthetic labels.
    """
    if tolerance <= 0 or not math.isfinite(tolerance):
        raise ValueError("tolerance must be a finite positive number")
    missing = [feature for feature in FEATURES if feature not in values]
    if missing:
        raise ValueError(f"missing required features: {', '.join(missing)}")
    row = np.asarray([[values[name] for name in FEATURES]], dtype=float)
    if not np.isfinite(row).all():
        raise ValueError("all explanation inputs must be finite")
    scaler = MODEL.named_steps["scale"]
    classifier = MODEL.named_steps["classifier"]
    standardized = scaler.transform(row)[0]
    contributions = standardized * classifier.coef_[0]
    intercept = float(classifier.intercept_[0])
    reconstructed_log_odds = intercept + float(contributions.sum())
    probability = float(MODEL.predict_proba(row)[0, 1])
    probability_log_odds = math.log(probability / (1.0 - probability))
    absolute_error = abs(reconstructed_log_odds - probability_log_odds)
    return {
        "model_version": MODEL_VERSION,
        "method": "standardized logistic-regression additive log-odds decomposition",
        "intercept": round(intercept, 8),
        "contribution_sum": round(float(contributions.sum()), 8),
        "reconstructed_log_odds": round(reconstructed_log_odds, 8),
        "probability_derived_log_odds": round(probability_log_odds, 8),
        "absolute_error": round(absolute_error, 10),
        "tolerance": tolerance,
        "passed": absolute_error <= tolerance,
        "interpretation": "Mathematical consistency check only; contributions are not causal explanations or clinical guidance.",
        "demo_only": True,
        "clinically_validated": False,
    }

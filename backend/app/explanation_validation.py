"""Quality checks for additive explanations from the currently serving demo model."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from .model import FEATURES, active_model


def validate_additive_explanation(values: dict[str, Any], *, tolerance: float = 1e-6) -> dict[str, object]:
    """Check log-odds reconstruction for a standardized logistic-regression model.

    This is a mathematical consistency check only; it does not validate the
    model's data, labels, clinical meaning, calibration, or safety.
    """
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be a finite positive number")

    missing = [feature for feature in FEATURES if feature not in values or values[feature] is None]
    if missing:
        raise ValueError(f"missing required features: {', '.join(missing)}")

    try:
        row = np.asarray([[float(values[name]) for name in FEATURES]], dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("all explanation inputs must be finite numeric values") from exc
    if not np.isfinite(row).all():
        raise ValueError("all explanation inputs must be finite numeric values")

    model = active_model()
    if not model.supports_coefficient_contributions:
        return {
            "model_version": model.version,
            "available": False,
            "passed": None,
            "reason": "The active model does not support additive logistic-regression contributions.",
            "demo_only": True,
            "clinically_validated": False,
        }

    pipeline = model.pipeline
    scaler = pipeline.named_steps["scale"]
    classifier = pipeline.named_steps["classifier"]
    standardized = scaler.transform(row)[0]
    contributions = standardized * classifier.coef_[0]
    intercept = float(classifier.intercept_[0])
    reconstructed = intercept + float(contributions.sum())
    probability = float(model.predict_proba(dict(zip(FEATURES, row[0]))))
    # Avoid infinities when a model probability is numerically rounded to 0 or 1.
    clipped_probability = min(max(probability, 1e-15), 1 - 1e-15)
    probability_log_odds = math.log(clipped_probability / (1.0 - clipped_probability))
    error = abs(reconstructed - probability_log_odds)

    return {
        "model_version": model.version,
        "available": True,
        "method": "standardized logistic-regression additive log-odds decomposition",
        "intercept": round(intercept, 8),
        "contribution_sum": round(float(contributions.sum()), 8),
        "reconstructed_log_odds": round(reconstructed, 8),
        "probability_derived_log_odds": round(probability_log_odds, 8),
        "absolute_error": round(error, 10),
        "tolerance": tolerance,
        "passed": error <= tolerance,
        "interpretation": "Mathematical consistency only; contributions are not causal explanations or clinical guidance.",
        "demo_only": True,
        "clinically_validated": False,
    }

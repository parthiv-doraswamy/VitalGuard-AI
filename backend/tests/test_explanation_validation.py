import math
import pytest

from app.explanation_validation import validate_additive_explanation


VALUES = {
    "age": 58, "heart_rate": 82, "spo2": 98, "systolic_bp": 122,
    "diastolic_bp": 78, "temperature": 37.0, "respiratory_rate": 16,
}


def test_additive_explanation_reconstructs_model_log_odds():
    report = validate_additive_explanation(VALUES)
    assert report["passed"] is True
    assert report["absolute_error"] <= report["tolerance"]
    assert report["demo_only"] is True
    assert report["clinically_validated"] is False
    assert "not causal" in report["interpretation"]


def test_explanation_validation_rejects_missing_or_non_finite_values():
    with pytest.raises(ValueError, match="missing required features"):
        validate_additive_explanation({"age": 58})
    invalid = {**VALUES, "spo2": math.nan}
    with pytest.raises(ValueError, match="finite"):
        validate_additive_explanation(invalid)


def test_explanation_validation_rejects_invalid_tolerance():
    with pytest.raises(ValueError, match="finite positive"):
        validate_additive_explanation(VALUES, tolerance=0)

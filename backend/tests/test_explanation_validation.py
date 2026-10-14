import math

import pytest

from app.explanation_validation import validate_additive_explanation


VALUES = {
    "age": 58,
    "heart_rate": 82,
    "spo2": 98,
    "systolic_bp": 122,
    "diastolic_bp": 78,
    "temperature": 37.0,
    "respiratory_rate": 16,
}


def test_additive_explanation_reconstructs_active_model_log_odds():
    result = validate_additive_explanation(VALUES)
    assert result["available"] is True
    assert result["passed"] is True
    assert result["absolute_error"] <= result["tolerance"]
    assert result["demo_only"] is True
    assert result["clinically_validated"] is False
    assert "not causal" in result["interpretation"]


def test_explanation_check_rejects_missing_values():
    with pytest.raises(ValueError, match="missing required features"):
        validate_additive_explanation({"age": 58})
    with pytest.raises(ValueError, match="missing required features"):
        validate_additive_explanation({**VALUES, "spo2": None})


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf, "not-a-number"])
def test_explanation_check_rejects_non_finite_or_non_numeric_values(invalid):
    with pytest.raises(ValueError, match="finite numeric"):
        validate_additive_explanation({**VALUES, "spo2": invalid})


@pytest.mark.parametrize("tolerance", [0, -1, math.nan, math.inf, -math.inf])
def test_explanation_check_rejects_invalid_tolerance(tolerance):
    with pytest.raises(ValueError, match="finite positive"):
        validate_additive_explanation(VALUES, tolerance=tolerance)

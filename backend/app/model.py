"""A reproducible scikit-learn model trained only on generated demo data.

This module deliberately does not load patient records or external datasets.
Its labels are generated from a transparent heuristic solely to exercise the
end-to-end software workflow. It is not a clinical model.
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = (
    "age",
    "heart_rate",
    "spo2",
    "systolic_bp",
    "diastolic_bp",
    "temperature",
    "respiratory_rate",
)
MODEL_VERSION = "synthetic-logreg-0.1.0"


def _heuristic_score(rows: np.ndarray) -> np.ndarray:
    age, hr, spo2, sys, dia, temp, rr = rows.T
    score = np.zeros(len(rows), dtype=float)
    score += np.clip(np.abs(hr - 82) - 12, 0, 70) * 0.55
    score += np.clip(96 - spo2, 0, 30) * 4.4
    score += np.clip(105 - sys, 0, 80) * 0.72
    score += np.clip(rr - 18, 0, 35) * 1.5
    score += np.clip(12 - rr, 0, 12) * 1.8
    score += np.clip(np.abs(temp - 37) - 0.5, 0, 5) * 10
    score += np.clip(age - 65, 0, 45) * 0.18
    score += np.clip(55 - dia, 0, 35) * 0.3
    return np.clip(score, 0, 100)


def _training_data(seed: int = 20261010, samples: int = 12000):
    rng = np.random.default_rng(seed)
    rows = np.column_stack(
        [
            rng.integers(18, 101, samples),
            rng.normal(84, 22, samples).clip(35, 190),
            rng.normal(96, 3.2, samples).clip(75, 100),
            rng.normal(122, 22, samples).clip(65, 220),
            rng.normal(76, 13, samples).clip(35, 130),
            rng.normal(37.0, 1.0, samples).clip(34, 42),
            rng.normal(17, 6, samples).clip(5, 42),
        ]
    )
    heuristic = _heuristic_score(rows)
    # A small noise term prevents an unrealistically perfect synthetic boundary.
    labels = ((heuristic + rng.normal(0, 7, samples)) >= 35).astype(int)
    return rows, labels


def build_model() -> Pipeline:
    rows, labels = _training_data()
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1200,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(rows, labels)
    return model


MODEL = build_model()


def predict_probability(values: dict[str, float]) -> float:
    row = np.array([[values[name] for name in FEATURES]], dtype=float)
    return float(MODEL.predict_proba(row)[0, 1])


def explain(values: dict[str, float]) -> list[dict[str, object]]:
    """Return understandable rule-based indicators, not causal explanations."""
    candidates = [
        ("spo2", values["spo2"], values["spo2"] < 94, "Low oxygen saturation can be a risk signal in this demo."),
        ("heart_rate", values["heart_rate"], values["heart_rate"] < 50 or values["heart_rate"] > 110, "Heart rate is outside the demo reference band of 50–110 bpm."),
        ("systolic_bp", values["systolic_bp"], values["systolic_bp"] < 100, "Low systolic blood pressure can be a risk signal in this demo."),
        ("respiratory_rate", values["respiratory_rate"], values["respiratory_rate"] < 10 or values["respiratory_rate"] > 22, "Respiratory rate is outside the demo reference band of 10–22/min."),
        ("temperature", values["temperature"], values["temperature"] < 36 or values["temperature"] > 38, "Temperature is outside the demo reference band of 36–38 °C."),
    ]
    factors = []
    for feature, observed, flagged, explanation in candidates:
        if flagged:
            factors.append(
                {
                    "feature": feature,
                    "observed_value": round(float(observed), 1),
                    "direction": "increases-risk",
                    "explanation": explanation,
                }
            )
    if not factors:
        factors.append(
            {
                "feature": "observations",
                "observed_value": 0.0,
                "direction": "decreases-risk",
                "explanation": "No configured demo thresholds were crossed; this does not rule out a medical problem.",
            }
        )
    return factors


def risk_level(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 30:
        return "moderate"
    return "low"

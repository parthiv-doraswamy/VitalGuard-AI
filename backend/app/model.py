"""Active risk model for the VitalGuard demo API.

The API serves a pre-built, versioned artifact (see model_artifact.py and ml/)
and never trains during import. The default artifact is the synthetic demo
model, trained only on generated data with heuristic labels; it is not a
clinical model.

Fallback: if the artifact is missing or fails verification, the synthetic demo
model is rebuilt deterministically in-process (identical to the artifact) and
/api/v1/model/info reports model_source="fallback-synthetic-training". Set
VITALGUARD_MODEL_REQUIRE_ARTIFACT=true to fail instead of falling back.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .model_artifact import ArtifactError, load_artifact
from .synthetic_data import training_data

FEATURES = (
    "age",
    "heart_rate",
    "spo2",
    "systolic_bp",
    "diastolic_bp",
    "temperature",
    "respiratory_rate",
)
# Version of the synthetic demo model; the active version comes from the loaded artifact.
MODEL_VERSION = "synthetic-logreg-0.1.0"
DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parent / "model_artifacts" / MODEL_VERSION
# Only synthetic models may be served by this demo unless an operator explicitly opts in.
DEMO_DATASET_KINDS = {"synthetic-demo"}

logger = logging.getLogger("vitalguard.model")


def _training_data(seed: int = 20261010, samples: int = 12000):
    return training_data(seed=seed, samples=samples)


def build_model() -> Pipeline:
    """Train the synthetic demo pipeline (used by ml/ and as the documented fallback)."""
    rows, labels = training_data()
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


@dataclass(frozen=True)
class ActiveModel:
    pipeline: Pipeline
    version: str
    source: str
    manifest: dict[str, Any] | None = None
    load_error: str | None = None
    info: dict[str, Any] = field(default_factory=dict)


_ACTIVE: ActiveModel | None = None
_LOCK = threading.Lock()


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _load() -> ActiveModel:
    directory = Path(os.getenv("VITALGUARD_MODEL_ARTIFACT", str(DEFAULT_ARTIFACT_DIR)))
    try:
        pipeline, manifest = load_artifact(directory, FEATURES, os.getenv("VITALGUARD_MODEL_SHA256") or None)
        kind = manifest.get("dataset", {}).get("kind")
        if kind not in DEMO_DATASET_KINDS and not _flag("VITALGUARD_ALLOW_NON_DEMO_MODEL"):
            raise ArtifactError(f"Artifact dataset kind '{kind}' is not allowed in the demo API")
        return ActiveModel(pipeline=pipeline, version=manifest["model_version"], source="artifact", manifest=manifest)
    except ArtifactError as exc:
        if _flag("VITALGUARD_MODEL_REQUIRE_ARTIFACT"):
            raise
        logger.warning("Model artifact unavailable (%s); rebuilding the synthetic demo model in-process", exc)
        return ActiveModel(pipeline=build_model(), version=MODEL_VERSION,
                           source="fallback-synthetic-training", load_error=str(exc))


def active_model() -> ActiveModel:
    """Return the loaded model, loading (or falling back) once per process."""
    global _ACTIVE
    if _ACTIVE is None:
        with _LOCK:
            if _ACTIVE is None:
                _ACTIVE = _load()
    return _ACTIVE


def reset_active_model() -> None:
    """Forget the loaded model so the next call reloads it (tests and operators)."""
    global _ACTIVE
    with _LOCK:
        _ACTIVE = None


def predict_probability(values: dict[str, float]) -> float:
    row = np.array([[values[name] for name in FEATURES]], dtype=float)
    return float(active_model().pipeline.predict_proba(row)[0, 1])


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

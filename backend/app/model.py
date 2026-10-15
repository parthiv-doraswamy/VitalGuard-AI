"""Active risk model for the VitalGuard demo API.

The API serves a pre-built, versioned artifact (see model_artifact.py and ml/)
and never trains during import. The default artifact is the synthetic demo
model, trained only on generated data with heuristic labels; it is not a
clinical model.

Which artifact: VITALGUARD_MODEL_ARTIFACT if set, otherwise the `active` entry of
model_artifacts/registry.json (managed by ml/model_registry.py promote/rollback).

Fallback chain: if the active artifact fails verification, the registry's
`previous` artifact is served (model_source "artifact-previous-after-active-failed");
if none is usable, the synthetic demo model is rebuilt deterministically
in-process (model_source "fallback-synthetic-training"). Set
VITALGUARD_MODEL_REQUIRE_ARTIFACT=true to fail startup instead of rebuilding.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .model_artifact import ArtifactError, load_artifact
from .model_registry_file import read_registry
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
ARTIFACT_ROOT = Path(__file__).resolve().parent / "model_artifacts"
DEFAULT_ARTIFACT_DIR = ARTIFACT_ROOT / MODEL_VERSION
DEMO_DATASET_KINDS = {"synthetic-demo"}
# Served without opt-in: synthetic data, and open-licensed, de-identified public research data
# (e.g. the PhysioNet 2019 benchmark). Anything else, such as credentialed clinical data, needs
# VITALGUARD_ALLOW_NON_DEMO_MODEL=true.
SERVABLE_DATASET_KINDS = DEMO_DATASET_KINDS | {"public-research"}

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


class InvalidModelInput(ValueError):
    """Inputs are missing, non-numeric or non-finite."""


@dataclass(frozen=True)
class ActiveModel:
    """Common interface for every servable model: load, predict, metadata, validate.

    All algorithms are sklearn Pipelines over FEATURES (in that order) exposing
    predict_proba, so the API code path is the same for every model type.
    """
    pipeline: Pipeline
    version: str
    source: str
    manifest: dict[str, Any] | None = None
    load_error: str | None = None
    info: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, directory: Path, source: str = "artifact") -> "ActiveModel":
        pipeline, manifest = load_artifact(directory, FEATURES, os.getenv("VITALGUARD_MODEL_SHA256") or None)
        kind = manifest.get("dataset", {}).get("kind")
        if kind not in SERVABLE_DATASET_KINDS and not _flag("VITALGUARD_ALLOW_NON_DEMO_MODEL"):
            raise ArtifactError(f"Artifact dataset kind '{kind}' is not allowed in the demo API")
        return cls(pipeline=pipeline, version=manifest["model_version"], source=source, manifest=manifest,
                   info={"artifact_dir": str(directory)})

    def predict_proba(self, values: Mapping[str, Any]) -> float:
        """Probability for one observation; inputs are read strictly in FEATURES order."""
        missing = [name for name in FEATURES if name not in values or values[name] is None]
        if missing:
            raise InvalidModelInput(f"Missing model inputs: {missing}")
        try:
            row = np.array([[float(values[name]) for name in FEATURES]], dtype=float)
        except (TypeError, ValueError) as exc:
            raise InvalidModelInput("Model inputs must be numeric") from exc
        if not np.isfinite(row).all():
            raise InvalidModelInput("Model inputs must be finite numbers")
        probability = float(self.pipeline.predict_proba(row)[0, 1])
        if not 0.0 <= probability <= 1.0:
            raise ArtifactError(f"Model returned an out-of-range probability: {probability}")
        return probability

    @property
    def algorithm(self) -> str:
        if self.manifest and self.manifest.get("training", {}).get("algorithm"):
            return self.manifest["training"]["algorithm"]
        return "StandardScaler + LogisticRegression"

    @property
    def mode(self) -> str:
        """synthetic-demo unless an explicitly allowed research artifact is active."""
        kind = (self.manifest or {}).get("dataset", {}).get("kind", "synthetic-demo")
        return "synthetic-demo" if kind in DEMO_DATASET_KINDS else "research-model"

    @property
    def supports_coefficient_contributions(self) -> bool:
        return isinstance(self.pipeline.named_steps.get("classifier"), LogisticRegression) and \
            isinstance(self.pipeline.named_steps.get("scale"), StandardScaler)

    def validate(self) -> None:
        """Re-check that the loaded model reproduces its manifest's reference probabilities."""
        if not self.manifest:
            return
        reproduced = self.pipeline.predict_proba(np.array(self.manifest["reference_inputs"], dtype=float))[:, 1]
        if not np.allclose(reproduced, self.manifest["reference_probabilities"], rtol=0, atol=1e-9):
            raise ArtifactError("Active model no longer reproduces its reference probabilities")

    def metadata(self) -> dict[str, Any]:
        manifest = self.manifest or {}
        dataset = manifest.get("dataset", {})
        return {
            "model_version": self.version, "mode": self.mode, "model_source": self.source,
            "algorithm": self.algorithm, "features": list(FEATURES),
            "training_data": dataset.get("description", "generated synthetic observations only"),
            "artifact": {"sha256": manifest.get("model_sha256"), "created_at": manifest.get("created_at"),
                         "dataset_kind": dataset.get("kind", "synthetic-demo"), "dataset_id": dataset.get("id"),
                         "training_run_id": manifest.get("training", {}).get("run_id"),
                         "library_versions": manifest.get("library_versions"),
                         "decision_threshold": (manifest.get("decision_threshold") or {}).get("value"),
                         "selection": manifest.get("selection")} if manifest else None,
            "load_error": self.load_error,
            "supports_coefficient_contributions": self.supports_coefficient_contributions,
        }


_ACTIVE: ActiveModel | None = None
_LOCK = threading.Lock()


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _candidates() -> list[tuple[Path, str]]:
    """Artifacts to try in order: explicit override, else registry active then previous."""
    override = os.getenv("VITALGUARD_MODEL_ARTIFACT")
    if override:
        return [(Path(override), "artifact")]
    try:
        registry = read_registry(ARTIFACT_ROOT)
    except (OSError, ValueError) as exc:
        logger.warning("Model registry unreadable (%s); using the default demo artifact", exc)
        return [(DEFAULT_ARTIFACT_DIR, "artifact")]
    ordered = [(ARTIFACT_ROOT / registry["active"], "artifact")]
    if registry.get("previous"):
        ordered.append((ARTIFACT_ROOT / registry["previous"], "artifact-previous-after-active-failed"))
    return ordered


def _load() -> ActiveModel:
    errors = []
    for directory, source in _candidates():
        try:
            model = ActiveModel.load(directory, source)
            if errors:
                logger.error("Active model artifact failed (%s); serving previous artifact %s", errors[0], model.version)
                return replace(model, load_error="; ".join(errors))
            return model
        except ArtifactError as exc:
            errors.append(f"{directory.name}: {exc}")
    if _flag("VITALGUARD_MODEL_REQUIRE_ARTIFACT"):
        raise ArtifactError("; ".join(errors))
    logger.warning("No usable model artifact (%s); rebuilding the synthetic demo model in-process", "; ".join(errors))
    return ActiveModel(pipeline=build_model(), version=MODEL_VERSION,
                       source="fallback-synthetic-training", load_error="; ".join(errors))


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
    return active_model().predict_proba(values)


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

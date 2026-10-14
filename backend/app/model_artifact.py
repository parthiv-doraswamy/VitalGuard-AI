"""Save and load versioned model artifacts with integrity and compatibility checks.

An artifact directory holds:
  model.joblib   the fitted scikit-learn Pipeline (preprocessing + classifier)
  manifest.json  version, dataset/target/split provenance, feature order,
                 library versions, the model file's SHA-256, and reference
                 inputs with their expected probabilities.

Loading verifies the hash, the exact feature order, the scikit-learn version
(pickles are only supported across identical versions), and that the loaded
model reproduces the reference probabilities. joblib/pickle can execute code,
so only load artifacts from trusted locations; VITALGUARD_MODEL_SHA256 can pin
the expected hash independently of the manifest.
"""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import sklearn

ARTIFACT_FORMAT = "vitalguard-model-artifact"
FORMAT_VERSION = 1
MODEL_FILE = "model.joblib"
MANIFEST_FILE = "manifest.json"
REFERENCE_TOLERANCE = 1e-9

# Plausible fictional inputs in feature order: age, HR, SpO2, SBP, DBP, temp, RR.
REFERENCE_INPUTS = [
    [58, 82, 98, 122, 78, 37.0, 16],
    [67, 118, 91, 96, 58, 38.4, 25],
    [80, 140, 85, 84, 48, 39.3, 32],
    [35, 64, 99, 134, 86, 36.6, 12],
    [72, 101, 94, 108, 66, 37.8, 21],
]


class ArtifactError(RuntimeError):
    """The artifact is missing, altered, incompatible or does not reproduce its reference outputs."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def library_versions() -> dict[str, str]:
    return {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
            "numpy": np.__version__, "joblib": joblib.__version__}


def save_artifact(pipeline: Any, directory: Path, features: Sequence[str], manifest: dict[str, Any]) -> dict[str, Any]:
    """Persist the fitted pipeline and a manifest; returns the written manifest."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / MODEL_FILE
    joblib.dump(pipeline, model_path)
    reference = np.array(REFERENCE_INPUTS, dtype=float)
    written = {
        "format": ARTIFACT_FORMAT,
        "format_version": FORMAT_VERSION,
        **manifest,
        "features": list(features),
        "model_file": MODEL_FILE,
        "model_sha256": sha256_file(model_path),
        "library_versions": library_versions(),
        "reference_inputs": REFERENCE_INPUTS,
        "reference_probabilities": [float(p) for p in pipeline.predict_proba(reference)[:, 1]],
        "created_at": manifest.get("created_at") or datetime.now(timezone.utc).isoformat(),
    }
    (directory / MANIFEST_FILE).write_text(json.dumps(written, indent=2, sort_keys=True) + "\n")
    return written


def read_manifest(directory: Path) -> dict[str, Any]:
    path = Path(directory) / MANIFEST_FILE
    if not path.is_file():
        raise ArtifactError(f"No {MANIFEST_FILE} in artifact directory")
    try:
        manifest = json.loads(path.read_text())
    except ValueError as exc:
        raise ArtifactError("Artifact manifest is not valid JSON") from exc
    if manifest.get("format") != ARTIFACT_FORMAT or manifest.get("format_version") != FORMAT_VERSION:
        raise ArtifactError("Unsupported artifact format")
    return manifest


def load_artifact(directory: Path, expected_features: Sequence[str], expected_sha256: str | None = None):
    """Load and verify an artifact; returns (pipeline, manifest) or raises ArtifactError."""
    directory = Path(directory)
    manifest = read_manifest(directory)
    if list(manifest.get("features", [])) != list(expected_features):
        raise ArtifactError(f"Feature order mismatch: artifact {manifest.get('features')} != API {list(expected_features)}")
    trained_with = manifest.get("library_versions", {}).get("scikit_learn")
    if trained_with != sklearn.__version__:
        raise ArtifactError(f"Artifact was saved with scikit-learn {trained_with}; this process has {sklearn.__version__}")
    model_path = directory / manifest.get("model_file", MODEL_FILE)
    if not model_path.is_file():
        raise ArtifactError("Model file missing")
    actual = sha256_file(model_path)
    if actual != manifest.get("model_sha256"):
        raise ArtifactError("Model file hash does not match the manifest")
    if expected_sha256 and actual != expected_sha256:
        raise ArtifactError("Model file hash does not match VITALGUARD_MODEL_SHA256")
    pipeline = joblib.load(model_path)
    # A Pipeline whose first step is "passthrough" (tree models) reports its feature count on the final estimator.
    feature_count = getattr(pipeline, "n_features_in_", None) or getattr(getattr(pipeline, "steps", [[None, None]])[-1][1],
                                                                         "n_features_in_", None)
    if not hasattr(pipeline, "predict_proba") or feature_count != len(expected_features):
        raise ArtifactError("Artifact is not a classifier for the expected feature count")
    reproduced = pipeline.predict_proba(np.array(manifest["reference_inputs"], dtype=float))[:, 1]
    if not np.allclose(reproduced, manifest["reference_probabilities"], rtol=0, atol=REFERENCE_TOLERANCE):
        raise ArtifactError("Loaded model does not reproduce its reference probabilities")
    return pipeline, manifest

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import model as model_module
from app.main import app
from app.model import DEFAULT_ARTIFACT_DIR, FEATURES, MODEL_VERSION, ActiveModel, active_model, build_model, reset_active_model
from app.model_artifact import ArtifactError, load_artifact
from app.model_evaluation import evaluate_synthetic_holdout
from app.synthetic_data import training_data

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _fresh_model(monkeypatch):
    for name in ("VITALGUARD_MODEL_ARTIFACT", "VITALGUARD_MODEL_SHA256", "VITALGUARD_MODEL_REQUIRE_ARTIFACT",
                 "VITALGUARD_ALLOW_NON_DEMO_MODEL"):
        monkeypatch.delenv(name, raising=False)
    reset_active_model()
    yield
    reset_active_model()


@pytest.fixture
def artifact_copy(tmp_path, monkeypatch):
    target = tmp_path / "artifact"
    shutil.copytree(DEFAULT_ARTIFACT_DIR, target)
    monkeypatch.setenv("VITALGUARD_MODEL_ARTIFACT", str(target))
    return target


def _edit_manifest(directory: Path, **changes):
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(manifest.get(key), dict):
            manifest[key].update(value)
        else:
            manifest[key] = value
    path.write_text(json.dumps(manifest))


def test_committed_registry_serves_the_physionet_model_with_the_synthetic_one_as_fallback():
    model = active_model()
    assert model.source == "artifact" and model.load_error is None
    assert model.version == "physionet2019-logistic-regression-1.0.0"
    assert model.manifest["dataset"]["kind"] == "public-research"
    assert model.manifest["features"] == list(FEATURES)
    registry = json.loads((DEFAULT_ARTIFACT_DIR.parent / "registry.json").read_text())
    assert registry["previous"] == MODEL_VERSION
    # The served model separates the demo scenarios: deteriorated vitals score far above normal ones.
    deteriorated = dict(age=67, heart_rate=138, spo2=85, systolic_bp=86, diastolic_bp=50, temperature=39.3, respiratory_rate=31)
    normal = dict(age=58, heart_rate=78, spo2=97, systolic_bp=122, diastolic_bp=78, temperature=37.0, respiratory_rate=16)
    assert model.predict_proba(deteriorated) > 0.65 > 0.5 > model.predict_proba(normal)


def test_artifact_reproduces_the_previous_in_process_model_exactly():
    rows, _ = training_data(seed=99, samples=2000)
    from_artifact = ActiveModel.load(DEFAULT_ARTIFACT_DIR).pipeline.predict_proba(rows)[:, 1]
    rebuilt = build_model().predict_proba(rows)[:, 1]
    assert np.allclose(from_artifact, rebuilt, rtol=0, atol=1e-12)


def test_stored_evaluation_matches_a_fresh_computation():
    stored = json.loads((DEFAULT_ARTIFACT_DIR / "evaluation.json").read_text())
    assert stored == json.loads(json.dumps(evaluate_synthetic_holdout()))


def test_importing_and_starting_the_api_never_trains(tmp_path):
    script = f"""
import os, sys
os.environ["VITALGUARD_DB_PATH"] = {str(tmp_path / 'db.sqlite3')!r}
from sklearn.linear_model import LogisticRegression
def refuse(*args, **kwargs):
    raise AssertionError("model training was attempted")
LogisticRegression.fit = refuse
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    body = client.post("/api/v1/risk/predict", json={{"patient_id": "DEMO-1", "age": 58, "heart_rate": 82, "spo2": 98,
        "systolic_bp": 122, "diastolic_bp": 78, "temperature": 37.0, "respiratory_rate": 16}}).json()
    info = client.get("/api/v1/model/info").json()
print(body["risk_score"], info["model_source"])
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_DIR, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    score, source = result.stdout.split()
    assert source == "artifact"
    in_process = round(active_model().pipeline.predict_proba(np.array([[58, 82, 98, 122, 78, 37.0, 16]]))[0, 1] * 100)
    assert int(score) == in_process


def test_tampered_artifact_falls_back_to_the_identical_synthetic_model(artifact_copy):
    (artifact_copy / "model.joblib").write_bytes((artifact_copy / "model.joblib").read_bytes() + b"tampered")
    with pytest.raises(ArtifactError, match="hash"):
        load_artifact(artifact_copy, FEATURES)
    model = active_model()
    assert model.source == "fallback-synthetic-training" and "hash" in model.load_error
    with TestClient(app) as client:
        info = client.get("/api/v1/model/info").json()
    assert info["model_source"] == "fallback-synthetic-training" and info["model_version"] == MODEL_VERSION


def test_required_artifact_fails_startup_instead_of_falling_back(artifact_copy, monkeypatch, tmp_path):
    (artifact_copy / "model.joblib").unlink()
    monkeypatch.setenv("VITALGUARD_MODEL_REQUIRE_ARTIFACT", "true")
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "db.sqlite3"))
    with pytest.raises(ArtifactError):
        with TestClient(app):
            pass


@pytest.mark.parametrize("changes, message", [
    ({"features": list(reversed(FEATURES))}, "Feature order"),
    ({"library_versions": {"scikit_learn": "0.0.1"}}, "scikit-learn"),
    ({"reference_probabilities": [0.5, 0.5, 0.5, 0.5, 0.5]}, "reference probabilities"),
    ({"format_version": 99}, "Unsupported artifact format"),
])
def test_incompatible_artifacts_are_rejected(artifact_copy, changes, message):
    _edit_manifest(artifact_copy, **changes)
    with pytest.raises(ArtifactError, match=message):
        load_artifact(artifact_copy, FEATURES)


def test_pinned_hash_must_match(artifact_copy, monkeypatch):
    monkeypatch.setenv("VITALGUARD_MODEL_SHA256", "0" * 64)
    monkeypatch.setenv("VITALGUARD_MODEL_REQUIRE_ARTIFACT", "true")
    with pytest.raises(ArtifactError, match="VITALGUARD_MODEL_SHA256"):
        active_model()


def test_non_demo_artifacts_are_not_served_without_explicit_opt_in(artifact_copy, monkeypatch):
    _edit_manifest(artifact_copy, dataset={"kind": "approved-clinical"})
    monkeypatch.setenv("VITALGUARD_MODEL_REQUIRE_ARTIFACT", "true")
    with pytest.raises(ArtifactError, match="not allowed in the demo API"):
        active_model()
    reset_active_model()
    monkeypatch.setenv("VITALGUARD_ALLOW_NON_DEMO_MODEL", "true")
    assert active_model().source == "artifact"


def test_missing_artifact_directory_uses_documented_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("VITALGUARD_MODEL_ARTIFACT", str(tmp_path / "does-not-exist"))
    model = active_model()
    assert model.source == "fallback-synthetic-training" and model.version == MODEL_VERSION


def test_model_info_reports_artifact_provenance(tmp_path, monkeypatch):
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "db.sqlite3"))
    with TestClient(app) as client:
        info = client.get("/api/v1/model/info").json()
    assert info["model_source"] == "artifact"
    assert info["training_data"] == "PhysioNet/CinC Challenge 2019 sepsis data (7 vitals, hourly)"
    assert info["artifact"]["dataset_kind"] == "public-research"
    assert len(info["artifact"]["sha256"]) == 64
    assert info["clinically_validated"] is False and info["load_error"] is None


def test_model_module_has_no_import_time_model():
    assert not hasattr(model_module, "MODEL")

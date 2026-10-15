"""The common model interface, registry-driven loading, rollback and the prediction contract."""
import json
import math
import shutil

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from app import model as model_module
from app.main import app
from app.model import (DEFAULT_ARTIFACT_DIR, FEATURES, MODEL_VERSION, InvalidModelInput, active_model, reset_active_model,
                       risk_level)
from app.model_artifact import ArtifactError, save_artifact
from app.model_registry_file import read_registry, write_registry
from app.synthetic_data import training_data

VALID = {"age": 58, "heart_rate": 82, "spo2": 98, "systolic_bp": 122, "diastolic_bp": 78, "temperature": 37.0,
         "respiratory_rate": 16}
API_RANGES = {"age": (18, 110), "heart_rate": (20, 250), "spo2": (50, 100), "systolic_bp": (90, 280),
              "diastolic_bp": (20, 85), "temperature": (30, 45), "respiratory_rate": (3, 70)}


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    for name in ("VITALGUARD_MODEL_ARTIFACT", "VITALGUARD_MODEL_SHA256", "VITALGUARD_MODEL_REQUIRE_ARTIFACT",
                 "VITALGUARD_ALLOW_NON_DEMO_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "model-tests.sqlite3"))
    reset_active_model()
    yield
    reset_active_model()


@pytest.fixture
def store(tmp_path, monkeypatch):
    """An isolated artifact store + registry containing the committed demo artifact."""
    root = tmp_path / "model_artifacts"
    root.mkdir()
    shutil.copytree(DEFAULT_ARTIFACT_DIR, root / MODEL_VERSION)
    (root / "registry.json").write_text(json.dumps({"format": "vitalguard-model-registry", "active": MODEL_VERSION,
                                                    "previous": None, "history": []}))
    monkeypatch.setattr(model_module, "ARTIFACT_ROOT", root)
    return root


def _activate(root, active, previous=None):
    registry = read_registry(root)
    registry.update({"active": active, "previous": previous})
    write_registry(root, registry)
    reset_active_model()


def _forest_artifact(root, version="synthetic-forest-test"):
    rows, labels = training_data(seed=3, samples=1500)
    pipeline = Pipeline([("scale", "passthrough"),
                         ("classifier", RandomForestClassifier(n_estimators=20, max_depth=4, random_state=0, n_jobs=1))])
    pipeline.fit(rows, labels)
    save_artifact(pipeline, root / version, FEATURES, {
        "model_version": version, "dataset": {"kind": "synthetic-demo", "description": "generated synthetic observations only"},
        "training": {"algorithm": "RandomForestClassifier"}})
    return pipeline


# --- Prediction contract ----------------------------------------------------------------

def test_probabilities_and_scores_stay_in_bounds_across_the_input_space():
    rng = np.random.default_rng(0)
    model = active_model()
    for _ in range(500):
        values = {name: float(rng.uniform(*API_RANGES[name])) for name in FEATURES}
        probability = model.predict_proba(values)
        score = round(probability * 100)
        assert 0.0 <= probability <= 1.0 and 0 <= score <= 100
        assert risk_level(score) in {"low", "moderate", "high", "critical"}


def test_inputs_are_read_by_name_in_the_fixed_feature_order():
    shuffled = dict(reversed(list(VALID.items())))
    model = active_model()
    assert model.predict_proba(shuffled) == model.predict_proba(VALID)
    row = np.array([[VALID[name] for name in FEATURES]])
    assert model.predict_proba(VALID) == pytest.approx(model.pipeline.predict_proba(row)[0, 1], abs=0)


@pytest.mark.parametrize("bad", [
    {k: v for k, v in VALID.items() if k != "spo2"},
    {**VALID, "spo2": None},
    {**VALID, "heart_rate": "fast"},
    {**VALID, "temperature": math.nan},
    {**VALID, "respiratory_rate": math.inf},
])
def test_missing_or_invalid_inputs_are_rejected_by_the_model_interface(bad):
    with pytest.raises(InvalidModelInput):
        active_model().predict_proba(bad)


@pytest.mark.parametrize("change", [
    {"spo2": None}, {"spo2": "NaN"}, {"spo2": 140}, {"heart_rate": "fast"}, {"unexpected": 1},
])
def test_api_rejects_missing_and_invalid_inputs(change):
    payload = {"patient_id": "DEMO-MODEL", **VALID, **change}
    payload = {k: v for k, v in payload.items() if v is not None}
    with TestClient(app) as client:
        response = client.post("/api/v1/risk/predict", json=payload)
    assert response.status_code == 422


def test_prediction_response_contract_is_unchanged():
    with TestClient(app) as client:
        body = client.post("/api/v1/risk/predict", json={"patient_id": "DEMO-MODEL", **VALID}).json()
    assert set(body) == {"patient_id", "observation_id", "created_at", "risk_score", "risk_level", "model_probability",
                         "factors", "model_version", "demo_only", "disclaimer"}


# --- Active version, metadata and synthetic-demo mode -------------------------------------

def test_api_reports_the_version_that_is_actually_serving(store):
    _forest_artifact(store)
    _activate(store, "synthetic-forest-test", previous=MODEL_VERSION)
    with TestClient(app) as client:
        info = client.get("/api/v1/model/info").json()
        health = client.get("/health").json()
        prediction = client.post("/api/v1/risk/predict", json={"patient_id": "DEMO-MODEL", **VALID}).json()
        explanation = client.post("/api/v1/risk/explain", json={"patient_id": "DEMO-MODEL", **VALID}).json()
    assert info["model_version"] == health["model_version"] == prediction["model_version"] == "synthetic-forest-test"
    assert info["algorithm"] == "RandomForestClassifier" and info["supports_coefficient_contributions"] is False
    assert explanation["contributions"] == [] and explanation["method"].startswith("not available")
    assert prediction["model_probability"] == pytest.approx(active_model().predict_proba(VALID), abs=1e-4)


def test_default_model_is_the_promoted_physionet_benchmark_model():
    with TestClient(app) as client:
        info = client.get("/api/v1/model/info").json()
    assert info["mode"] == "research-model" and info["model_version"] == "physionet2019-logistic-regression-1.0.0"
    assert info["artifact"]["dataset_kind"] == "public-research"
    assert info["model_source"] == "artifact" and info["clinically_validated"] is False
    assert info["supports_coefficient_contributions"] is True
    # Fields from the earlier contract remain.
    for key in ("name", "model_version", "algorithm", "features", "training_data", "demo_only", "clinically_validated"):
        assert key in info


def test_public_research_artifacts_are_servable_without_opt_in(store):
    manifest_path = store / MODEL_VERSION / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["dataset"]["kind"] = "public-research"
    manifest_path.write_text(json.dumps(manifest))
    model = active_model()
    assert model.source == "artifact" and model.mode == "research-model"


def test_research_mode_requires_explicit_opt_in(store, monkeypatch):
    manifest_path = store / MODEL_VERSION / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["dataset"]["kind"] = "approved-clinical"
    manifest_path.write_text(json.dumps(manifest))
    assert active_model().source == "fallback-synthetic-training"
    reset_active_model()
    monkeypatch.setenv("VITALGUARD_ALLOW_NON_DEMO_MODEL", "true")
    assert active_model().mode == "research-model"


# --- Loading, rollback and fallback -------------------------------------------------------

def test_failed_active_artifact_rolls_back_to_the_previous_one(store):
    _forest_artifact(store)
    (store / "synthetic-forest-test" / "model.joblib").write_bytes(b"corrupt")
    _activate(store, "synthetic-forest-test", previous=MODEL_VERSION)
    model = active_model()
    assert model.version == MODEL_VERSION
    assert model.source == "artifact-previous-after-active-failed"
    assert "synthetic-forest-test" in model.load_error


def test_incompatible_active_artifact_rolls_back(store):
    _forest_artifact(store)
    manifest_path = store / "synthetic-forest-test" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["library_versions"]["scikit_learn"] = "0.24.2"
    manifest_path.write_text(json.dumps(manifest))
    _activate(store, "synthetic-forest-test", previous=MODEL_VERSION)
    assert active_model().source == "artifact-previous-after-active-failed"


def test_missing_artifacts_fall_back_to_synthetic_training_or_fail_when_required(store, monkeypatch):
    _activate(store, "does-not-exist", previous="also-missing")
    model = active_model()
    assert model.source == "fallback-synthetic-training" and model.version == MODEL_VERSION
    with TestClient(app) as client:
        assert client.get("/api/v1/model/info").json()["model_source"] == "fallback-synthetic-training"
    reset_active_model()
    monkeypatch.setenv("VITALGUARD_MODEL_REQUIRE_ARTIFACT", "true")
    with pytest.raises(ArtifactError, match="does-not-exist"):
        active_model()


def test_unreadable_registry_uses_the_default_demo_artifact(store):
    (store / "registry.json").write_text("{not json")
    assert active_model().source == "artifact"


def test_reloading_after_restart_gives_identical_predictions(store):
    expected = _forest_artifact(store).predict_proba(np.array([[VALID[name] for name in FEATURES]]))[0, 1]
    _activate(store, "synthetic-forest-test")
    first = active_model().predict_proba(VALID)
    reset_active_model()  # simulates a new process: nothing is cached
    assert active_model().predict_proba(VALID) == first == pytest.approx(expected, abs=1e-12)
    active_model().validate()

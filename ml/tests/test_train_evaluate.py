"""Patient-level splits, reproducibility, test-set isolation, serialization and evaluation."""
import json
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from common import BACKEND_DIR, PipelineError, sha256_file
from conftest import ML_DIR, fixture_config
from evaluate import evaluate
from prepare_dataset import assign_splits, prepare
from train import check_patient_disjoint, fit_baseline, load_dataset, train_baseline
from app.model import FEATURES
from app.model_artifact import ArtifactError, load_artifact


@pytest.fixture(scope="module")
def trained(prepared, tmp_path_factory):
    out = tmp_path_factory.mktemp("artifacts")
    result = train_baseline("mimic_format_fixture", prepared["dataset_dir"], out, config=prepared["config"],
                            check_reproducible=True)
    return result


def test_no_patient_appears_in_more_than_one_split(prepared):
    rows, manifest = load_dataset(prepared["dataset_dir"])
    sets = {split: set(part["patient_id"]) for split, part in rows.groupby("split")}
    assert set(sets) == {"train", "validation", "test"}
    assert not (sets["train"] & sets["validation"]) and not (sets["train"] & sets["test"]) and not (sets["validation"] & sets["test"])
    assert all(summary["patients"] > 0 for summary in manifest["splits"].values())


def test_split_assignment_is_deterministic_and_patient_level():
    rows = pd.DataFrame({"patient_id": [str(i // 3) for i in range(600)], "split_group": "g"})
    split = {"strategy": "patient_hash", "seed": 5, "fractions": {"train": 0.7, "validation": 0.15, "test": 0.15}}
    first, second = assign_splits(rows, split), assign_splits(rows, split)
    assert first.equals(second)
    assert (rows.assign(split=first).groupby("patient_id")["split"].nunique() == 1).all()
    assert assign_splits(rows, {**split, "seed": 6}).ne(first).any()


def test_patient_group_strategy_holds_out_whole_groups():
    rows = pd.DataFrame({"patient_id": [str(i) for i in range(200)],
                         "split_group": ["2017 - 2019" if i % 4 == 0 else "2008 - 2010" for i in range(200)]})
    split = {"strategy": "patient_group", "seed": 5, "test_groups": ["2017 - 2019"],
             "fractions": {"train": 0.7, "validation": 0.15, "test": 0.15}}
    assigned = rows.assign(split=assign_splits(rows, split))
    assert set(assigned.loc[assigned["split_group"] == "2017 - 2019", "split"]) == {"test"}
    assert set(assigned.loc[assigned["split_group"] != "2017 - 2019", "split"]) == {"train", "validation"}


def test_leakage_check_rejects_a_patient_in_two_splits():
    rows = pd.DataFrame({"patient_id": ["a", "a", "b"], "split": ["train", "test", "validation"]})
    with pytest.raises(PipelineError, match="Patient leakage"):
        check_patient_disjoint(rows)


def test_preparing_the_same_data_twice_gives_the_same_dataset_version(prepared, tmp_path):
    config = fixture_config(prepared["root"] / "synthetic-mimic-format")
    again = prepare("mimic_format_fixture", out_dir=tmp_path / "dataset", config=config)
    assert again["dataset_sha256"] == prepared["manifest"]["dataset_sha256"]
    assert again["dataset_version"] == prepared["manifest"]["dataset_version"]


def test_training_twice_is_reproducible_within_tolerance(prepared, trained, tmp_path):
    second = train_baseline("mimic_format_fixture", prepared["dataset_dir"], tmp_path, config=prepared["config"])
    a, b = trained["manifest"], second["manifest"]
    tolerance = prepared["config"]["reproducibility"]["abs_tolerance"]
    assert np.allclose(a["training"]["coefficients"], b["training"]["coefficients"], rtol=0, atol=tolerance)
    assert abs(a["training"]["intercept"] - b["training"]["intercept"]) <= tolerance
    assert a["training"]["selected_C"] == b["training"]["selected_C"]
    assert a["decision_threshold"] == b["decision_threshold"]
    assert np.allclose(a["reference_probabilities"], b["reference_probabilities"], rtol=0, atol=tolerance)
    assert a["model_version"] == b["model_version"]  # version = dataset hash + config hash
    assert a["training"]["reproducibility_checked"] is True


def test_test_split_never_influences_model_or_threshold_selection(prepared):
    rows, _ = load_dataset(prepared["dataset_dir"])
    baseline = fit_baseline(rows, prepared["config"])
    scrambled = rows.copy()
    test = scrambled["split"] == "test"
    rng = np.random.default_rng(0)
    scrambled.loc[test, "label"] = 1 - scrambled.loc[test, "label"]
    scrambled.loc[test, list(FEATURES)] = rng.permutation(scrambled.loc[test, list(FEATURES)].to_numpy())
    changed = fit_baseline(scrambled, prepared["config"])
    assert changed["C"] == baseline["C"] and changed["threshold"] == baseline["threshold"]
    assert np.array_equal(changed["pipeline"].named_steps["classifier"].coef_, baseline["pipeline"].named_steps["classifier"].coef_)
    assert baseline["threshold"]["selected_on"] == "validation"


def test_manifest_versions_everything_needed_to_reproduce_the_run(trained, prepared):
    manifest = trained["manifest"]
    assert manifest["features"] == list(FEATURES)
    assert manifest["dataset"]["sha256"] == prepared["manifest"]["dataset_sha256"]
    assert manifest["dataset"]["kind"] == "synthetic-fixture" and manifest["dataset"]["synthetic_fixture"] is True
    assert manifest["target"]["id"] == "inhospital-death-within-24h-v1"
    assert manifest["split"]["strategy"] == "patient_hash" and len(manifest["split"]["train_patient_ids_sha256"]) == 64
    assert manifest["training"]["seed"] == prepared["config"]["split"]["seed"]
    assert len(manifest["training"]["config_sha256"]) == 64
    assert manifest["clinically_validated"] is False
    assert manifest["model_sha256"] == sha256_file(trained["artifact_dir"] / "model.joblib")


def test_predictions_are_identical_before_and_after_serialization(prepared, trained):
    rows, _ = load_dataset(prepared["dataset_dir"])
    fitted = fit_baseline(rows, prepared["config"])
    sample = rows[list(FEATURES)].to_numpy(float)[:500]
    loaded, _ = load_artifact(trained["artifact_dir"], FEATURES)
    assert np.array_equal(fitted["pipeline"].predict_proba(sample), loaded.predict_proba(sample))


def test_inference_works_in_a_fresh_process(trained):
    script = (
        "import sys, json; from app.model import FEATURES; from app.model_artifact import load_artifact; "
        f"p, m = load_artifact({str(trained['artifact_dir'])!r}, FEATURES); "
        "print(json.dumps([float(v) for v in p.predict_proba(m['reference_inputs'])[:, 1]]))"
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_DIR, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == trained["manifest"]["reference_probabilities"]


def test_training_cli_refuses_a_dataset_prepared_with_a_different_configuration(prepared):
    command = [sys.executable, str(ML_DIR / "train.py"), "--experiment", "mimic_format_fixture",
               "--dataset", str(prepared["dataset_dir"])]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    # The CLI uses ml/config.yaml as-is; this dataset was prepared with a different (test) data_dir.
    assert result.returncode == 2 and "different configuration" in result.stdout


def test_fixture_artifact_is_refused_by_the_demo_api_loader_policy(trained, monkeypatch):
    from app.model import active_model, reset_active_model
    monkeypatch.setenv("VITALGUARD_MODEL_ARTIFACT", str(trained["artifact_dir"]))
    monkeypatch.setenv("VITALGUARD_MODEL_REQUIRE_ARTIFACT", "true")
    reset_active_model()
    try:
        with pytest.raises(ArtifactError, match="not allowed in the demo API"):
            active_model()
    finally:
        reset_active_model()


def test_evaluation_reports_metrics_without_retuning(prepared, trained):
    report = evaluate(trained["artifact_dir"], prepared["dataset_dir"])
    metrics = report["metrics"]
    for name in ("roc_auc", "pr_auc_average_precision", "sensitivity", "specificity", "precision_ppv", "npv"):
        assert metrics[name] is None or 0 <= metrics[name] <= 1
    assert metrics["threshold"] == trained["manifest"]["decision_threshold"]["value"]
    assert report["threshold_provenance"]["selected_on"] == "validation"
    assert "brier_score" in report["calibration"] and len(report["calibration"]["reliability_table"]) == 10
    assert report["leakage_checks"]["patient_disjoint_splits"] is True
    assert report["clinically_validated"] is False
    assert report["disclaimer"].startswith("SYNTHETIC FIXTURE")
    assert (trained["artifact_dir"] / "evaluation.md").is_file()


def test_evaluation_refuses_a_different_dataset_or_split(prepared, trained, tmp_path):
    altered = tmp_path / "dataset"
    shutil.copytree(prepared["dataset_dir"], altered)
    rows = pd.read_csv(altered / "dataset.csv", dtype={"patient_id": str, "split_group": str})
    with open(altered / "dataset.csv", "a") as handle:
        handle.write(rows.iloc[[0]].to_csv(index=False, header=False))
    with pytest.raises(PipelineError, match="does not match its manifest hash"):
        evaluate(trained["artifact_dir"], altered)

    moved = rows.copy()
    first_test_patient = moved.loc[moved["split"] == "test", "patient_id"].iloc[0]
    moved.loc[moved["patient_id"] == first_test_patient, "split"] = "train"
    moved.to_csv(altered / "dataset.csv", index=False)
    manifest = json.loads((altered / "dataset_manifest.json").read_text())
    manifest["dataset_sha256"] = sha256_file(altered / "dataset.csv")
    (altered / "dataset_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(PipelineError, match="Dataset version differs"):
        evaluate(trained["artifact_dir"], altered)

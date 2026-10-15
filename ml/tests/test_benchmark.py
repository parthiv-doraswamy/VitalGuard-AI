"""Candidate benchmarking: identical protocol, validation-only selection, recomputable reports, registry."""
import json
import shutil

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

import model_registry
from common import PipelineError
from evaluate import evaluate_benchmark
from train import benchmark, fit_candidate, load_dataset, select_model
from app.model import DEFAULT_ARTIFACT_DIR, FEATURES
from app.model_artifact import ArtifactError, load_artifact
from app.model_registry_file import read_registry


@pytest.fixture(scope="module")
def benchmarked(prepared, tmp_path_factory):
    out = tmp_path_factory.mktemp("bench")
    result = benchmark("mimic_format_fixture", prepared["dataset_dir"], out, config=prepared["config"])
    report = evaluate_benchmark(result["benchmark_dir"], prepared["dataset_dir"])
    return {**result, "report": report, "out": out}


def _manifest(benchmark_dir, item):
    return json.loads((benchmark_dir / item["artifact"] / "manifest.json").read_text())


def test_every_candidate_uses_identical_inputs_and_splits(benchmarked):
    selection = benchmarked["selection"]
    trained = {name: item for name, item in selection["candidates"].items() if item["status"] == "trained"}
    assert set(trained) == {"logreg", "random_forest", "xgboost"}
    manifests = [_manifest(benchmarked["benchmark_dir"], item) for item in trained.values()]
    for key in (("dataset", "sha256"), ("split", "train_patient_ids_sha256"), ("split", "validation_patient_ids_sha256"),
                ("training", "config_sha256")):
        assert len({m[key[0]][key[1]] for m in manifests}) == 1, key
    assert all(m["features"] == list(FEATURES) for m in manifests)
    assert len({m["decision_threshold"]["strategy"] for m in manifests}) == 1


def test_candidate_fitting_never_uses_the_test_split(prepared):
    rows, _ = load_dataset(prepared["dataset_dir"])
    scrambled = rows.copy()
    test = scrambled["split"] == "test"
    scrambled.loc[test, "label"] = 1 - scrambled.loc[test, "label"]
    scrambled.loc[test, list(FEATURES)] = np.random.default_rng(1).permutation(scrambled.loc[test, list(FEATURES)].to_numpy())
    for name in ("random_forest", "xgboost"):
        original, changed = fit_candidate(rows, prepared["config"], name), fit_candidate(scrambled, prepared["config"], name)
        assert original["params"] == changed["params"] and original["threshold"] == changed["threshold"]
        assert np.array_equal(original["validation_probabilities"], changed["validation_probabilities"])


def test_selection_is_frozen_before_test_evaluation(benchmarked):
    report = benchmarked["report"]
    assert report["selection_frozen_at"] < report["test_evaluated_at"]
    assert benchmarked["selection"]["selection_inputs"].startswith("validation split only")
    assert report["decision"] == benchmarked["selection"]["decision"]


def test_reported_test_metrics_can_be_recomputed_from_saved_predictions(benchmarked):
    for row in benchmarked["report"]["candidates"]:
        if row["status"] != "trained":
            continue
        saved = pd.read_csv(benchmarked["benchmark_dir"] / f"candidates/{row['model_version']}/test_predictions.csv")
        labels, probabilities = saved["label"].to_numpy(int), saved["probability"].to_numpy(float)
        predicted = probabilities >= row["threshold"]
        test = row["test"]
        assert test["roc_auc"] == pytest.approx(roc_auc_score(labels, probabilities))
        assert test["pr_auc_average_precision"] == pytest.approx(average_precision_score(labels, probabilities))
        assert test["brier_score"] == pytest.approx(brier_score_loss(labels, probabilities), abs=1e-5)
        assert test["sensitivity"] == pytest.approx(predicted[labels == 1].mean(), abs=1e-4)
        assert test["specificity"] == pytest.approx((~predicted[labels == 0]).mean(), abs=1e-4)


def test_comparison_report_covers_calibration_latency_and_size(benchmarked):
    for row in benchmarked["report"]["candidates"]:
        assert row["latency"]["single_row_p95_ms"] > 0 and row["artifact_bytes"] > 0
        assert row["validation"]["calibration_slope"] is not None and row["test"]["calibration_intercept"] is not None
    assert (benchmarked["benchmark_dir"] / "comparison_report.md").is_file()
    assert benchmarked["report"]["disclaimer"].startswith("SYNTHETIC FIXTURE")


def test_chosen_artifact_carries_selection_metadata_and_still_loads(benchmarked):
    decision = benchmarked["selection"]["decision"]
    chosen = benchmarked["benchmark_dir"] / benchmarked["selection"]["candidates"][decision["selected"]]["artifact"]
    _, manifest = load_artifact(chosen, FEATURES)
    assert manifest["selection"]["selected"] == decision["selected"]
    assert manifest["selection"]["compared"] == ["logreg", "random_forest", "xgboost"]
    assert (chosen / "comparison_report.json").is_file()


def test_xgboost_is_gated_out_because_the_api_runtime_cannot_load_it(benchmarked):
    xgb = benchmarked["selection"]["candidates"]["xgboost"]
    assert xgb["gates"]["loadable_by_backend_runtime"] is False and xgb["eligible"] is False


def test_tampering_after_selection_is_detected(benchmarked, prepared, tmp_path):
    copy = tmp_path / "bench"
    shutil.copytree(benchmarked["benchmark_dir"], copy)
    item = benchmarked["selection"]["candidates"]["random_forest"]
    manifest_path = copy / item["artifact"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["decision_threshold"]["value"] = 0.01
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(PipelineError, match="changed after the selection was frozen"):
        evaluate_benchmark(copy, prepared["dataset_dir"])


def test_benchmark_is_deterministic(prepared, benchmarked, tmp_path):
    again = benchmark("mimic_format_fixture", prepared["dataset_dir"], tmp_path, config=prepared["config"])["selection"]
    first = benchmarked["selection"]
    assert again["decision"] == first["decision"]
    for name, item in first["candidates"].items():
        other = again["candidates"][name]
        assert other["validation"] == item["validation"] and other["hyperparameters"] == item["hyperparameters"]
        assert other.get("paired_vs_baseline") == item.get("paired_vs_baseline")


def test_uninstalled_candidates_are_skipped_not_faked(prepared, tmp_path, monkeypatch):
    monkeypatch.setattr("train.installed", lambda candidate: candidate.name != "xgboost")
    selection = benchmark("mimic_format_fixture", prepared["dataset_dir"], tmp_path, config=prepared["config"])["selection"]
    assert selection["candidates"]["xgboost"]["status"] == "skipped"
    assert any("xgboost: skipped" in line for line in selection["decision"]["rationale"])


def _result(name, complexity, metric, eligible=True, difference=None, ci=None):
    result = {"status": "trained", "complexity": complexity, "model_version": f"{name}-v", "eligible": eligible,
              "gates": {"g": eligible}, "validation": {"pr_auc_average_precision": metric}}
    if difference is not None:
        result["paired_vs_baseline"] = {"difference": difference, "ci95": ci}
    return result


SETTINGS = {"primary_metric": "average_precision", "min_improvement": 0.02}


@pytest.mark.parametrize("challenger, expected", [
    (_result("random_forest", 2, 0.75, difference=0.05, ci=[0.01, 0.09]), "random_forest"),   # meaningful and robust
    (_result("random_forest", 2, 0.75, difference=0.05, ci=[-0.01, 0.09]), "logreg"),         # CI includes zero
    (_result("random_forest", 2, 0.71, difference=0.01, ci=[0.001, 0.02]), "logreg"),         # below min_improvement
    (_result("random_forest", 2, 0.90, eligible=False, difference=0.2, ci=[0.1, 0.3]), "logreg"),  # fails a gate
])
def test_selection_rule_prefers_the_baseline_unless_clearly_better(challenger, expected):
    results = {"logreg": _result("logreg", 1, 0.70), "random_forest": challenger}
    assert select_model(results, SETTINGS)["selected"] == expected


def test_most_complex_model_is_not_preferred_when_gains_tie():
    results = {"logreg": _result("logreg", 1, 0.70),
               "random_forest": _result("random_forest", 2, 0.75, difference=0.05, ci=[0.01, 0.09]),
               "xgboost": _result("xgboost", 3, 0.75, difference=0.05, ci=[0.01, 0.09])}
    assert select_model(results, SETTINGS)["selected"] == "random_forest"


def test_undeployable_baseline_falls_to_the_best_eligible_candidate_or_none():
    results = {"logreg": _result("logreg", 1, 0.70, eligible=False),
               "random_forest": _result("random_forest", 2, 0.65, difference=-0.05, ci=[-0.1, 0.0])}
    assert select_model(results, SETTINGS)["selected"] == "random_forest"
    results["random_forest"]["eligible"] = False
    assert select_model(results, SETTINGS)["selected"] is None


@pytest.fixture
def registry_root(tmp_path):
    root = tmp_path / "model_artifacts"
    root.mkdir()
    shutil.copytree(DEFAULT_ARTIFACT_DIR, root / DEFAULT_ARTIFACT_DIR.name)
    # A store holding only the synthetic demo artifact, active with no previous version.
    (root / "registry.json").write_text(json.dumps({"format": "vitalguard-model-registry",
                                                    "active": DEFAULT_ARTIFACT_DIR.name, "previous": None, "history": []}))
    return root


def test_fixture_artifacts_can_never_be_promoted(benchmarked, registry_root):
    chosen = benchmarked["benchmark_dir"] / benchmarked["selection"]["candidates"]["logreg"]["artifact"]
    with pytest.raises(PipelineError, match="synthetic fixture"):
        model_registry.promote(chosen, allow_research=True, root=registry_root)


def test_promote_and_rollback_round_trip(benchmarked, registry_root, tmp_path):
    research = tmp_path / "research-artifact"
    shutil.copytree(benchmarked["benchmark_dir"] / benchmarked["selection"]["candidates"]["logreg"]["artifact"], research)
    manifest = json.loads((research / "manifest.json").read_text())
    manifest["dataset"].update({"kind": "approved-clinical", "synthetic_fixture": False})
    manifest["model_version"] = "logreg-research-test"
    (research / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(PipelineError, match="allow-research-artifact"):
        model_registry.promote(research, root=registry_root)
    promoted = model_registry.promote(research, allow_research=True, root=registry_root)
    assert (promoted["active"], promoted["previous"]) == ("logreg-research-test", "synthetic-logreg-0.1.0")
    rolled_back = model_registry.rollback(root=registry_root)
    assert rolled_back["active"] == "synthetic-logreg-0.1.0"
    assert [entry["action"] for entry in read_registry(registry_root)["history"]][-2:] == ["promote", "rollback"]


def test_promotion_verifies_the_artifact_first(registry_root, tmp_path):
    broken = tmp_path / "broken"
    shutil.copytree(DEFAULT_ARTIFACT_DIR, broken)
    (broken / "model.joblib").write_bytes(b"not a model")
    with pytest.raises(ArtifactError):
        model_registry.promote(broken, root=registry_root)
    assert read_registry(registry_root)["active"] == "synthetic-logreg-0.1.0"


def test_rollback_without_a_previous_artifact_is_refused(registry_root):
    with pytest.raises(PipelineError, match="No previous artifact"):
        model_registry.rollback(root=registry_root)

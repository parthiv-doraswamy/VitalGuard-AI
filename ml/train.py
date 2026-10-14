"""Train a versioned model artifact.

    python ml/train.py --experiment mimic_format_fixture [--check-reproducible]
    python ml/train.py --experiment synthetic_demo      # rebuilds the committed demo API artifact

Baseline: the same StandardScaler + LogisticRegression pipeline the API uses.
The regularisation strength C and the decision threshold are chosen on the
validation split only. This script never reads test-split labels or features;
held-out evaluation is ml/evaluate.py.

The artifact (model.joblib + manifest.json) is written with the backend's own
saver and immediately re-loaded with the backend's verifying loader.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from common import (ARTIFACTS_DIR, REPO_ROOT, RUNS_DIR, PipelineError, config_sha256, git_commit, load_config,
                    sha256_file, sha256_ids, write_json)
from app.model import FEATURES, MODEL_VERSION, build_model
from app.model_artifact import load_artifact, save_artifact
from metrics import paired_bootstrap_difference, prediction_metrics
from model_registry import BASELINE, CANDIDATES, backend_runtime_supports, installed

SELECTION_METRICS = {"average_precision": average_precision_score, "roc_auc": roc_auc_score}


def load_dataset(dataset_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest = json.loads((dataset_dir / "dataset_manifest.json").read_text())
    path = dataset_dir / "dataset.csv"
    if sha256_file(path) != manifest["dataset_sha256"]:
        raise PipelineError("dataset.csv does not match its manifest hash; re-run prepare_dataset.py")
    rows = pd.read_csv(path, dtype={"patient_id": str, "split_group": str})
    check_patient_disjoint(rows)
    return rows, manifest


def check_patient_disjoint(rows: pd.DataFrame) -> None:
    """Fail if any patient appears in more than one split (patient leakage)."""
    splits_per_patient = rows.groupby("patient_id")["split"].nunique()
    leaking = splits_per_patient[splits_per_patient > 1]
    if len(leaking):
        raise PipelineError(f"Patient leakage: {len(leaking)} patients appear in more than one split")


def select_threshold(labels: np.ndarray, probabilities: np.ndarray, threshold_config: dict[str, Any]) -> dict[str, Any]:
    """Highest threshold whose sensitivity on these (validation) rows reaches the target."""
    if threshold_config["strategy"] != "target_sensitivity":
        raise PipelineError(f"Unknown threshold strategy {threshold_config['strategy']}")
    target = threshold_config["target_sensitivity"]
    positives = labels == 1
    if positives.sum() == 0:
        raise PipelineError("Validation split has no positive labels; cannot select a threshold")
    best = float(np.min(probabilities))
    for candidate in np.unique(probabilities)[::-1]:
        if (probabilities[positives] >= candidate).mean() >= target:
            best = float(candidate)
            break
    predicted = probabilities >= best
    return {"value": best, "selected_on": "validation", "strategy": "target_sensitivity", "target_sensitivity": target,
            "validation_sensitivity": round(float(predicted[positives].mean()), 4),
            "validation_specificity": round(float((~predicted[~positives]).mean()), 4) if (~positives).any() else None}


def _split_xy(part: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    return part[list(FEATURES)].to_numpy(float), part["label"].to_numpy(int)


def fit_candidate(rows: pd.DataFrame, config: dict[str, Any], name: str) -> dict[str, Any]:
    """Search one candidate's grid on validation; the final model is fitted on train only.

    Every candidate goes through this same function: same rows, same patient-level
    split, same feature order, same selection metric and threshold policy. Test
    rows are never touched.
    """
    candidate = CANDIDATES[name]
    train = rows[rows["split"] == "train"]
    validation = rows[rows["split"] == "validation"]
    if train["label"].nunique() < 2 or validation["label"].nunique() < 2:
        raise PipelineError("Train and validation splits each need both outcome classes")
    x_train, y_train = _split_xy(train)
    x_val, y_val = _split_xy(validation)
    context = {"negative_to_positive_ratio": float((y_train == 0).sum() / max(1, (y_train == 1).sum()))}
    metric = SELECTION_METRICS[config["model"]["selection_metric"]]
    search, best = [], None
    for params in candidate.grid(config):
        pipeline = candidate.build(config, params, context).fit(x_train, y_train)
        probabilities = pipeline.predict_proba(x_val)[:, 1]
        search.append({**params, "validation_average_precision": round(float(average_precision_score(y_val, probabilities)), 6),
                       "validation_roc_auc": round(float(roc_auc_score(y_val, probabilities)), 6)})
        score = metric(y_val, probabilities)
        # Ties keep the earlier (simpler / more regularised) grid entry.
        if best is None or score > best[0] + 1e-12:
            best = (score, params, pipeline, probabilities)
    _, params, pipeline, val_probabilities = best
    return {"candidate": name, "pipeline": pipeline, "params": params, "search": search,
            "threshold": select_threshold(y_val, val_probabilities, config["threshold"]),
            "validation_probabilities": val_probabilities,
            "train_patients": sorted(train["patient_id"].unique()), "validation_patients": sorted(validation["patient_id"].unique())}


def fit_baseline(rows: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """The logistic-regression baseline (same structure as the deployed demo model)."""
    fitted = fit_candidate(rows, config, BASELINE)
    return {**fitted, "C": fitted["params"]["C"]}


def train_baseline(experiment: str, dataset_dir: Path | None = None, out_root: Path | None = None,
                   config: dict[str, Any] | None = None, check_reproducible: bool = False) -> dict[str, Any]:
    config = config or load_config(experiment)
    dataset_dir = Path(dataset_dir or RUNS_DIR / experiment / "dataset")
    rows, dataset = load_dataset(dataset_dir)
    if dataset["config_sha256"] != config_sha256(config):
        raise PipelineError("Dataset was prepared with a different configuration; re-run prepare_dataset.py")
    fitted = fit_baseline(rows, config)
    if check_reproducible:
        verify_reproducible(fitted, fit_baseline(rows, config), config["reproducibility"]["abs_tolerance"])

    config_hash = config_sha256(config)
    version = f"{config['model']['name']}-{experiment.replace('_', '-')}-{dataset['dataset_sha256'][:8]}-{config_hash[:8]}"
    out_dir = Path(out_root or ARTIFACTS_DIR) / version
    manifest = save_artifact(fitted["pipeline"], out_dir, FEATURES,
                             _research_manifest(experiment, config, dataset, fitted, version, check_reproducible))
    load_artifact(out_dir, FEATURES)  # the backend loader must accept what we just wrote
    return {"artifact_dir": out_dir, "manifest": manifest}


def verify_reproducible(first: dict[str, Any], second: dict[str, Any], tolerance: float) -> None:
    a, b = first["pipeline"], second["pipeline"]
    checks = {
        "coefficients": np.abs(a.named_steps["classifier"].coef_ - b.named_steps["classifier"].coef_).max(),
        "intercept": np.abs(a.named_steps["classifier"].intercept_ - b.named_steps["classifier"].intercept_).max(),
        "scaler_mean": np.abs(a.named_steps["scale"].mean_ - b.named_steps["scale"].mean_).max(),
        "threshold": abs(first["threshold"]["value"] - second["threshold"]["value"]),
    }
    failures = {name: float(delta) for name, delta in checks.items() if delta > tolerance}
    if failures or first["C"] != second["C"]:
        raise PipelineError(f"Training is not reproducible within {tolerance}: {failures or 'selected C differs'}")


def train_synthetic_demo(config: dict[str, Any] | None = None, out_dir: Path | None = None) -> dict[str, Any]:
    """Rebuild the demo API artifact: generated data, heuristic labels, identical to the previous in-process model."""
    from app.model_evaluation import evaluate_synthetic_holdout
    from app.synthetic_data import LABEL_DEFINITION, SYNTHETIC_SAMPLES, SYNTHETIC_SEED
    config = config or load_config("synthetic_demo")
    out_dir = Path(out_dir or REPO_ROOT / config["output_dir"])
    pipeline = build_model()
    manifest = save_artifact(pipeline, out_dir, FEATURES, {
        "model_version": MODEL_VERSION,
        "intended_use": "software demonstration only — synthetic data, not a clinical model",
        "clinically_validated": False,
        "dataset": {"kind": "synthetic-demo", "id": f"synthetic-demo-seed{SYNTHETIC_SEED}-n{SYNTHETIC_SAMPLES}",
                    "source": "backend/app/synthetic_data.py", "synthetic_fixture": False,
                    "description": "generated synthetic observations only", "label_definition": LABEL_DEFINITION},
        "training": {"run_id": str(uuid.uuid4()), "experiment": "synthetic_demo", "seed": SYNTHETIC_SEED, "random_state": 42,
                     "algorithm": "StandardScaler + LogisticRegression", "fitted_on": "all generated rows",
                     "git_commit": git_commit(), "config_sha256": config_sha256(config)},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    write_json(out_dir / "evaluation.json", evaluate_synthetic_holdout())
    load_artifact(out_dir, FEATURES)
    return {"artifact_dir": out_dir, "manifest": manifest}


def _research_manifest(experiment: str, config: dict[str, Any], dataset: dict[str, Any], fitted: dict[str, Any],
                       version: str, check_reproducible: bool) -> dict[str, Any]:
    candidate = CANDIDATES[fitted["candidate"]]
    classifier = fitted["pipeline"].named_steps["classifier"]
    training = {"run_id": str(uuid.uuid4()), "experiment": experiment, "seed": config["split"]["seed"],
                "random_state": config["model"]["random_state"], "config_version": config["config_version"],
                "config_sha256": config_sha256(config), "git_commit": git_commit(), "candidate": candidate.name,
                "algorithm": candidate.algorithm, "hyperparameters": fitted["params"],
                "selection_metric": config["model"]["selection_metric"], "hyperparameter_search": fitted["search"],
                "fitted_on": "train split only", "reproducibility_checked": check_reproducible}
    if candidate.linear:
        training.update({"selected_C": fitted["params"]["C"], "coefficients": [float(v) for v in classifier.coef_[0]],
                         "intercept": float(classifier.intercept_[0])})
    return {
        "model_version": version,
        "intended_use": "research experiment — not for clinical use; not served by the demo API",
        "clinically_validated": False,
        "dataset": {"kind": dataset["kind"], "id": dataset["dataset_version"], "sha256": dataset["dataset_sha256"],
                    "source": dataset["source"], "synthetic_fixture": dataset["synthetic_fixture"],
                    "description": ("fictional MIMIC-format fixture (synthetic)" if dataset["synthetic_fixture"]
                                    else f"{dataset['source']} ({dataset['kind']})")},
        "target": config["target"],
        "feature_definitions": config["features"],
        "split": {**config["split"], "summary": dataset["splits"],
                  "train_patient_ids_sha256": sha256_ids(fitted["train_patients"]),
                  "validation_patient_ids_sha256": sha256_ids(fitted["validation_patients"])},
        "training": training,
        "decision_threshold": fitted["threshold"],
    }


def measure_latency(artifact_dir: Path, rows: np.ndarray, settings: dict[str, Any]) -> dict[str, Any]:
    """Single-observation inference time through the backend loader, as the API would call it."""
    pipeline, _ = load_artifact(artifact_dir, FEATURES)
    for index in range(settings["warmup_calls"]):
        pipeline.predict_proba(rows[index % len(rows)].reshape(1, -1))
    timings = []
    for index in range(settings["timed_calls"]):
        started = time.perf_counter()
        pipeline.predict_proba(rows[index % len(rows)].reshape(1, -1))
        timings.append((time.perf_counter() - started) * 1000)
    return {"single_row_p50_ms": round(float(np.percentile(timings, 50)), 3),
            "single_row_p95_ms": round(float(np.percentile(timings, 95)), 3), "calls": len(timings),
            "machine": {"platform": platform.platform(), "processor": platform.processor() or platform.machine(),
                        "cpu_count": os.cpu_count(), "python": platform.python_version()}}


def benchmark(experiment: str, dataset_dir: Path | None = None, out_root: Path | None = None,
              config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Train every candidate identically, apply the predefined gates and selection rule, freeze the decision.

    Writes <out_root>/benchmarks/<benchmark_id>/candidates/<version>/ and selection.json.
    Only validation data informs the decision; ml/evaluate.py --benchmark scores the test split afterwards.
    """
    config = config or load_config(experiment)
    rows, dataset = load_dataset(Path(dataset_dir or RUNS_DIR / experiment / "dataset"))
    if dataset["config_sha256"] != config_sha256(config):
        raise PipelineError("Dataset was prepared with a different configuration; re-run prepare_dataset.py")
    config_hash = config_sha256(config)
    benchmark_id = f"benchmark-{experiment.replace('_', '-')}-{dataset['dataset_sha256'][:8]}-{config_hash[:8]}"
    out_dir = Path(out_root or ARTIFACTS_DIR) / "benchmarks" / benchmark_id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    validation = rows[rows["split"] == "validation"].reset_index(drop=True)
    x_val, y_val = _split_xy(validation)
    selection_settings, gates = config["selection"], config["selection"]["gates"]
    bins = config["evaluation"]["calibration_bins"]

    results: dict[str, dict[str, Any]] = {}
    fitted_by_name: dict[str, dict[str, Any]] = {}
    for name, candidate in CANDIDATES.items():
        entry: dict[str, Any] = {"candidate": name, "algorithm": candidate.algorithm, "complexity": candidate.complexity}
        if not installed(candidate):
            results[name] = {**entry, "status": "skipped", "reason": f"{candidate.runtime_package} is not installed"}
            continue
        fitted = fit_candidate(rows, config, name)
        fitted_by_name[name] = fitted
        version = f"{name.replace('_', '-')}-{experiment.replace('_', '-')}-{dataset['dataset_sha256'][:8]}-{config_hash[:8]}"
        artifact_dir = out_dir / "candidates" / version
        manifest = save_artifact(fitted["pipeline"], artifact_dir, FEATURES,
                                 _research_manifest(experiment, config, dataset, fitted, version, False))
        validation_metrics = prediction_metrics(y_val, fitted["validation_probabilities"], fitted["threshold"]["value"], bins)
        latency = measure_latency(artifact_dir, x_val, selection_settings["latency"])
        size = (artifact_dir / "model.joblib").stat().st_size
        slope = validation_metrics["calibration"].get("calibration_slope")
        gate_results = {
            "loadable_by_backend_runtime": backend_runtime_supports(candidate) or not gates["loadable_by_backend_runtime"],
            "single_row_p95_latency": latency["single_row_p95_ms"] <= gates["max_single_row_p95_latency_ms"],
            "artifact_size": size <= gates["max_artifact_bytes"],
            "validation_sensitivity": (validation_metrics["sensitivity"] or 0) >= gates["min_validation_sensitivity"],
            "validation_calibration_slope": slope is not None and abs(slope - 1) <= gates["max_abs_calibration_slope_error"],
        }
        results[name] = {**entry, "status": "trained", "model_version": version, "artifact": f"candidates/{version}",
                         "manifest_sha256": sha256_file(artifact_dir / "manifest.json"),
                         "hyperparameters": fitted["params"], "threshold": fitted["threshold"],
                         "validation": validation_metrics, "latency": latency, "artifact_bytes": size,
                         "gates": gate_results, "eligible": all(gate_results.values())}

    if BASELINE not in fitted_by_name:
        raise PipelineError("The logistic-regression baseline could not be trained")
    baseline_probabilities = fitted_by_name[BASELINE]["validation_probabilities"]
    for name, fitted in fitted_by_name.items():
        if name != BASELINE:
            results[name]["paired_vs_baseline"] = paired_bootstrap_difference(
                validation, fitted["validation_probabilities"], baseline_probabilities,
                selection_settings["paired_bootstrap_samples"], selection_settings["bootstrap_seed"])

    decision = select_model(results, selection_settings)
    selection = {
        "benchmark_id": benchmark_id, "experiment": experiment, "frozen_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {"version": dataset["dataset_version"], "sha256": dataset["dataset_sha256"], "kind": dataset["kind"],
                    "synthetic_fixture": dataset["synthetic_fixture"]},
        "config_sha256": config_hash, "features": list(FEATURES), "target": config["target"]["id"],
        "split": {"strategy": config["split"]["strategy"], "seed": config["split"]["seed"],
                  "train_patient_ids_sha256": sha256_ids(fitted_by_name[BASELINE]["train_patients"]),
                  "validation_patient_ids_sha256": sha256_ids(fitted_by_name[BASELINE]["validation_patients"])},
        "policy": {key: selection_settings[key] for key in ("primary_metric", "min_improvement", "gates")},
        "candidates": results, "decision": decision,
        "selection_inputs": "validation split only; test split not yet evaluated",
    }
    write_json(out_dir / "selection.json", selection)
    return {"benchmark_dir": out_dir, "selection": selection}


def select_model(results: dict[str, dict[str, Any]], settings: dict[str, Any]) -> dict[str, Any]:
    """Apply the predefined rule: baseline unless a gated candidate is meaningfully and robustly better.

    If the baseline itself fails a gate, the eligible candidate with the best validation
    primary metric is chosen (ties go to the simpler model); if none is eligible, nothing is selected.
    """
    metric_key = {"average_precision": "pr_auc_average_precision", "roc_auc": "roc_auc"}[settings["primary_metric"]]
    ordered = sorted(results.items(), key=lambda item: item[1]["complexity"])
    rationale = [f"{name}: skipped ({result['reason']})" for name, result in ordered if result["status"] != "trained"]
    eligible = [(name, result) for name, result in ordered if result["status"] == "trained" and result["eligible"]]
    rationale += [f"{name}: fails gates {[k for k, ok in result['gates'].items() if not ok]}"
                  for name, result in ordered if result["status"] == "trained" and not result["eligible"]]
    rule = ("baseline unless a gated candidate improves the primary metric by >= min_improvement "
            "with paired patient-bootstrap 95% CI lower bound > 0; ties go to the simpler model")
    if not eligible:
        return {"selected": None, "rule": "no candidate passed the gates", "rationale": rationale}

    if not results[BASELINE].get("eligible"):
        best_name, _ = max(eligible, key=lambda item: (item[1]["validation"][metric_key] or 0, -item[1]["complexity"]))
        rationale.append(f"baseline is not deployable; selected {best_name}, the eligible candidate with the best "
                         f"validation {settings['primary_metric']}")
        return {"selected": best_name, "selected_model_version": results[best_name]["model_version"],
                "rule": "baseline not eligible: best eligible validation primary metric, ties to the simpler model",
                "rationale": rationale}

    best, best_gain = BASELINE, 0.0
    for name, result in eligible:
        if name == BASELINE:
            continue
        paired = result["paired_vs_baseline"]
        robust = paired["ci95"] is not None and paired["ci95"][0] > 0
        if paired["difference"] >= settings["min_improvement"] and robust:
            rationale.append(f"{name}: validation {settings['primary_metric']} +{paired['difference']} vs baseline, CI {paired['ci95']}")
            if paired["difference"] > best_gain:
                best, best_gain = name, paired["difference"]
        else:
            rationale.append(f"{name}: gain {paired['difference']} (CI {paired['ci95']}) does not meet "
                             f"min_improvement {settings['min_improvement']} with CI lower bound > 0")
    rationale.append(f"selected {best}" + (" (simplest model; no candidate met the improvement rule)" if best == BASELINE else ""))
    return {"selected": best, "selected_model_version": results[best]["model_version"], "rule": rule, "rationale": rationale}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--dataset", type=Path, help="prepared dataset directory (default ml/runs/<experiment>/dataset)")
    parser.add_argument("--check-reproducible", action="store_true", help="train twice and compare within the configured tolerance")
    parser.add_argument("--benchmark", action="store_true", help="train and compare all candidate algorithms")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.experiment)
        if args.benchmark:
            result = benchmark(args.experiment, args.dataset, config=config)
            decision = result["selection"]["decision"]
            print(f"benchmark {result['selection']['benchmark_id']} -> {result['benchmark_dir']}")
            for line in decision["rationale"]:
                print(f"  {line}")
            print("  selection frozen (validation only). Next: python ml/evaluate.py --benchmark " + str(result["benchmark_dir"]))
            return 0
        if config["source"] == "synthetic-demo":
            result = train_synthetic_demo(config)
        else:
            result = train_baseline(args.experiment, args.dataset, config=config, check_reproducible=args.check_reproducible)
    except PipelineError as exc:
        print(str(exc))
        return 2
    manifest = result["manifest"]
    print(f"artifact {manifest['model_version']} -> {result['artifact_dir']}")
    if "decision_threshold" in manifest:
        print(f"  selected C={manifest['training']['selected_C']} threshold={manifest['decision_threshold']['value']:.4f} "
              f"(validation sensitivity {manifest['decision_threshold']['validation_sensitivity']})")
    if args.check_reproducible:
        print("  reproducibility check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

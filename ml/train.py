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
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from common import (ARTIFACTS_DIR, REPO_ROOT, RUNS_DIR, PipelineError, config_sha256, git_commit, load_config,
                    sha256_file, sha256_ids, write_json)
from app.model import FEATURES, MODEL_VERSION, build_model
from app.model_artifact import load_artifact, save_artifact

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


def make_pipeline(config: dict[str, Any], c_value: float) -> Pipeline:
    model = config["model"]
    return Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(C=c_value, class_weight=model["class_weight"], max_iter=model["max_iter"],
                                          random_state=model["random_state"])),
    ])


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


def fit_baseline(rows: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Grid-search C on validation, then fit the final model on train only. Test rows are never touched."""
    train = rows[rows["split"] == "train"]
    validation = rows[rows["split"] == "validation"]
    if train["label"].nunique() < 2 or validation["label"].nunique() < 2:
        raise PipelineError("Train and validation splits each need both outcome classes")
    x_train, y_train = train[list(FEATURES)].to_numpy(float), train["label"].to_numpy(int)
    x_val, y_val = validation[list(FEATURES)].to_numpy(float), validation["label"].to_numpy(int)
    metric_name = config["model"]["selection_metric"]
    metric = SELECTION_METRICS[metric_name]
    search = []
    best = None
    for c_value in config["model"]["c_grid"]:
        pipeline = make_pipeline(config, c_value).fit(x_train, y_train)
        probabilities = pipeline.predict_proba(x_val)[:, 1]
        result = {"C": c_value, "validation_average_precision": round(float(average_precision_score(y_val, probabilities)), 6),
                  "validation_roc_auc": round(float(roc_auc_score(y_val, probabilities)), 6)}
        search.append(result)
        score = metric(y_val, probabilities)
        # Ties keep the smaller C (stronger regularisation).
        if best is None or score > best[0] + 1e-12:
            best = (score, c_value, pipeline, probabilities)
    _, c_value, pipeline, val_probabilities = best
    return {"pipeline": pipeline, "C": c_value, "search": search,
            "threshold": select_threshold(y_val, val_probabilities, config["threshold"]),
            "train_patients": sorted(train["patient_id"].unique()), "validation_patients": sorted(validation["patient_id"].unique())}


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
    classifier = fitted["pipeline"].named_steps["classifier"]
    manifest = save_artifact(fitted["pipeline"], out_dir, FEATURES, {
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
        "training": {"run_id": str(uuid.uuid4()), "experiment": experiment, "seed": config["split"]["seed"],
                     "random_state": config["model"]["random_state"], "config_version": config["config_version"],
                     "config_sha256": config_hash, "git_commit": git_commit(),
                     "algorithm": "StandardScaler + LogisticRegression", "selected_C": fitted["C"],
                     "selection_metric": config["model"]["selection_metric"], "hyperparameter_search": fitted["search"],
                     "fitted_on": "train split only", "coefficients": [float(v) for v in classifier.coef_[0]],
                     "intercept": float(classifier.intercept_[0]), "reproducibility_checked": check_reproducible},
        "decision_threshold": fitted["threshold"],
    })
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--dataset", type=Path, help="prepared dataset directory (default ml/runs/<experiment>/dataset)")
    parser.add_argument("--check-reproducible", action="store_true", help="train twice and compare within the configured tolerance")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.experiment)
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

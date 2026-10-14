"""Held-out evaluation of a trained artifact on the test split.

    python ml/evaluate.py --artifact ml/artifacts/<model_version> [--dataset ml/runs/<experiment>/dataset]

The artifact is loaded with the backend's verifying loader (proving the API can
load it). Evaluation refuses to run unless the dataset is byte-identical to the
one used for training, the train/validation patient sets match the manifest,
and no test patient appears in them. The decision threshold is the one stored
at training time (selected on validation); nothing is tuned here.

Writes evaluation.json and evaluation.md next to the artifact.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from common import RUNS_DIR, PipelineError, load_config, sha256_ids, write_json
from train import load_dataset
from app.model import FEATURES
from app.model_artifact import load_artifact

DISCLAIMER = ("Research evaluation only. Not clinically validated; not for diagnosis, triage or treatment decisions. "
              "Performance on one retrospective dataset does not establish clinical safety or effectiveness.")


def _safe(metric, labels: np.ndarray, scores: np.ndarray) -> float | None:
    return float(metric(labels, scores)) if len(np.unique(labels)) == 2 else None


def threshold_metrics(labels: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    predicted = probabilities >= threshold
    tp = int((predicted & (labels == 1)).sum()); fp = int((predicted & (labels == 0)).sum())
    tn = int((~predicted & (labels == 0)).sum()); fn = int((~predicted & (labels == 1)).sum())
    ratio = lambda num, den: round(num / den, 4) if den else None  # noqa: E731
    return {"threshold": threshold, "sensitivity": ratio(tp, tp + fn), "specificity": ratio(tn, tn + fp),
            "precision_ppv": ratio(tp, tp + fp), "npv": ratio(tn, tn + fn),
            "alerts_per_100_predictions": ratio(100 * (tp + fp), len(labels)),
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}}


def calibration(labels: np.ndarray, probabilities: np.ndarray, bins: int) -> dict[str, Any]:
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(probabilities, edges[1:-1]), 0, bins - 1)
    table = [{"bin": f"{edges[i]:.1f}-{edges[i + 1]:.1f}", "count": int((index == i).sum()),
              "mean_predicted": round(float(probabilities[index == i].mean()), 4) if (index == i).any() else None,
              "observed_rate": round(float(labels[index == i].mean()), 4) if (index == i).any() else None}
             for i in range(bins)]
    result: dict[str, Any] = {"brier_score": round(float(brier_score_loss(labels, probabilities)), 5), "reliability_table": table,
                              "note": "class_weight='balanced' training shifts probabilities upward; scores are not calibrated risks."}
    if len(np.unique(labels)) == 2:
        logit = np.log(np.clip(probabilities, 1e-6, 1 - 1e-6) / np.clip(1 - probabilities, 1e-6, 1))
        fit = LogisticRegression(C=1e6, max_iter=1000).fit(logit.reshape(-1, 1), labels)
        result.update({"calibration_slope": round(float(fit.coef_[0, 0]), 4), "calibration_intercept": round(float(fit.intercept_[0]), 4)})
    return result


def bootstrap(rows, probabilities: np.ndarray, samples: int, seed: int) -> dict[str, Any]:
    """Patient-level bootstrap: resample patients, keeping each patient's rows together."""
    rng = np.random.default_rng(seed)
    labels = rows["label"].to_numpy(int)
    groups = rows.groupby("patient_id").indices
    patients = list(groups)
    stats: dict[str, list[float]] = {"roc_auc": [], "pr_auc": []}
    for _ in range(samples):
        chosen = np.concatenate([groups[patients[i]] for i in rng.integers(0, len(patients), len(patients))])
        if len(np.unique(labels[chosen])) < 2:
            continue
        stats["roc_auc"].append(roc_auc_score(labels[chosen], probabilities[chosen]))
        stats["pr_auc"].append(average_precision_score(labels[chosen], probabilities[chosen]))
    return {name: ({"ci95": [round(float(np.percentile(values, 2.5)), 4), round(float(np.percentile(values, 97.5)), 4)],
                    "resamples_used": len(values)} if values else None) for name, values in stats.items()}


def evaluate(artifact_dir: Path, dataset_dir: Path | None = None) -> dict[str, Any]:
    pipeline, manifest = load_artifact(artifact_dir, FEATURES)
    if "decision_threshold" not in manifest:
        raise PipelineError("Artifact has no validation-selected threshold (synthetic demo artifacts are evaluated by the API)")
    experiment = manifest["training"]["experiment"]
    rows, dataset = load_dataset(Path(dataset_dir or RUNS_DIR / experiment / "dataset"))
    if dataset["dataset_sha256"] != manifest["dataset"]["sha256"]:
        raise PipelineError("Dataset version differs from the one the artifact was trained on")
    train_ids = rows.loc[rows["split"] == "train", "patient_id"].unique()
    validation_ids = rows.loc[rows["split"] == "validation", "patient_id"].unique()
    if (sha256_ids(train_ids) != manifest["split"]["train_patient_ids_sha256"]
            or sha256_ids(validation_ids) != manifest["split"]["validation_patient_ids_sha256"]):
        raise PipelineError("Train/validation patients differ from training; the split is not the one the model saw")
    test = rows[rows["split"] == "test"].reset_index(drop=True)
    if set(test["patient_id"]) & (set(train_ids) | set(validation_ids)):
        raise PipelineError("Test patients overlap train/validation patients")
    if test.empty:
        raise PipelineError("Test split is empty")

    labels = test["label"].to_numpy(int)
    probabilities = pipeline.predict_proba(test[list(FEATURES)].to_numpy(float))[:, 1]
    config = load_config(experiment)["evaluation"]
    report = {
        "model_version": manifest["model_version"],
        "evaluation_type": "held-out test split (patient-disjoint), evaluated once with the validation-selected threshold",
        "dataset": manifest["dataset"],
        "target": manifest["target"],
        "test_rows": int(len(test)), "test_patients": int(test["patient_id"].nunique()),
        "test_positives": int(labels.sum()), "test_prevalence": round(float(labels.mean()), 4),
        "metrics": {"roc_auc": _safe(roc_auc_score, labels, probabilities),
                    "pr_auc_average_precision": _safe(average_precision_score, labels, probabilities),
                    **threshold_metrics(labels, probabilities, manifest["decision_threshold"]["value"])},
        "threshold_provenance": manifest["decision_threshold"],
        "bootstrap_95ci_patient_level": bootstrap(test, probabilities, config["bootstrap_samples"], config["bootstrap_seed"]),
        "calibration": calibration(labels, probabilities, config["calibration_bins"]),
        "leakage_checks": {"patient_disjoint_splits": True, "dataset_hash_matches_training": True,
                           "train_validation_patients_match_manifest": True,
                           "features_use_only_values_stored_at_or_before_prediction_time": True},
        "clinically_validated": False,
        "disclaimer": DISCLAIMER if not manifest["dataset"].get("synthetic_fixture") else
            "SYNTHETIC FIXTURE: these numbers describe fictional generated data and are meaningless as model performance.",
    }
    write_json(artifact_dir / "evaluation.json", report)
    (artifact_dir / "evaluation.md").write_text(_markdown(report))
    return report


def _markdown(report: dict[str, Any]) -> str:
    m = report["metrics"]
    ci = report["bootstrap_95ci_patient_level"]
    fmt = lambda v: "n/a" if v is None else f"{v:.4f}" if isinstance(v, float) else str(v)  # noqa: E731
    lines = [f"# Evaluation — {report['model_version']}", "", f"> {report['disclaimer']}", "",
             f"- Dataset: {report['dataset']['id']} ({report['dataset']['kind']})",
             f"- Target: {report['target']['id']}",
             f"- Test split: {report['test_rows']} rows, {report['test_patients']} patients, prevalence {report['test_prevalence']}",
             f"- Threshold {m['threshold']:.4f} selected on validation for sensitivity ≥ {report['threshold_provenance']['target_sensitivity']}",
             "", "| Metric | Value | 95% CI (patient bootstrap) |", "| --- | --- | --- |",
             f"| ROC-AUC | {fmt(m['roc_auc'])} | {ci['roc_auc']['ci95'] if ci['roc_auc'] else 'n/a'} |",
             f"| PR-AUC | {fmt(m['pr_auc_average_precision'])} | {ci['pr_auc']['ci95'] if ci['pr_auc'] else 'n/a'} |",
             f"| Sensitivity | {fmt(m['sensitivity'])} | |", f"| Specificity | {fmt(m['specificity'])} | |",
             f"| Precision (PPV) | {fmt(m['precision_ppv'])} | |", f"| NPV | {fmt(m['npv'])} | |",
             f"| Brier score | {fmt(report['calibration']['brier_score'])} | |",
             f"| Calibration slope / intercept | {fmt(report['calibration'].get('calibration_slope'))} / {fmt(report['calibration'].get('calibration_intercept'))} | |", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--dataset", type=Path)
    args = parser.parse_args(argv)
    try:
        evaluate(args.artifact, args.dataset)
    except PipelineError as exc:
        print(str(exc))
        return 2
    print((args.artifact / "evaluation.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

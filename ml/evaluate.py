"""Held-out evaluation of a trained artifact on the test split.

    python ml/evaluate.py --artifact ml/artifacts/<model_version> [--dataset ml/runs/<experiment>/dataset]

The artifact is loaded with the backend's verifying loader (proving the API can
load it). Evaluation refuses to run unless the dataset is byte-identical to the
one used for training, the train/validation patient sets match the manifest,
and no test patient appears in them. The decision threshold is the one stored
at training time (selected on validation); nothing is tuned here.

Writes evaluation.json, evaluation.md and test_predictions.csv (row ids, label,
probability) next to the artifact; every metric is computed from that saved file.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from common import RUNS_DIR, PipelineError, load_config, sha256_file, sha256_ids, write_json
from metrics import bootstrap, prediction_metrics
from train import load_dataset
from app.model import FEATURES
from app.model_artifact import load_artifact

PREDICTIONS_FILE = "test_predictions.csv"
DISCLAIMER = ("Research evaluation only. Not clinically validated; not for diagnosis, triage or treatment decisions. "
              "Performance on one retrospective dataset does not establish clinical safety or effectiveness.")


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

    predictions = test[["patient_id", "stay_id", "prediction_time", "label"]].copy()
    predictions["probability"] = pipeline.predict_proba(test[list(FEATURES)].to_numpy(float))[:, 1]
    predictions_path = artifact_dir / PREDICTIONS_FILE
    predictions.to_csv(predictions_path, index=False)
    # Every reported number is computed from the saved file, so it can be re-derived independently.
    saved = pd.read_csv(predictions_path, dtype={"patient_id": str})
    labels, probabilities = saved["label"].to_numpy(int), saved["probability"].to_numpy(float)
    config = load_config(experiment)["evaluation"]
    computed = prediction_metrics(labels, probabilities, manifest["decision_threshold"]["value"], config["calibration_bins"])
    calibration_report = computed.pop("calibration")
    report = {
        "model_version": manifest["model_version"],
        "evaluation_type": "held-out test split (patient-disjoint), evaluated once with the validation-selected threshold",
        "dataset": manifest["dataset"],
        "target": manifest["target"],
        "test_rows": int(len(test)), "test_patients": int(test["patient_id"].nunique()),
        "test_positives": int(labels.sum()), "test_prevalence": round(float(labels.mean()), 4),
        "metrics": computed,
        "predictions_file": PREDICTIONS_FILE,
        "predictions_sha256": sha256_file(predictions_path),
        "threshold_provenance": manifest["decision_threshold"],
        "bootstrap_95ci_patient_level": bootstrap(saved, probabilities, config["bootstrap_samples"], config["bootstrap_seed"]),
        "calibration": calibration_report,
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


def evaluate_benchmark(benchmark_dir: Path, dataset_dir: Path | None = None) -> dict[str, Any]:
    """Score every candidate on the test split after the selection was frozen, then write the comparison report."""
    benchmark_dir = Path(benchmark_dir)
    selection_path = benchmark_dir / "selection.json"
    selection = json.loads(selection_path.read_text())
    selection_sha = sha256_file(selection_path)
    trained = {name: item for name, item in selection["candidates"].items() if item["status"] == "trained"}
    reference = None
    for name, item in trained.items():
        manifest_path = benchmark_dir / item["artifact"] / "manifest.json"
        if sha256_file(manifest_path) != item["manifest_sha256"]:
            raise PipelineError(f"{name}: artifact manifest changed after the selection was frozen")
        manifest = json.loads(manifest_path.read_text())
        comparable = (manifest["dataset"]["sha256"], manifest["features"], manifest["split"]["train_patient_ids_sha256"],
                      manifest["split"]["validation_patient_ids_sha256"], manifest["training"]["config_sha256"])
        if reference is None:
            reference = comparable
        elif comparable != reference:
            raise PipelineError(f"{name} was not trained on the same dataset, features, splits and configuration")

    reports = {name: evaluate(benchmark_dir / item["artifact"], dataset_dir) for name, item in trained.items()}
    decision = selection["decision"]
    rows = []
    for name, item in selection["candidates"].items():
        test = reports.get(name)
        rows.append({
            "candidate": name, "algorithm": item["algorithm"], "status": item["status"],
            "model_version": item.get("model_version"), "eligible": item.get("eligible"), "gates": item.get("gates"),
            "selected": name == decision.get("selected"),
            "validation": {key: item["validation"][key] for key in ("roc_auc", "pr_auc_average_precision", "sensitivity",
                                                                     "specificity", "precision_ppv")} | {
                "brier_score": item["validation"]["calibration"]["brier_score"],
                "calibration_slope": item["validation"]["calibration"].get("calibration_slope")} if test else None,
            "paired_vs_baseline_validation": item.get("paired_vs_baseline"),
            "test": ({key: test["metrics"][key] for key in ("roc_auc", "pr_auc_average_precision", "sensitivity",
                                                            "specificity", "precision_ppv", "npv")} | {
                "brier_score": test["calibration"]["brier_score"],
                "calibration_slope": test["calibration"].get("calibration_slope"),
                "calibration_intercept": test["calibration"].get("calibration_intercept"),
                "predictions_sha256": test["predictions_sha256"]}) if test else None,
            "threshold": item.get("threshold", {}).get("value"),
            "latency": item.get("latency"), "artifact_bytes": item.get("artifact_bytes"),
            "reason": item.get("reason"),
        })
    report = {
        "benchmark_id": selection["benchmark_id"], "dataset": selection["dataset"], "target": selection["target"],
        "features": selection["features"], "split": selection["split"], "policy": selection["policy"],
        "decision": decision, "selection_sha256": selection_sha, "selection_frozen_at": selection["frozen_at"],
        "test_evaluated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "identical features, rows and patient-level splits for every candidate; hyperparameters and "
                    "thresholds chosen on validation; selection frozen before this test evaluation",
        "candidates": rows, "clinically_validated": False,
        "disclaimer": ("SYNTHETIC FIXTURE: these numbers describe fictional generated data and are meaningless as "
                       "model performance." if selection["dataset"]["synthetic_fixture"] else DISCLAIMER),
    }
    write_json(benchmark_dir / "comparison_report.json", report)
    (benchmark_dir / "comparison_report.md").write_text(_comparison_markdown(report))
    if decision.get("selected"):
        chosen_dir = benchmark_dir / selection["candidates"][decision["selected"]]["artifact"]
        manifest = json.loads((chosen_dir / "manifest.json").read_text())
        # Selection metadata travels with the chosen artifact (the model file and its hash are unchanged).
        manifest["selection"] = {"benchmark_id": report["benchmark_id"], "selected": decision["selected"],
                                 "rule": decision["rule"], "rationale": decision["rationale"],
                                 "compared": [row["candidate"] for row in rows], "selection_sha256": selection_sha}
        write_json(chosen_dir / "manifest.json", manifest)
        write_json(chosen_dir / "comparison_report.json", report)
    return report


def _comparison_markdown(report: dict[str, Any]) -> str:
    fmt = lambda v: "n/a" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)  # noqa: E731
    lines = [f"# Model comparison — {report['benchmark_id']}", "", f"> {report['disclaimer']}", "",
             f"- Dataset {report['dataset']['version']} ({report['dataset']['kind']}); target {report['target']}",
             f"- Protocol: {report['protocol']}",
             f"- Decision: **{report['decision'].get('selected')}** — {report['decision']['rule']}", ""]
    lines += [f"  - {line}" for line in report["decision"]["rationale"]]
    lines += ["", "| Candidate | Status | Gates | Val PR-AUC | Val ROC-AUC | Val Brier | Val cal. slope | Test PR-AUC | Test ROC-AUC | "
              "Test sens. | Test spec. | Test Brier | p95 latency ms | Size bytes |", "|" + " --- |" * 14]
    for row in report["candidates"]:
        val, test = row["validation"] or {}, row["test"] or {}
        gates = "pass" if row.get("eligible") else ("—" if row["status"] != "trained" else
                ", ".join(k for k, ok in (row["gates"] or {}).items() if not ok))
        lines.append(f"| {row['candidate']}{' ✔' if row['selected'] else ''} | {row['status']} | {gates} | "
                     f"{fmt(val.get('pr_auc_average_precision'))} | {fmt(val.get('roc_auc'))} | {fmt(val.get('brier_score'))} | "
                     f"{fmt(val.get('calibration_slope'))} | {fmt(test.get('pr_auc_average_precision'))} | {fmt(test.get('roc_auc'))} | "
                     f"{fmt(test.get('sensitivity'))} | {fmt(test.get('specificity'))} | {fmt(test.get('brier_score'))} | "
                     f"{fmt((row['latency'] or {}).get('single_row_p95_ms'))} | {fmt(row['artifact_bytes'])} |")
    return "\n".join(lines) + "\n"


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
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--artifact", type=Path)
    target.add_argument("--benchmark", type=Path, help="benchmark directory written by train.py --benchmark")
    parser.add_argument("--dataset", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.benchmark:
            evaluate_benchmark(args.benchmark, args.dataset)
        else:
            evaluate(args.artifact, args.dataset)
    except PipelineError as exc:
        print(str(exc))
        return 2
    print((args.benchmark / "comparison_report.md" if args.benchmark else args.artifact / "evaluation.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

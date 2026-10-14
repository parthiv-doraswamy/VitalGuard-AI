"""Metric helpers shared by training (validation), evaluation (test) and benchmarking."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


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
                              "note": "Class re-weighting during training shifts probabilities upward; scores are not calibrated risks."}
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


def prediction_metrics(labels: np.ndarray, probabilities: np.ndarray, threshold: float, bins: int = 10) -> dict[str, Any]:
    """Discrimination, operating-point and calibration metrics for one set of predictions."""
    return {"roc_auc": _safe(roc_auc_score, labels, probabilities),
            "pr_auc_average_precision": _safe(average_precision_score, labels, probabilities),
            **threshold_metrics(labels, probabilities, threshold),
            "calibration": calibration(labels, probabilities, bins)}


def metrics_from_predictions(path: Path, threshold: float, bins: int = 10) -> dict[str, Any]:
    """Recompute reported metrics from a saved predictions CSV (label, probability columns)."""
    saved = pd.read_csv(path)
    return prediction_metrics(saved["label"].to_numpy(int), saved["probability"].to_numpy(float), threshold, bins)


def paired_bootstrap_difference(rows: pd.DataFrame, candidate: np.ndarray, baseline: np.ndarray,
                                samples: int, seed: int) -> dict[str, Any]:
    """Patient-level paired bootstrap of average precision(candidate) - average precision(baseline)."""
    rng = np.random.default_rng(seed)
    labels = rows["label"].to_numpy(int)
    groups = rows.groupby("patient_id").indices
    patients = list(groups)
    differences = []
    for _ in range(samples):
        chosen = np.concatenate([groups[patients[i]] for i in rng.integers(0, len(patients), len(patients))])
        if len(np.unique(labels[chosen])) < 2:
            continue
        differences.append(average_precision_score(labels[chosen], candidate[chosen])
                           - average_precision_score(labels[chosen], baseline[chosen]))
    point = float(average_precision_score(labels, candidate) - average_precision_score(labels, baseline))
    if not differences:
        return {"difference": round(point, 4), "ci95": None, "resamples_used": 0}
    return {"difference": round(point, 4), "resamples_used": len(differences),
            "ci95": [round(float(np.percentile(differences, 2.5)), 4), round(float(np.percentile(differences, 97.5)), 4)]}

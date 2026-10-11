"""Synthetic-only calibration and subgroup diagnostics for model validation.

These diagnostics measure agreement with fictional heuristic labels. They are
not clinical calibration, fairness evidence, or a release gate for real care.
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .grouped_feature_evaluation import _synthetic_episodes
from .model import _heuristic_score
from .feature_engineering import RAW_FEATURES

DIAGNOSTICS_VERSION = "synthetic-calibration-subgroups-0.1.0"
MIN_SUBGROUP_ROWS = 20


def _calibration_bins(labels: np.ndarray, probabilities: np.ndarray, bin_count: int = 5) -> list[dict]:
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    result = []
    for index in range(bin_count):
        # Include probability 1.0 in the final bin.
        mask = ((probabilities >= edges[index]) &
                ((probabilities < edges[index + 1]) if index < bin_count - 1 else
                 (probabilities <= edges[index + 1])))
        count = int(mask.sum())
        result.append({
            "bin": index + 1,
            "lower_bound": round(float(edges[index]), 2),
            "upper_bound": round(float(edges[index + 1]), 2),
            "count": count,
            "mean_predicted_probability": round(float(probabilities[mask].mean()), 4) if count else None,
            "observed_positive_fraction": round(float(labels[mask].mean()), 4) if count else None,
        })
    return result


def _subgroup_summary(labels: np.ndarray, predictions: np.ndarray, ages: np.ndarray) -> dict:
    bands = {
        "under_40": ages < 40,
        "age_40_to_64": (ages >= 40) & (ages < 65),
        "age_65_plus": ages >= 65,
    }
    report = {}
    for name, mask in bands.items():
        group_labels, group_predictions = labels[mask], predictions[mask]
        count = int(mask.sum())
        positives = int(group_labels.sum())
        if count < MIN_SUBGROUP_ROWS:
            report[name] = {"count": count, "positive_count": positives,
                            "available": False, "reason": f"fewer than {MIN_SUBGROUP_ROWS} rows"}
        elif len(np.unique(group_labels)) < 2:
            report[name] = {"count": count, "positive_count": positives,
                            "available": False, "reason": "only one label class in subgroup"}
        else:
            report[name] = {
                "count": count, "positive_count": positives, "available": True,
                "precision": round(float(precision_score(group_labels, group_predictions, zero_division=0)), 4),
                "recall": round(float(recall_score(group_labels, group_predictions, zero_division=0)), 4),
            }
    return report


def evaluate_synthetic_calibration_and_subgroups(seed: int = 20261011) -> dict[str, object]:
    """Fit on synthetic subjects and report held-out calibration and age-band diagnostics."""
    episodes = _synthetic_episodes(seed=seed)
    subjects = sorted(episodes)
    train_subjects, test_subjects = train_test_split(subjects, test_size=0.25, random_state=42)
    train_set, test_set = set(train_subjects), set(test_subjects)
    x_train, y_train, x_test, y_test, ages_test = [], [], [], [], []

    for subject_id, observations in episodes.items():
        for observation in observations[1:]:
            vector = [float(observation[name]) for name in RAW_FEATURES]
            score = float(_heuristic_score(np.asarray([vector]))[0])
            noise = ((int(subject_id[-4:]) * 17 + observations.index(observation) * 13 + seed) % 101 - 50) / 10
            label = int(score + noise >= 35)
            if subject_id in train_set:
                x_train.append(vector)
                y_train.append(label)
            elif subject_id in test_set:
                x_test.append(vector)
                y_test.append(label)
                ages_test.append(float(observation["age"]))

    if len(set(y_train)) < 2 or len(set(y_test)) < 2:
        raise ValueError("synthetic evaluation split must contain both label classes")

    pipeline = Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1200, class_weight="balanced", random_state=42)),
    ])
    pipeline.fit(np.asarray(x_train), np.asarray(y_train))
    probabilities = pipeline.predict_proba(np.asarray(x_test))[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    labels = np.asarray(y_test)
    ages = np.asarray(ages_test)
    return {
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "evaluation_type": "synthetic subject-grouped holdout",
        "seed": seed,
        "train_subject_count": len(train_set),
        "test_subject_count": len(test_set),
        "subject_overlap": sorted(train_set & test_set),
        "test_row_count": len(labels),
        "positive_label_count": int(labels.sum()),
        "brier_score": round(float(brier_score_loss(labels, probabilities)), 4),
        "roc_auc": round(float(roc_auc_score(labels, probabilities)), 4),
        "calibration_bins": _calibration_bins(labels, probabilities),
        "age_subgroups": _subgroup_summary(labels, predictions, ages),
        "threshold": 0.5,
        "threshold_note": "Fixed demonstration threshold; not clinically selected or approved.",
        "limitations": [
            "Fictional trajectories and heuristic-derived labels only.",
            "Calibration bins describe agreement with synthetic labels, not real-world risk probabilities.",
            "Age-band metrics are exploratory synthetic diagnostics, not fairness or safety evidence.",
            "This evaluator does not change or promote the serving model.",
        ],
        "demo_only": True,
        "clinically_validated": False,
    }

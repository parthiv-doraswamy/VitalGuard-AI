"""Grouped synthetic evaluation for candidate temporal features.

This evaluator is intentionally separate from the serving model. Synthetic
labels are heuristic-derived; results are engineering diagnostics, not clinical
performance estimates.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .feature_engineering import RAW_FEATURES, TREND_FEATURES, build_temporal_features
from .model import _heuristic_score

EVALUATION_VERSION = "grouped-temporal-eval-0.1.0"
EXTRA_FEATURES = tuple(f"delta_{name}" for name in TREND_FEATURES) + tuple(
    f"rolling_mean_{name}" for name in TREND_FEATURES
)


def _synthetic_episodes(seed: int = 20261011, subject_count: int = 240, steps: int = 6):
    """Create fictional repeated readings; subjects, not individual rows, are split."""
    rng = np.random.default_rng(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    episodes = {}
    for subject_index in range(subject_count):
        subject_id = f"DEMO-SUBJECT-{subject_index:04d}"
        baseline = np.array([
            rng.integers(25, 91), rng.normal(84, 15), rng.normal(96, 2.2),
            rng.normal(122, 17), rng.normal(76, 10), rng.normal(37, 0.5),
            rng.normal(17, 4),
        ], dtype=float)
        drift = np.array([
            0, rng.normal(0, 2.0), rng.normal(0, 0.5), rng.normal(0, 2.0),
            rng.normal(0, 1.0), rng.normal(0, 0.08), rng.normal(0, 0.8),
        ])
        rows = []
        for step in range(steps):
            values = baseline + drift * step + rng.normal(0, [0, 2, 0.5, 2, 1, 0.08, 0.8])
            values[0] = baseline[0]
            values[1] = np.clip(values[1], 35, 190)
            values[2] = np.clip(values[2], 75, 100)
            values[3] = np.clip(values[3], 65, 220)
            values[4] = np.clip(values[4], 35, 130)
            values[5] = np.clip(values[5], 34, 42)
            values[6] = np.clip(values[6], 5, 42)
            row = {name: float(value) for name, value in zip(RAW_FEATURES, values)}
            row["age"] = int(round(row["age"]))
            row["observed_at"] = (start + timedelta(days=subject_index, minutes=step * 15)).isoformat()
            rows.append(row)
        episodes[subject_id] = rows
    return episodes


def evaluate_grouped_temporal_features(seed: int = 20261011) -> dict[str, object]:
    """Compare raw baseline with candidate temporal features on held-out subjects."""
    episodes = _synthetic_episodes(seed=seed)
    subject_ids = sorted(episodes)
    train_subjects, test_subjects = train_test_split(
        subject_ids, test_size=0.25, random_state=42
    )
    train_set, test_set = set(train_subjects), set(test_subjects)
    x_raw_train, x_raw_test, x_eng_train, x_eng_test = [], [], [], []
    y_train, y_test = [], []
    train_rows = 0

    for subject_id, observations in episodes.items():
        history = []
        for observation in observations:
            history.append(observation)
            # Start at the second reading so both candidates have valid temporal context.
            if len(history) < 2:
                continue
            features = build_temporal_features(history)
            raw = [float(features[name]) for name in RAW_FEATURES]
            engineered = raw + [
                float(features["trend_deltas"][name]) for name in TREND_FEATURES
            ] + [
                float(features["rolling_means"][name]) for name in TREND_FEATURES
            ]
            row_array = np.array([[float(observation[name]) for name in RAW_FEATURES]])
            score = float(_heuristic_score(row_array)[0])
            # Deterministic per-subject/time noise prevents random row-level split leakage.
            label_noise = ((int(subject_id[-4:]) * 17 + len(history) * 13 + seed) % 101 - 50) / 10
            label = int(score + label_noise >= 35)
            if subject_id in train_set:
                x_raw_train.append(raw)
                x_eng_train.append(engineered)
                y_train.append(label)
                train_rows += 1
            elif subject_id in test_set:
                x_raw_test.append(raw)
                x_eng_test.append(engineered)
                y_test.append(label)

    if len(set(y_train)) < 2 or len(set(y_test)) < 2:
        raise ValueError("synthetic evaluation split must contain both label classes")

    def fit_score(x_train, x_test):
        pipeline = Pipeline([
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1200, class_weight="balanced", random_state=42)),
        ])
        pipeline.fit(np.asarray(x_train), np.asarray(y_train))
        probabilities = pipeline.predict_proba(np.asarray(x_test))[:, 1]
        predictions = (probabilities >= 0.5).astype(int)
        return {
            "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
            "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, predictions, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
        }

    return {
        "evaluation_version": EVALUATION_VERSION,
        "evaluation_type": "synthetic subject-grouped holdout",
        "seed": seed,
        "subject_count": len(subject_ids),
        "train_subject_count": len(train_set),
        "test_subject_count": len(test_set),
        "train_row_count": train_rows,
        "test_row_count": len(y_test),
        "subject_overlap": sorted(train_set & test_set),
        "baseline_feature_count": len(RAW_FEATURES),
        "candidate_feature_count": len(RAW_FEATURES) + len(EXTRA_FEATURES),
        "baseline_metrics": fit_score(x_raw_train, x_raw_test),
        "candidate_metrics": fit_score(x_eng_train, x_eng_test),
        "feature_names": list(RAW_FEATURES) + list(EXTRA_FEATURES),
        "limitations": [
            "Generated fictional trajectories and heuristic labels only.",
            "Metrics are engineering diagnostics, not clinical performance or safety evidence.",
            "The serving model is unchanged; this evaluator does not promote the candidate feature set.",
        ],
        "demo_only": True,
        "clinically_validated": False,
    }

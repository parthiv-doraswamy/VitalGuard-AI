"""Generated demo training data for the synthetic VitalGuard model.

No patient records are used. Labels come from a transparent hand-written
heuristic plus seeded noise, purely to exercise the software workflow. Moved
unchanged from model.py so the training pipeline (ml/) and the in-process
fallback produce the identical model.
"""
from __future__ import annotations

import numpy as np

SYNTHETIC_SEED = 20261010
SYNTHETIC_SAMPLES = 12000
LABEL_DEFINITION = "synthetic heuristic score plus seeded noise >= 35"


def heuristic_score(rows: np.ndarray) -> np.ndarray:
    age, hr, spo2, sys, dia, temp, rr = rows.T
    score = np.zeros(len(rows), dtype=float)
    score += np.clip(np.abs(hr - 82) - 12, 0, 70) * 0.55
    score += np.clip(96 - spo2, 0, 30) * 4.4
    score += np.clip(105 - sys, 0, 80) * 0.72
    score += np.clip(rr - 18, 0, 35) * 1.5
    score += np.clip(12 - rr, 0, 12) * 1.8
    score += np.clip(np.abs(temp - 37) - 0.5, 0, 5) * 10
    score += np.clip(age - 65, 0, 45) * 0.18
    score += np.clip(55 - dia, 0, 35) * 0.3
    return np.clip(score, 0, 100)


def training_data(seed: int = SYNTHETIC_SEED, samples: int = SYNTHETIC_SAMPLES):
    rng = np.random.default_rng(seed)
    rows = np.column_stack(
        [
            rng.integers(18, 101, samples),
            rng.normal(84, 22, samples).clip(35, 190),
            rng.normal(96, 3.2, samples).clip(75, 100),
            rng.normal(122, 22, samples).clip(65, 220),
            rng.normal(76, 13, samples).clip(35, 130),
            rng.normal(37.0, 1.0, samples).clip(34, 42),
            rng.normal(17, 6, samples).clip(5, 42),
        ]
    )
    heuristic = heuristic_score(rows)
    # A small noise term prevents an unrealistically perfect synthetic boundary.
    labels = ((heuristic + rng.normal(0, 7, samples)) >= 35).astype(int)
    return rows, labels

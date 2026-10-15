"""Benchmark risk models on the PhysioNet/CinC Challenge 2019 sepsis dataset.

Dataset: "Early Prediction of Sepsis from Clinical Data: the PhysioNet/Computing
in Cardiology Challenge 2019" (Reyna et al., Crit Care Med 2020), open access on
PhysioNet (https://physionet.org/content/challenge-2019/1.0.0/), CC BY 4.0.
Hourly ICU records of ~40,000 patients from two hospital systems.

Task (one prediction per patient-hour):
- Feature set "api_vitals": exactly the seven inputs the VitalGuard API accepts,
  in API order: age, heart_rate, spo2, systolic_bp, diastolic_bp, temperature,
  respiratory_rate. Only this set can be served by the current API.
- Feature set "extended": the same seven plus 6-hour trends (change, rolling
  min/max), MAP, hours since ICU admission, sex and hospital-to-ICU delay.
  It shows how much signal temporal context adds; serving it would need an API
  that accepts observation history.
- Vitals are forward-filled within each patient (never backward, and trends look
  back only, so no future values are used); diastolic BP is derived from MAP when
  not charted.
- Label: SepsisLabel, which the challenge already sets to 1 from six hours
  before clinical sepsis onset, so a positive means "sepsis within ~6 hours".
- Split: by patient (SHA-256 of seed:patient id) into 70/15/15
  train/validation/test, so no patient appears in two splits. Decision
  thresholds are chosen on validation only; test is used once for reporting.

Usage:
  python ml/download_physionet2019.py                 # fetch the data (~42 MB)
  python ml/benchmark_physionet.py                    # writes ml/reports/physionet2019_benchmark.json
  python ml/benchmark_physionet.py --save-artifact    # also stores the selected model for the API

This is a research benchmark on retrospective data. It is not clinically
validated and must not be used for patient care.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, roc_auc_score, roc_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "ml" / "data" / "physionet-2019"
DEFAULT_REPORT = ROOT / "ml" / "reports" / "physionet2019_benchmark.json"
FEATURES = ("age", "heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature", "respiratory_rate")
SOURCE_COLUMNS = {"Age": "age", "HR": "heart_rate", "O2Sat": "spo2", "SBP": "systolic_bp", "DBP": "diastolic_bp",
                  "Temp": "temperature", "Resp": "respiratory_rate"}
# Same plausibility ranges as the API's input validation (backend/app/schemas.py).
VALID_RANGES = {"age": (18, 110), "heart_rate": (20, 250), "spo2": (50, 100), "systolic_bp": (50, 280),
                "diastolic_bp": (20, 180), "temperature": (30, 45), "respiratory_rate": (3, 70)}
SPLIT_SEED = 20261015
TREND_HOURS = 6
EXTENDED = FEATURES + (
    "map", "iculos_hours", "sex_male", "hosp_to_icu_hours",
    "heart_rate_change_6h", "spo2_change_6h", "systolic_bp_change_6h", "temperature_change_6h",
    "respiratory_rate_change_6h", "map_change_6h",
    "heart_rate_max_6h", "respiratory_rate_max_6h", "temperature_max_6h", "spo2_min_6h", "systolic_bp_min_6h",
)
FEATURE_SETS = {"api_vitals": FEATURES, "extended": EXTENDED}


# --- Data -------------------------------------------------------------------------------

def load_records(data_dir: Path) -> pd.DataFrame:
    frames = []
    columns = ["HR", "O2Sat", "Temp", "SBP", "MAP", "DBP", "Resp", "Age", "Gender", "HospAdmTime", "ICULOS", "SepsisLabel"]
    for subset in ("training_setA", "training_setB"):
        for path in sorted((data_dir / subset).glob("p*.psv")):
            frame = pd.read_csv(path, sep="|", usecols=columns)
            frame["patient_id"] = path.stem
            frame["hospital"] = "A" if subset.endswith("A") else "B"
            frames.append(frame)
    if not frames:
        raise SystemExit(f"No .psv files under {data_dir}; run ml/download_physionet2019.py first")
    return pd.concat(frames, ignore_index=True)


def prepare(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Forward-fill within patient, derive DBP from MAP, keep complete and plausible rows."""
    data = raw.sort_values(["patient_id", "ICULOS"]).copy()
    vitals = ["HR", "O2Sat", "Temp", "SBP", "MAP", "DBP", "Resp"]
    data[vitals] = data.groupby("patient_id", sort=False)[vitals].ffill()
    derived = (3 * data["MAP"] - data["SBP"]) / 2
    use_map = data["DBP"].isna() & derived.notna()
    data.loc[use_map, "DBP"] = derived[use_map]
    data = data.rename(columns=SOURCE_COLUMNS)
    # Look-back-only temporal context for the "extended" feature set.
    by_patient = data.groupby("patient_id", sort=False)
    data["map"] = data["MAP"]
    data["iculos_hours"] = data["ICULOS"]
    data["sex_male"] = data["Gender"].fillna(0.5)
    data["hosp_to_icu_hours"] = (-data["HospAdmTime"]).fillna(0).clip(lower=0)
    for name in ("heart_rate", "spo2", "systolic_bp", "temperature", "respiratory_rate", "map"):
        data[f"{name}_change_6h"] = (data[name] - by_patient[name].shift(TREND_HOURS)).fillna(0)
    for name, how in (("heart_rate", "max"), ("respiratory_rate", "max"), ("temperature", "max"),
                      ("spo2", "min"), ("systolic_bp", "min")):
        rolled = by_patient[name].rolling(TREND_HOURS, min_periods=1).agg(how).reset_index(level=0, drop=True)
        data[f"{name}_{how}_6h"] = rolled.fillna(data[name])
    data["map"] = data["map"].fillna((data["systolic_bp"] + 2 * data["diastolic_bp"]) / 3)
    rows_total = len(data)
    missing_rate = {name: round(float(data[name].isna().mean()), 4) for name in FEATURES}
    data = data.dropna(subset=list(FEATURES))
    for name, (low, high) in VALID_RANGES.items():
        data = data[(data[name] >= low) & (data[name] <= high)]
    data = data[data["diastolic_bp"] < data["systolic_bp"]]
    stats = {
        "patients_total": int(raw["patient_id"].nunique()),
        "rows_total": rows_total,
        "missing_rate_after_forward_fill": missing_rate,
        "dbp_derived_from_map_rows": int(use_map.sum()),
        "patients_used": int(data["patient_id"].nunique()),
        "rows_used": int(len(data)),
        "positive_rows": int(data["SepsisLabel"].sum()),
        "positive_rate": round(float(data["SepsisLabel"].mean()), 4),
        "patients_with_sepsis": int(data.groupby("patient_id")["SepsisLabel"].max().sum()),
    }
    return data, stats


def assign_split(patient_ids: pd.Series, seed: int = SPLIT_SEED) -> pd.Series:
    def bucket(pid: str) -> str:
        value = int(hashlib.sha256(f"{seed}:{pid}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        return "train" if value < 0.70 else "validation" if value < 0.85 else "test"
    mapping = {pid: bucket(pid) for pid in patient_ids.unique()}
    return patient_ids.map(mapping)


# --- Models -----------------------------------------------------------------------------

def news2_points(x: np.ndarray) -> np.ndarray:
    """NEWS2 aggregate from the observed vitals (SpO2 scale 1, room air, alert): a clinical rule baseline."""
    _age, hr, spo2, sbp, _dbp, temp, rr = x.T

    def band(values, edges_points, otherwise):
        out = np.full(values.shape, otherwise, dtype=float)
        assigned = np.zeros(values.shape, dtype=bool)
        for upper, points in edges_points:
            hit = (values <= upper) & ~assigned
            out[hit] = points
            assigned |= hit
        return out

    return (band(rr, [(8, 3), (11, 1), (20, 0), (24, 2)], 3) + band(spo2, [(91, 3), (93, 2), (95, 1)], 0)
            + band(sbp, [(90, 3), (100, 2), (110, 1), (219, 0)], 3)
            + band(hr, [(40, 3), (50, 1), (90, 0), (110, 1), (130, 2)], 3)
            + band(temp, [(35, 3), (36, 1), (38, 0), (39, 1)], 2))


def candidates(positive_weight: float) -> dict[str, tuple[str, object]]:
    from xgboost import XGBClassifier
    return {
        "logistic_regression": ("Logistic Regression", Pipeline([
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42))])),
        "random_forest": ("Random Forest", Pipeline([
            ("classifier", RandomForestClassifier(n_estimators=200, max_depth=14, min_samples_leaf=40,
                                                  class_weight="balanced_subsample", n_jobs=-1, random_state=42))])),
        "hist_gradient_boosting": ("HistGradientBoosting", Pipeline([
            ("classifier", HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31,
                                                          min_samples_leaf=200, l2_regularization=1.0,
                                                          class_weight="balanced",
                                                          random_state=42))])),
        "xgboost": ("XGBoost", Pipeline([
            ("classifier", XGBClassifier(n_estimators=600, max_depth=4, learning_rate=0.04, subsample=0.8,
                                         colsample_bytree=0.8, min_child_weight=50, reg_lambda=5.0,
                                         scale_pos_weight=positive_weight, tree_method="hist",
                                         eval_metric="aucpr", n_jobs=-1, random_state=42))])),
    }


# --- Metrics ----------------------------------------------------------------------------

def youden_threshold(y: np.ndarray, scores: np.ndarray) -> float:
    fpr, tpr, thresholds = roc_curve(y, scores)
    best = int(np.argmax(tpr - fpr))
    return float(min(thresholds[best], 1.0))


def metrics_at(y: np.ndarray, scores: np.ndarray, threshold: float, probabilities: bool = True) -> dict:
    predicted = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    sensitivity = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * precision * sensitivity / (precision + sensitivity) if precision + sensitivity else 0.0
    out = {
        "threshold": round(float(threshold), 4),
        "accuracy": round(float((tp + tn) / len(y)), 4),
        "balanced_accuracy": round(float((sensitivity + specificity) / 2), 4),
        "sensitivity": round(float(sensitivity), 4),
        "specificity": round(float(specificity), 4),
        "precision": round(float(precision), 4),
        "f1": round(float(f1), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }
    if len(np.unique(scores)) > 1:
        out["auroc"] = round(float(roc_auc_score(y, scores)), 4)
        out["auprc"] = round(float(average_precision_score(y, scores)), 4)
    else:
        out["auroc"], out["auprc"] = 0.5, round(float(y.mean()), 4)
    if probabilities:
        out["brier"] = round(float(brier_score_loss(y, np.clip(scores, 0, 1))), 4)
    return out


def bootstrap_auroc(y: np.ndarray, scores: np.ndarray, groups: np.ndarray, samples: int = 100, seed: int = 7) -> list[float]:
    """Patient-level bootstrap 95% CI: resample patients, not rows (rows of one patient are correlated)."""
    rng = np.random.default_rng(seed)
    unique, inverse = np.unique(groups, return_inverse=True)
    rows_by_patient = np.split(np.argsort(inverse, kind="stable"), np.cumsum(np.bincount(inverse))[:-1])
    values = []
    for _ in range(samples):
        picked = rng.integers(0, len(unique), len(unique))
        index = np.concatenate([rows_by_patient[i] for i in picked])
        if y[index].min() != y[index].max():
            values.append(roc_auc_score(y[index], scores[index]))
    return [round(float(np.percentile(values, 2.5)), 4), round(float(np.percentile(values, 97.5)), 4)]


def roc_points(y: np.ndarray, scores: np.ndarray, points: int = 40) -> list[list[float]]:
    fpr, tpr, _ = roc_curve(y, scores)
    grid = np.linspace(0, 1, points)
    return [[round(float(x), 4), round(float(np.interp(x, fpr, tpr)), 4)] for x in grid]


def single_row_latency_ms(model, row: np.ndarray, calls: int = 200) -> float:
    for _ in range(20):
        model.predict_proba(row)
    timings = []
    for _ in range(calls):
        start = time.perf_counter()
        model.predict_proba(row)
        timings.append((time.perf_counter() - start) * 1000)
    return round(float(np.percentile(timings, 95)), 3)


def importance(model, names: tuple[str, ...]) -> dict[str, float] | None:
    classifier = model.named_steps["classifier"]
    values = getattr(classifier, "feature_importances_", None)
    if values is None and hasattr(classifier, "coef_"):
        values = np.abs(classifier.coef_[0])
    if values is None:
        return None
    total = float(np.sum(values)) or 1.0
    return {name: round(float(value) / total, 4) for name, value in zip(names, values)}


def evaluation_file(version: str, result: dict, report: dict) -> dict:
    """GET /api/v1/model/evaluation payload for the served artifact: held-out test patients only."""
    test, cm = result["test"], result["test"]["confusion_matrix"]
    split = report["dataset"]["split_counts"]["test"]
    return {
        "model_version": version,
        "evaluation_type": "held-out test patients (patient-level split), PhysioNet/CinC Challenge 2019",
        "sample_count": split["rows"],
        "patient_count": split["patients"],
        "positive_label_definition": report["dataset"]["label"],
        "threshold": test["threshold"],
        "metrics": {"accuracy": test["accuracy"], "balanced_accuracy": test["balanced_accuracy"],
                    "precision": test["precision"], "recall": test["sensitivity"], "specificity": test["specificity"],
                    "f1": test["f1"], "roc_auc": test["auroc"], "pr_auc_average_precision": test["auprc"]},
        "roc_auc_95ci": result.get("test_auroc_95ci"),
        "confusion_matrix": {"labels": ["no_sepsis_within_6h", "sepsis_within_6h"],
                             "rows_actual_columns_predicted": [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]]},
        "limitations": report["limitations"] + [
            "The risk score is a class-weighted probability, not a calibrated absolute risk.",
            "Only about 2% of patient-hours are positive: precision is low and accuracy alone is misleading."],
        "demo_only": True,
        "clinically_validated": False,
    }


# --- Main -------------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-train-rows", type=int, default=400_000,
                        help="Cap on training rows: all positives are kept, negatives are sampled.")
    parser.add_argument("--save-artifact", action="store_true",
                        help="Store the selected model under backend/app/model_artifacts for the API.")
    args = parser.parse_args()
    started = time.time()

    print("Loading PhysioNet 2019 records…", flush=True)
    data, stats = prepare(load_records(args.data_dir))
    data["split"] = assign_split(data["patient_id"])
    y_all = data["SepsisLabel"].to_numpy(dtype=int)
    split = data["split"].to_numpy()
    groups = data["patient_id"].to_numpy()
    stats["split_counts"] = {name: {"patients": int(data.loc[data.split == name, "patient_id"].nunique()),
                             "rows": int((split == name).sum()), "positive_rows": int(y_all[split == name].sum())}
                      for name in ("train", "validation", "test")}

    rng = np.random.default_rng(42)
    train_index = np.flatnonzero(split == "train")
    positives = train_index[y_all[train_index] == 1]
    negatives = train_index[y_all[train_index] == 0]
    keep = min(len(negatives), max(0, args.max_train_rows - len(positives)))
    train_index = np.sort(np.concatenate([positives, rng.choice(negatives, keep, replace=False)]))
    stats["training_rows_after_negative_sampling"] = int(len(train_index))
    val, test = split == "validation", split == "test"
    y_train = y_all[train_index]
    positive_weight = float((y_train == 0).sum() / max(1, (y_train == 1).sum()))
    print(f"{stats['rows_used']} usable rows from {stats['patients_used']} patients; "
          f"{len(train_index)} training rows, positive rate {stats['positive_rate']:.2%}", flush=True)

    results: dict[str, dict] = {}
    fitted: dict[str, object] = {}
    for set_name, names in FEATURE_SETS.items():
        x_all = data[list(names)].to_numpy(dtype=float)
        x_train = x_all[train_index]
        results[set_name] = {}
        for key, (label, model) in candidates(positive_weight).items():
            print(f"[{set_name}] training {label}…", flush=True)
            t0 = time.time()
            model.fit(x_train, y_train)
            train_seconds = time.time() - t0
            val_scores = model.predict_proba(x_all[val])[:, 1]
            threshold = youden_threshold(y_all[val], val_scores)
            test_scores = model.predict_proba(x_all[test])[:, 1]
            test_metrics = metrics_at(y_all[test], test_scores, threshold)
            results[set_name][key] = {
                "label": label, "kind": "trained",
                "validation": metrics_at(y_all[val], val_scores, threshold),
                "test": test_metrics,
                "test_auroc_95ci": bootstrap_auroc(y_all[test], test_scores, groups[test]),
                "test_at_0_5": {k: v for k, v in metrics_at(y_all[test], test_scores, 0.5).items()
                                if k in ("accuracy", "balanced_accuracy", "sensitivity", "specificity")},
                "roc_curve": roc_points(y_all[test], test_scores),
                "train_seconds": round(train_seconds, 1),
                "p95_single_row_latency_ms": single_row_latency_ms(model, x_all[test][:1]),
                "feature_importance": importance(model, names),
            }
            if set_name == "api_vitals":
                fitted[key] = model
            print(f"  test AUROC {test_metrics['auroc']}  AUPRC {test_metrics['auprc']}  "
                  f"accuracy {test_metrics['accuracy']}  balanced {test_metrics['balanced_accuracy']}", flush=True)

    # Untrained reference points (computed from the seven vitals).
    x_vitals = data[list(FEATURES)].to_numpy(dtype=float)
    val_news2, test_news2 = news2_points(x_vitals[val]), news2_points(x_vitals[test])
    news2_threshold = youden_threshold(y_all[val], val_news2)
    baselines = {
        "news2_rule": {"label": "NEWS2 rule (no training)", "kind": "baseline",
                       "validation": metrics_at(y_all[val], val_news2, news2_threshold, probabilities=False),
                       "test": metrics_at(y_all[test], test_news2, news2_threshold, probabilities=False),
                       "test_auroc_95ci": bootstrap_auroc(y_all[test], test_news2, groups[test]),
                       "roc_curve": roc_points(y_all[test], test_news2)},
        "majority_class": {"label": "Always 'no sepsis'", "kind": "baseline",
                           "test": metrics_at(y_all[test], np.zeros(test.sum()), 0.5, probabilities=False)},
    }

    # Selection uses validation AUPRC only (the primary metric for a rare outcome), never test results.
    best = {set_name: max(models, key=lambda key: models[key]["validation"]["auprc"])
            for set_name, models in results.items()}
    selected = best["api_vitals"]
    trained = list(results["api_vitals"])

    # How each deployable model would score the fictional demo cohort used by the live stream.
    sys.path.insert(0, str(ROOT / "backend"))
    from app.cohort import cohort_vitals, patients  # noqa: E402
    cohort_check = {}
    for key in trained:
        by_scenario: dict[str, list[float]] = {}
        for patient in patients():
            row = np.array([[cohort_vitals(patient, 45)[name] for name in FEATURES]], dtype=float)
            by_scenario.setdefault(patient["scenario"], []).append(float(fitted[key].predict_proba(row)[0, 1]))
        cohort_check[key] = {scenario: {"min": round(min(v) * 100), "max": round(max(v) * 100)}
                             for scenario, v in sorted(by_scenario.items())}

    report = {
        "format": "vitalguard-benchmark-report", "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "name": "PhysioNet/Computing in Cardiology Challenge 2019 — Early Prediction of Sepsis from Clinical Data",
            "url": "https://physionet.org/content/challenge-2019/1.0.0/",
            "license": "Creative Commons Attribution 4.0 International",
            "citation": "Reyna MA, Josef CS, Jeter R, et al. Early Prediction of Sepsis From Clinical Data: "
                        "the PhysioNet/Computing in Cardiology Challenge 2019. Crit Care Med. 2020;48(2):210-217.",
            "kind": "public-research",
            "unit_of_prediction": "one ICU patient-hour",
            "label": "SepsisLabel: 1 from 6 hours before clinical sepsis onset (Sepsis-3), else 0",
            "feature_sets": {name: list(names) for name, names in FEATURE_SETS.items()},
            "preprocessing": ["forward-fill vitals within each patient (past values only)",
                              "diastolic BP derived from MAP as (3·MAP − SBP)/2 when not charted",
                              "rows with any missing feature dropped (complete case)",
                              "values outside the API's input ranges dropped; age ≥ 18"],
            "split": "by patient: SHA-256(seed:patient id) → 70% train / 15% validation / 15% test",
            **stats,
        },
        "protocol": {
            "threshold": "per model, maximises Youden's J (sensitivity + specificity − 1) on validation",
            "selection": "per feature set, highest validation AUPRC; test results are reported only after selection",
            "deployable_feature_set": "api_vitals (the current API accepts one observation of seven vitals)",
            "training_sampling": f"all positive training rows plus a random sample of negatives (≤ {args.max_train_rows} rows)",
            "why_not_accuracy_alone": "Only about 2% of patient-hours are positive, so predicting 'no sepsis' for "
                                      "everyone is ~98% accurate and useless. Balanced accuracy, sensitivity, "
                                      "specificity, AUROC and AUPRC are reported alongside accuracy.",
        },
        "results": results,
        "baselines": baselines,
        "best_by_feature_set": best,
        "selected_model": selected,
        "demo_cohort_scores_at_step_45": cohort_check,
        "limitations": [
            "Seven bedside vitals from a single hour carry limited sepsis signal; the extended set adds trends "
            "but still no labs or treatments, so both are below challenge entries that used all 40 variables.",
            "Retrospective data from two US hospital systems; not externally or prospectively validated.",
            "Patient-hours are correlated; confidence intervals use a patient-level bootstrap.",
            "Not clinically validated. Not for diagnosis, triage or treatment decisions.",
        ],
        "runtime_seconds": round(time.time() - started),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=1) + "\n")
    print(f"Selected {results['api_vitals'][selected]['label']} (api_vitals); report written to {args.report}", flush=True)

    if args.save_artifact:
        from app.model_artifact import save_artifact  # noqa: E402
        version = f"physionet2019-{selected.replace('_', '-')}-1.0.0"
        directory = ROOT / "backend" / "app" / "model_artifacts" / version
        manifest = save_artifact(fitted[selected], directory, FEATURES, {
            "model_version": version, "clinically_validated": False,
            "intended_use": "research demonstration on public retrospective data — not a clinical model",
            "dataset": {"kind": "public-research", "id": "physionet-challenge-2019-v1.0.0",
                        "description": "PhysioNet/CinC Challenge 2019 sepsis data (7 vitals, hourly)",
                        "label_definition": report["dataset"]["label"], "source": report["dataset"]["url"],
                        "synthetic_fixture": False},
            "training": {"algorithm": results["api_vitals"][selected]["label"], "run_id": report["created_at"],
                         "rows": int(len(train_index))},
            "decision_threshold": {"value": results["api_vitals"][selected]["test"]["threshold"], "policy": "validation Youden J"},
            "selection": {"selected": results["api_vitals"][selected]["label"],
                          "compared": [results["api_vitals"][key]["label"] for key in trained],
                          "rule": report["protocol"]["selection"]},
            "metrics": {"test": results["api_vitals"][selected]["test"]},
        })
        (directory / "evaluation.json").write_text(json.dumps(
            evaluation_file(version, results["api_vitals"][selected], report), indent=2) + "\n")
        print(f"Artifact {manifest['model_version']} saved to {directory}", flush=True)


if __name__ == "__main__":
    main()

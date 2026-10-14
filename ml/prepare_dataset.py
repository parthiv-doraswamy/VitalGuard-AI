"""Build a versioned, validated prediction dataset from MIMIC-IV-format tables.

    python ml/prepare_dataset.py --experiment mimic_format_fixture --generate-fixture
    python ml/prepare_dataset.py --experiment mimic_iv --confirm-approved-access   # needs $MIMIC_IV_DIR

One output row = one prediction time for one ICU stay. Features are the most
recent valid value that was *stored* (max(charttime, storetime)) at or before
the prediction time, within each feature's lookback window, so no information
from after the prediction time can enter a row. The label looks only forward
(definition in ml/config.yaml and ml/data/README.md).

Outputs (ml/runs/<experiment>/dataset/, git-ignored):
  dataset.csv            rows with patient_id, split and features in API order
  dataset_manifest.json  provenance, dataset version (content hash), config hash, counts
  data_quality.json      units, invalid values, missingness and exclusions
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from common import (RUNS_DIR, PipelineError, config_sha256, git_commit, load_config, resolve_data_dir,
                    sha256_file, sha256_ids, write_json)
from fixtures import MARKER_FILE, generate_fixture

# MIMIC-IV chartevents itemids (d_items) mapped to the API feature schema.
ITEM_MAP = {
    220045: "heart_rate",          # Heart Rate (bpm)
    220277: "spo2",                # O2 saturation pulseoxymetry (%)
    220179: "systolic_bp",         # Non Invasive Blood Pressure systolic (mmHg)
    220050: "systolic_bp",         # Arterial Blood Pressure systolic (mmHg)
    220180: "diastolic_bp",        # Non Invasive Blood Pressure diastolic (mmHg)
    220051: "diastolic_bp",        # Arterial Blood Pressure diastolic (mmHg)
    220210: "respiratory_rate",    # Respiratory Rate (insp/min)
    223762: "temperature",         # Temperature Celsius
    223761: "temperature_f",       # Temperature Fahrenheit (converted to Celsius)
}
TABLES = {
    "patients": ("hosp/patients", ["subject_id", "anchor_age", "anchor_year"]),
    "admissions": ("hosp/admissions", ["subject_id", "hadm_id", "admittime", "deathtime"]),
    "icustays": ("icu/icustays", ["subject_id", "hadm_id", "stay_id", "intime", "outtime"]),
    "chartevents": ("icu/chartevents", ["stay_id", "charttime", "itemid", "valuenum"]),
}
OPTIONAL_COLUMNS = {"patients": ["anchor_year_group"], "chartevents": ["storetime"]}
CHUNK_ROWS = 2_000_000


def _table_path(data_dir: Path, relative: str) -> Path:
    for suffix in (".csv.gz", ".csv"):
        candidate = data_dir / f"{relative}{suffix}"
        if candidate.is_file():
            return candidate
    raise PipelineError(f"Missing table {relative}.csv(.gz) under the dataset directory")


def load_tables(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Read only the needed columns; validate the schema; filter chartevents to mapped items."""
    tables: dict[str, pd.DataFrame] = {}
    for name, (relative, required) in TABLES.items():
        path = _table_path(data_dir, relative)
        header = pd.read_csv(path, nrows=0).columns
        missing = [column for column in required if column not in header]
        if missing:
            raise PipelineError(f"Table {relative} is missing required columns: {missing}")
        columns = required + [column for column in OPTIONAL_COLUMNS.get(name, []) if column in header]
        if name == "chartevents":
            chunks = [chunk[chunk["itemid"].isin(ITEM_MAP)]
                      for chunk in pd.read_csv(path, usecols=columns, chunksize=CHUNK_ROWS)]
            tables[name] = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns)
        else:
            tables[name] = pd.read_csv(path, usecols=columns)
    return tables


def _parse_times(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


def extract_events(chartevents: pd.DataFrame, config: dict[str, Any], quality: dict[str, Any]) -> pd.DataFrame:
    """Map items to features, convert units and drop invalid values (counted in `quality`)."""
    events = chartevents.copy()
    before = len(events)
    events = events.drop_duplicates()
    quality["duplicate_events_removed"] = int(before - len(events))
    events["feature"] = events["itemid"].map(ITEM_MAP)
    events["value"] = pd.to_numeric(events["valuenum"], errors="coerce")
    events = _parse_times(events, ["charttime", "storetime"])
    unusable = events["value"].isna() | events["charttime"].isna() | events["stay_id"].isna()
    quality["non_numeric_or_untimed_events_removed"] = int(unusable.sum())
    events = events[~unusable].copy()

    fahrenheit = events["feature"] == "temperature_f"
    # A small share of Fahrenheit-item values are charted in Celsius; keep them as Celsius.
    already_celsius = fahrenheit & (events["value"] < 50)
    quality["fahrenheit_item_values_already_celsius"] = int(already_celsius.sum())
    converted = fahrenheit & ~already_celsius
    events.loc[converted, "value"] = (events.loc[converted, "value"] - 32) * 5 / 9
    quality["fahrenheit_values_converted"] = int(converted.sum())
    events.loc[fahrenheit, "feature"] = "temperature"

    ranges = {item["name"]: item["valid_range"] for item in config["features"]}
    invalid_counts: dict[str, int] = {}
    keep = pd.Series(True, index=events.index)
    for feature, (low, high) in ranges.items():
        mask = (events["feature"] == feature) & ~events["value"].between(low, high)
        invalid_counts[feature] = int(mask.sum())
        keep &= ~mask
    quality["out_of_range_values_removed"] = invalid_counts
    events = events[keep].copy()
    # A value is usable only once it has been stored, not merely charted.
    stored = events["storetime"] if "storetime" in events else events["charttime"]
    events["available_at"] = np.maximum(events["charttime"], stored.fillna(events["charttime"]))
    events["stay_id"] = events["stay_id"].astype("int64")
    quality["valid_events_by_feature"] = {key: int(value) for key, value in events["feature"].value_counts().sort_index().items()}
    return events[["stay_id", "feature", "charttime", "available_at", "value"]]


def prediction_times(tables: dict[str, pd.DataFrame], config: dict[str, Any], quality: dict[str, Any]) -> pd.DataFrame:
    """Expand each eligible ICU stay into prediction times (inclusion criteria applied here)."""
    stays = _parse_times(tables["icustays"].copy(), ["intime", "outtime"])
    admissions = _parse_times(tables["admissions"].copy(), ["admittime", "deathtime"])
    stays = stays.merge(admissions[["hadm_id", "admittime", "deathtime"]], on="hadm_id", how="left")
    stays = stays.merge(tables["patients"], on="subject_id", how="left")
    quality["icu_stays"] = int(len(stays))
    stays = stays.dropna(subset=["intime", "outtime", "admittime", "anchor_age", "anchor_year"])
    stays["age"] = stays["anchor_age"] + (stays["admittime"].dt.year - stays["anchor_year"])
    eligible = stays["age"] >= config["inclusion"]["min_age"]
    quality["stays_excluded_under_min_age"] = int((~eligible).sum())
    stays = stays[eligible].copy()

    settings = config["prediction_times"]
    first = pd.Timedelta(hours=settings["first_prediction_hours"])
    stride = pd.Timedelta(hours=settings["stride_hours"])
    span = (stays["outtime"] - stays["intime"] - first)
    counts = (span // stride).clip(lower=-1).astype("int64") + 1
    counts = counts.clip(upper=settings["max_per_stay"]).clip(lower=0)
    rows = stays.loc[stays.index.repeat(counts)].copy()
    rows["step"] = rows.groupby(level=0).cumcount()
    rows["prediction_time"] = rows["intime"] + first + rows["step"] * stride
    rows = rows[rows["prediction_time"] < rows["outtime"]]
    after_death = rows["deathtime"].notna() & (rows["prediction_time"] >= rows["deathtime"])
    quality["prediction_times_at_or_after_death_removed"] = int(after_death.sum())
    rows = rows[~after_death]
    rows["patient_id"] = rows["subject_id"].astype("int64").astype(str)
    rows["split_group"] = rows["anchor_year_group"] if "anchor_year_group" in rows else ""
    rows["stay_id"] = rows["stay_id"].astype("int64")
    return rows[["patient_id", "stay_id", "prediction_time", "deathtime", "age", "split_group"]].reset_index(drop=True)


def attach_features(times: pd.DataFrame, events: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """As-of join: latest value with available_at <= prediction_time and charttime within the lookback."""
    result = times.sort_values("prediction_time").reset_index(drop=True)
    for item in config["features"]:
        name, lookback = item["name"], item.get("lookback_hours")
        if lookback is None:
            continue
        feature_events = events[events["feature"] == name].sort_values("available_at")
        joined = pd.merge_asof(
            result[["prediction_time", "stay_id"]].reset_index(), feature_events[["stay_id", "available_at", "charttime", "value"]],
            left_on="prediction_time", right_on="available_at", by="stay_id", direction="backward", allow_exact_matches=True,
        ).set_index("index").sort_index()
        stale = joined["charttime"] < joined["prediction_time"] - pd.Timedelta(hours=lookback)
        result[name] = joined["value"].where(~stale)
    return result


def label_rows(rows: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    window = pd.Timedelta(hours=config["target"]["outcome_window_hours"])
    death = rows["deathtime"]
    return (death.notna() & (death > rows["prediction_time"]) & (death <= rows["prediction_time"] + window)).astype(int)


def _hash_fraction(seed: int, patient_id: str) -> float:
    digest = hashlib.sha256(f"{seed}:{patient_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2 ** 64


def assign_splits(rows: pd.DataFrame, split: dict[str, Any]) -> pd.Series:
    """Patient-level split: every row of a patient lands in the same partition."""
    fractions = split["fractions"]
    patients = rows[["patient_id", "split_group"]].drop_duplicates("patient_id")
    test_groups = set(split.get("test_groups") or [])
    assignment = {}
    for patient_id, group in zip(patients["patient_id"], patients["split_group"]):
        fraction = _hash_fraction(split["seed"], patient_id)
        if split["strategy"] == "patient_group":
            if group in test_groups:
                assignment[patient_id] = "test"
                continue
            train_share = fractions["train"] / (fractions["train"] + fractions["validation"])
            assignment[patient_id] = "train" if fraction < train_share else "validation"
        elif split["strategy"] == "patient_hash":
            assignment[patient_id] = ("train" if fraction < fractions["train"]
                                      else "validation" if fraction < fractions["train"] + fractions["validation"] else "test")
        else:
            raise PipelineError(f"Unknown split strategy {split['strategy']}")
    return rows["patient_id"].map(assignment)


def build_dataset(tables: dict[str, pd.DataFrame], config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    quality: dict[str, Any] = {}
    events = extract_events(tables["chartevents"], config, quality)
    rows = prediction_times(tables, config, quality)
    rows = attach_features(rows, events, config)
    rows["label"] = label_rows(rows, config)

    names = [item["name"] for item in config["features"]]
    age_low, age_high = next(item["valid_range"] for item in config["features"] if item["name"] == "age")
    rows.loc[~rows["age"].between(age_low, age_high), "age"] = np.nan
    inconsistent_bp = rows["diastolic_bp"] >= rows["systolic_bp"]
    quality["rows_with_diastolic_not_below_systolic"] = int(inconsistent_bp.sum())
    rows.loc[inconsistent_bp, ["systolic_bp", "diastolic_bp"]] = np.nan

    quality["prediction_times_before_exclusion"] = int(len(rows))
    quality["missing_rate_by_feature"] = {name: round(float(rows[name].isna().mean()), 4) for name in names}
    quality["label_prevalence_before_exclusion"] = round(float(rows["label"].mean()), 4) if len(rows) else None
    complete = rows[names].notna().all(axis=1)
    quality["rows_excluded_incomplete_features"] = int((~complete).sum())
    quality["label_prevalence_in_excluded_rows"] = round(float(rows.loc[~complete, "label"].mean()), 4) if (~complete).any() else None
    if config["inclusion"]["require_all_features"]:
        rows = rows[complete].copy()
    if rows.empty:
        raise PipelineError("No rows remain after validation and inclusion criteria")

    rows["split"] = assign_splits(rows, config["split"])
    rows[names] = rows[names].astype(float).round(4)
    rows["prediction_time"] = rows["prediction_time"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    rows = rows.sort_values(["patient_id", "stay_id", "prediction_time"]).reset_index(drop=True)
    columns = ["patient_id", "stay_id", "prediction_time", "split_group", "split", *names, "label"]
    return rows[columns], quality


def split_summary(rows: pd.DataFrame) -> dict[str, Any]:
    summary = {}
    for split, part in rows.groupby("split"):
        summary[split] = {"rows": int(len(part)), "patients": int(part["patient_id"].nunique()),
                          "positives": int(part["label"].sum()), "prevalence": round(float(part["label"].mean()), 4),
                          "patient_ids_sha256": sha256_ids(part["patient_id"].unique())}
    return summary


def check_access(config: dict[str, Any], data_dir: Path, confirmed: bool) -> None:
    has_marker = (data_dir / MARKER_FILE).is_file()
    kind = config["dataset_kind"]
    if kind == "synthetic-fixture" and not has_marker:
        raise PipelineError("Refusing: a synthetic-fixture experiment must point at a generated fixture directory")
    if kind != "synthetic-fixture" and has_marker:
        raise PipelineError(f"Refusing: {data_dir.name} is a synthetic fixture and cannot be labelled '{kind}'")
    if config.get("requires_access_confirmation") and not confirmed:
        raise PipelineError(
            "BLOCKED: this experiment uses a credentialed dataset. Re-run with --confirm-approved-access only if you "
            "hold approved access under the data use agreement and the intended use is permitted.")


def prepare(experiment: str, *, generate: bool = False, confirmed: bool = False, out_dir: Path | None = None,
            config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config(experiment)
    if config["source"] != "mimic-iv-format":
        raise PipelineError(f"Experiment '{experiment}' has no dataset preparation step; run ml/train.py directly")
    data_dir = resolve_data_dir(config)
    if generate:
        if config["dataset_kind"] != "synthetic-fixture":
            raise PipelineError("--generate-fixture is only allowed for synthetic-fixture experiments")
        generate_fixture(data_dir, **{"patients": 400, "seed": 11, **config.get("fixture", {})})
    if not data_dir.is_dir():
        raise PipelineError(f"BLOCKED: dataset directory not found ({data_dir.name}).")
    check_access(config, data_dir, confirmed)

    rows, quality = build_dataset(load_tables(data_dir), config)
    out_dir = Path(out_dir or RUNS_DIR / experiment / "dataset")
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = out_dir / "dataset.csv"
    rows.to_csv(dataset_path, index=False)
    dataset_sha = sha256_file(dataset_path)
    manifest = {
        "dataset_version": f"{experiment}-{dataset_sha[:12]}",
        "dataset_sha256": dataset_sha,
        "kind": config["dataset_kind"],
        "source": config["source"],
        "source_directory_name": data_dir.name,
        "synthetic_fixture": config["dataset_kind"] == "synthetic-fixture",
        "approved_access_confirmed_by_operator": bool(confirmed) if config.get("requires_access_confirmation") else None,
        "config_version": config["config_version"],
        "config_sha256": config_sha256(config),
        "target": config["target"],
        "features": config["features"],
        "prediction_times": config["prediction_times"],
        "inclusion": config["inclusion"],
        "split": config["split"],
        "splits": split_summary(rows),
        "rows": int(len(rows)),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
    }
    write_json(out_dir / "dataset_manifest.json", manifest)
    write_json(out_dir / "data_quality.json", quality)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--generate-fixture", action="store_true", help="(re)generate the fictional MIMIC-format fixture first")
    parser.add_argument("--confirm-approved-access", action="store_true",
                        help="assert you hold approved access to the credentialed dataset")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = prepare(args.experiment, generate=args.generate_fixture, confirmed=args.confirm_approved_access, out_dir=args.out)
    except PipelineError as exc:
        print(str(exc))
        return 2
    print(f"dataset {manifest['dataset_version']} ({manifest['kind']}): {manifest['rows']} rows")
    for split, summary in manifest["splits"].items():
        print(f"  {split:<10} rows={summary['rows']:<6} patients={summary['patients']:<5} prevalence={summary['prevalence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

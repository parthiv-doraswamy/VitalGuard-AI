"""Feature availability, unit/validity handling, labels, missingness and access gates."""
import json

import pandas as pd
import pytest

from common import PipelineError, load_config
from fixtures import MARKER_FILE
from prepare_dataset import build_dataset, check_access, load_tables, prepare
from app.model import FEATURES

T0 = pd.Timestamp("2150-01-01 08:00:00")
FIRST_PREDICTION = "2150-01-01T12:00:00"  # T0 + first_prediction_hours (4)


def tables(events, deathtime=None, stay_hours=30, anchor_age=60):
    """One patient, one admission, one ICU stay starting at T0."""
    return {
        "patients": pd.DataFrame({"subject_id": [1], "anchor_age": [anchor_age], "anchor_year": [2150],
                                  "anchor_year_group": ["2008 - 2010"]}),
        "admissions": pd.DataFrame({"subject_id": [1], "hadm_id": [2], "admittime": [str(T0 - pd.Timedelta(hours=2))],
                                    "deathtime": [str(deathtime) if deathtime is not None else None]}),
        "icustays": pd.DataFrame({"subject_id": [1], "hadm_id": [2], "stay_id": [3], "intime": [str(T0)],
                                  "outtime": [str(T0 + pd.Timedelta(hours=stay_hours))]}),
        "chartevents": pd.DataFrame(events, columns=["stay_id", "charttime", "storetime", "itemid", "valuenum"]),
    }


def vitals_at(hours, overrides=None, skip=()):
    """A full set of valid vitals charted `hours` after T0 and stored one minute later."""
    values = {220045: 80, 220277: 97, 220179: 120, 220180: 75, 220210: 16, 223762: 37.0, **(overrides or {})}
    charted = T0 + pd.Timedelta(hours=hours)
    stored = charted + pd.Timedelta(minutes=1)
    return [[3, str(charted), str(stored), item, value] for item, value in values.items() if item not in skip]


def event(hours, item, value, stored_hours=None):
    charted = T0 + pd.Timedelta(hours=hours)
    stored = T0 + pd.Timedelta(hours=stored_hours) if stored_hours is not None else charted
    return [3, str(charted), str(stored), item, value]


def build(events, **kwargs):
    return build_dataset(tables(events, **kwargs), load_config("mimic_format_fixture"))


def test_only_values_stored_by_the_prediction_time_are_used():
    events = vitals_at(3) + [
        event(3.5, 220045, 150, stored_hours=4.5),  # charted before, stored after the prediction time
        event(4.5, 220045, 170),                    # charted after the prediction time
    ]
    rows, _ = build(events, stay_hours=6)
    assert rows.iloc[0]["prediction_time"] == FIRST_PREDICTION
    assert rows.iloc[0]["heart_rate"] == 80


def test_stale_values_outside_the_lookback_make_the_row_incomplete():
    # Vitals only at T0: within the 4 h lookback at T0+4h, stale at T0+8h (that row is excluded).
    rows, quality = build(vitals_at(0), stay_hours=10)
    assert list(rows["prediction_time"]) == [FIRST_PREDICTION]
    assert quality["rows_excluded_incomplete_features"] == 1
    assert quality["missing_rate_by_feature"]["heart_rate"] == 0.5


def test_fahrenheit_is_converted_and_invalid_values_are_dropped():
    events = vitals_at(3, skip={223762}) + [
        event(3, 223761, 100.4),       # 38.0 °C
        event(3.5, 220045, 999),       # implausible heart rate
        event(3.5, 220277, "n/a"),     # non-numeric SpO2
    ]
    rows, quality = build(events, stay_hours=6)
    assert rows.iloc[0]["temperature"] == pytest.approx(38.0)
    assert rows.iloc[0]["heart_rate"] == 80
    assert rows.iloc[0]["spo2"] == 97
    assert quality["out_of_range_values_removed"]["heart_rate"] == 1
    assert quality["non_numeric_or_untimed_events_removed"] == 1
    assert quality["fahrenheit_values_converted"] == 1


def test_diastolic_not_below_systolic_excludes_the_row():
    with pytest.raises(PipelineError, match="No rows remain"):
        build(vitals_at(3, {220179: 70, 220180: 90}), stay_hours=6)


def test_label_window_is_forward_looking_and_rows_after_death_are_removed():
    events = [row for hours in range(3, 48, 4) for row in vitals_at(hours)]
    # Death at T0+40h; prediction times every 4 h from T0+4h.
    rows, quality = build(events, deathtime=T0 + pd.Timedelta(hours=40), stay_hours=48)
    labels = dict(zip(rows["prediction_time"], rows["label"]))
    assert labels[FIRST_PREDICTION] == 0          # T0+4h: death 36 h later, outside the window
    assert labels["2150-01-01T20:00:00"] == 0     # T0+12h: death 28 h later
    assert labels["2150-01-02T00:00:00"] == 1     # T0+16h: death exactly 24 h later (inclusive)
    assert labels["2150-01-02T20:00:00"] == 1     # T0+36h: death 4 h later
    assert quality["prediction_times_at_or_after_death_removed"] == 2   # T0+40h and T0+44h
    assert max(rows["prediction_time"]) < "2150-01-03T00:00:00"


def test_death_exactly_at_window_end_is_positive_and_one_second_later_is_not():
    rows, _ = build(vitals_at(3), deathtime=T0 + pd.Timedelta(hours=28), stay_hours=6)
    assert rows.iloc[0]["label"] == 1
    rows, _ = build(vitals_at(3), deathtime=T0 + pd.Timedelta(hours=28, seconds=1), stay_hours=6)
    assert rows.iloc[0]["label"] == 0


def test_underage_stays_are_excluded():
    with pytest.raises(PipelineError, match="No rows remain"):
        build(vitals_at(3), anchor_age=16, stay_hours=6)


def test_output_columns_follow_the_api_feature_order(prepared):
    rows = pd.read_csv(prepared["dataset_dir"] / "dataset.csv")
    assert tuple(column for column in rows.columns if column in FEATURES) == FEATURES
    assert rows[list(FEATURES)].notna().all().all()
    assert rows["label"].isin([0, 1]).all()


def test_fixture_quality_report_counts_injected_problems(prepared):
    quality = json.loads((prepared["dataset_dir"] / "data_quality.json").read_text())
    assert quality["duplicate_events_removed"] > 0
    assert quality["fahrenheit_values_converted"] > 0
    assert sum(quality["out_of_range_values_removed"].values()) > 0
    assert quality["rows_excluded_incomplete_features"] > 0
    assert prepared["manifest"]["synthetic_fixture"] is True
    assert prepared["manifest"]["kind"] == "synthetic-fixture"


def test_missing_tables_and_columns_are_reported(tmp_path):
    with pytest.raises(PipelineError, match="Missing table"):
        load_tables(tmp_path)
    (tmp_path / "hosp").mkdir()
    pd.DataFrame({"subject_id": [1]}).to_csv(tmp_path / "hosp" / "patients.csv", index=False)
    with pytest.raises(PipelineError, match="missing required columns"):
        load_tables(tmp_path)


def test_access_gates(tmp_path, prepared):
    fixture_dir = prepared["root"] / "synthetic-mimic-format"
    assert (fixture_dir / MARKER_FILE).is_file()
    clinical = load_config("mimic_iv")
    with pytest.raises(PipelineError, match="synthetic fixture and cannot be labelled"):
        check_access(clinical, fixture_dir, confirmed=True)
    with pytest.raises(PipelineError, match="BLOCKED"):
        check_access(clinical, tmp_path, confirmed=False)
    with pytest.raises(PipelineError, match="must point at a generated fixture"):
        check_access(load_config("mimic_format_fixture"), tmp_path, confirmed=False)


def test_unconfigured_clinical_dataset_is_blocked(monkeypatch):
    monkeypatch.delenv("MIMIC_IV_DIR", raising=False)
    with pytest.raises(PipelineError, match="BLOCKED"):
        prepare("mimic_iv", confirmed=True)

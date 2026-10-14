"""Fictional data in MIMIC-IV table layout, for exercising the real-data pipeline.

Every value is generated. Nothing here is derived from MIMIC-IV or any patient
record; only the table and column names follow the published MIMIC-IV schema so
the same adapter code path can be tested. Metrics computed on this fixture are
meaningless and must never be reported as model performance.

A SYNTHETIC_FIXTURE.txt marker is written next to the tables; the preparation
step refuses to label such a directory as anything but a synthetic fixture.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

MARKER_FILE = "SYNTHETIC_FIXTURE.txt"
ITEMS = {"heart_rate": 220045, "spo2": 220277, "nibp_sys": 220179, "nibp_dia": 220180,
         "art_sys": 220050, "art_dia": 220051, "resp_rate": 220210, "temp_f": 223761, "temp_c": 223762}
YEAR_GROUPS = ["2008 - 2010", "2011 - 2013", "2014 - 2016", "2017 - 2019"]
FMT = "%Y-%m-%d %H:%M:%S"


def generate_fixture(out_dir: Path, patients: int = 400, seed: int = 11) -> Path:
    out_dir = Path(out_dir)
    (out_dir / "hosp").mkdir(parents=True, exist_ok=True)
    (out_dir / "icu").mkdir(parents=True, exist_ok=True)
    (out_dir / MARKER_FILE).write_text(
        "SYNTHETIC FIXTURE — fictional values in MIMIC-IV table layout. Not patient data. "
        "Never report metrics from this directory as model performance.\n")
    rng = np.random.default_rng(seed)
    patient_rows, admission_rows, stay_rows, event_rows = [], [], [], []
    base = datetime(2150, 1, 1)
    for index in range(patients):
        subject_id, hadm_id, stay_id = 10_000_000 + index, 20_000_000 + index, 30_000_000 + index
        anchor_age = int(rng.integers(18, 91))
        admit = base + timedelta(days=int(rng.integers(0, 365 * 30)), hours=int(rng.integers(0, 24)))
        anchor_year = admit.year
        severity = rng.beta(2, 5)
        stay_hours = float(rng.uniform(24, 120))
        intime = admit + timedelta(hours=float(rng.uniform(1, 12)))
        outtime = intime + timedelta(hours=stay_hours)
        dies = rng.random() < 0.05 + 0.5 * severity ** 2
        deathtime = outtime - timedelta(hours=float(rng.uniform(0, 2))) if dies else None
        dischtime = (deathtime if dies else outtime + timedelta(hours=float(rng.uniform(12, 96))))
        patient_rows.append([subject_id, rng.choice(["F", "M"]), anchor_age, anchor_year,
                             YEAR_GROUPS[index % len(YEAR_GROUPS)], deathtime.strftime("%Y-%m-%d") if dies else ""])
        admission_rows.append([subject_id, hadm_id, admit.strftime(FMT), dischtime.strftime(FMT),
                               deathtime.strftime(FMT) if dies else "", int(dies)])
        stay_rows.append([subject_id, hadm_id, stay_id, intime.strftime(FMT), outtime.strftime(FMT), round(stay_hours / 24, 4)])

        uses_fahrenheit = rng.random() < 0.5
        has_arterial_line = rng.random() < 0.3
        hour = 0.0
        while hour < stay_hours:
            charttime = intime + timedelta(hours=hour)
            # Deterioration builds over the final 24 h before death.
            decline = max(0.0, 1 - (stay_hours - hour) / 24) if dies else 0.0
            drift = severity * 0.6 + decline
            vitals = {
                "heart_rate": rng.normal(82 + 45 * drift, 8),
                "spo2": min(100.0, rng.normal(97 - 9 * drift, 1.5)),
                "sys": rng.normal(124 - 35 * drift, 10),
                "resp_rate": rng.normal(16 + 12 * drift, 2.5),
                "temp_c": rng.normal(37.0 + 1.3 * drift, 0.35),
            }
            vitals["dia"] = vitals["sys"] * rng.uniform(0.55, 0.68)

            def emit(item: str, value: float) -> None:
                if rng.random() < 0.08:  # missing measurement
                    return
                if rng.random() < 0.01:  # implausible charting error
                    value = float(rng.choice([0, 999, -1]))
                # Values are stored (become available) minutes after they are charted.
                stored = charttime + timedelta(minutes=float(rng.uniform(1, 20)))
                event_rows.append([subject_id, hadm_id, stay_id, charttime.strftime(FMT), stored.strftime(FMT),
                                   ITEMS[item], round(value, 1), round(value, 1)])

            emit("heart_rate", vitals["heart_rate"])
            emit("spo2", vitals["spo2"])
            emit("resp_rate", vitals["resp_rate"])
            prefix = "art" if has_arterial_line and rng.random() < 0.7 else "nibp"
            systolic, diastolic = vitals["sys"], vitals["dia"]
            if rng.random() < 0.01:  # transposed blood pressure
                systolic, diastolic = diastolic, systolic
            emit(f"{prefix}_sys", systolic)
            emit(f"{prefix}_dia", diastolic)
            if int(hour) % 4 == 0:
                if uses_fahrenheit:
                    emit("temp_f", vitals["temp_c"] * 9 / 5 + 32)
                else:
                    emit("temp_c", vitals["temp_c"])
            if rng.random() < 0.01 and event_rows:  # exact duplicate row
                event_rows.append(list(event_rows[-1]))
            hour += float(rng.uniform(0.5, 1.5))

    _write(out_dir / "hosp" / "patients.csv", ["subject_id", "gender", "anchor_age", "anchor_year", "anchor_year_group", "dod"], patient_rows)
    _write(out_dir / "hosp" / "admissions.csv", ["subject_id", "hadm_id", "admittime", "dischtime", "deathtime", "hospital_expire_flag"], admission_rows)
    _write(out_dir / "icu" / "icustays.csv", ["subject_id", "hadm_id", "stay_id", "intime", "outtime", "los"], stay_rows)
    _write(out_dir / "icu" / "chartevents.csv", ["subject_id", "hadm_id", "stay_id", "charttime", "storetime", "itemid", "value", "valuenum"], event_rows)
    return out_dir


def _write(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)

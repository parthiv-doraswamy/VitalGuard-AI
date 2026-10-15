"""Fictional monitored cohort and its deterministic vital-sign trajectories.

data/cohort.json is the single source of truth for the demo patients, their
assigned doctors and the demo staff accounts; the frontend imports the same
file. Every person in it is fictional.

cohort_vitals(patient, step) returns the observation a cohort live stream emits
for that patient at that sequence number. It is a pure function of its inputs,
so a retried sequence regenerates identical values.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

COHORT_FILE = Path(__file__).resolve().parent / "data" / "cohort.json"

# Values a deteriorating patient drifts toward, and a recovering patient drifts away from.
DETERIORATED = {"heart_rate": 138.0, "spo2": 85.0, "systolic_bp": 86.0, "diastolic_bp": 50.0,
                "temperature": 39.3, "respiratory_rate": 31.0}
RECOVERED = {"heart_rate": 78.0, "spo2": 97.0, "systolic_bp": 122.0, "diastolic_bp": 78.0,
             "temperature": 36.9, "respiratory_rate": 16.0}
DETERIORATION_STEPS = 18
RECOVERY_STEPS = 20
# Per-vital amplitude of the deterministic beat-to-beat variation.
NOISE = {"heart_rate": 2.2, "spo2": 0.5, "systolic_bp": 2.5, "diastolic_bp": 1.5,
         "temperature": 0.05, "respiratory_rate": 0.7}


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    return json.loads(COHORT_FILE.read_text(encoding="utf-8"))


def patients() -> list[dict[str, Any]]:
    return _load()["patients"]


def staff() -> list[dict[str, Any]]:
    return _load()["staff"]


def get_patient(patient_id: str) -> dict[str, Any] | None:
    return next((patient for patient in patients() if patient["id"] == patient_id), None)


def get_staff(username: str) -> dict[str, Any] | None:
    return next((member for member in staff() if member["username"] == username), None)


def assigned_doctor(patient_id: str) -> str | None:
    patient = get_patient(patient_id)
    return patient["assigned_doctor"] if patient else None


def patients_for(username: str, role: str) -> list[dict[str, Any]]:
    """Doctors see only the patients assigned to them; nurses and admins see the whole cohort."""
    if role == "doctor":
        return [patient for patient in patients() if patient["assigned_doctor"] == username]
    return patients()


def _wobble(step: int, seed: int, vital_index: int) -> float:
    phase = seed * 0.37 + vital_index * 1.3
    return math.sin(step * 0.9 + phase) * 0.6 + math.sin(step * 0.37 + phase * 2) * 0.4


def _seed(patient_id: str) -> int:
    return sum(ord(char) * (index + 1) for index, char in enumerate(patient_id))


def _progress(patient: dict[str, Any], step: int) -> float:
    if patient["scenario"] == "worsening":
        raw = (step - patient.get("onset_step", 0)) / DETERIORATION_STEPS
    elif patient["scenario"] == "recovering":
        raw = step / RECOVERY_STEPS
    else:
        return 0.0
    clamped = min(1.0, max(0.0, raw))
    return clamped * clamped * (3 - 2 * clamped)  # smoothstep: gradual start and finish


def cohort_vitals(patient: dict[str, Any], step: int) -> dict[str, float | int]:
    """Observation for `patient` at stream sequence `step` (deterministic)."""
    step = max(0, min(step, 1000))
    base = patient["baseline"]
    progress = _progress(patient, step)
    target = DETERIORATED if patient["scenario"] == "worsening" else RECOVERED
    seed = _seed(patient["id"])
    values: dict[str, float | int] = {"age": patient["age"]}
    for index, name in enumerate(NOISE):
        start = float(base[name])
        level = start + (target[name] - start) * progress if patient["scenario"] != "stable" else start
        values[name] = level + _wobble(step, seed, index) * NOISE[name]
    values["heart_rate"] = round(min(190.0, max(35.0, values["heart_rate"])), 1)
    values["spo2"] = round(min(100.0, max(70.0, values["spo2"])), 1)
    values["systolic_bp"] = round(min(220.0, max(60.0, values["systolic_bp"])))
    values["diastolic_bp"] = round(min(values["systolic_bp"] - 10, max(30.0, values["diastolic_bp"])))
    values["temperature"] = round(min(42.0, max(34.0, values["temperature"])), 1)
    values["respiratory_rate"] = round(min(45.0, max(6.0, values["respiratory_rate"])), 1)
    return values

"""Deterministic fictional observation generator for the VitalGuard demo.

This simulator exists to exercise ingestion and prediction workflows. It does
not represent a device integration, real patient, or clinically validated
trajectory.
"""
from __future__ import annotations

from typing import Literal

Scenario = Literal["stable", "worsening", "recovering"]


def observation_for_step(scenario: Scenario, step: int) -> dict[str, float | int]:
    """Return repeatable vital signs for a requested scenario and step."""
    step = max(0, min(step, 1000))
    if scenario == "stable":
        return {
            "age": 58, "heart_rate": 78 + (step % 5), "spo2": 97,
            "systolic_bp": 122, "diastolic_bp": 78, "temperature": 37.0,
            "respiratory_rate": 16 + (step % 2),
        }

    if scenario == "worsening":
        return {
            "age": 67,
            "heart_rate": min(145, 88 + step * 4),
            "spo2": max(82, 97 - step * 2),
            "systolic_bp": max(82, 124 - step * 5),
            "diastolic_bp": max(45, 78 - step * 2),
            "temperature": min(39.5, 37.0 + step * 0.25),
            "respiratory_rate": min(34, 17 + step * 2),
        }

    # A recovery scenario moves from abnormal demo values toward a stable range.
    recovery_step = min(step, 6)
    return {
        "age": 67,
        "heart_rate": max(80, 132 - recovery_step * 8),
        "spo2": min(97, 85 + recovery_step * 2),
        "systolic_bp": min(120, 90 + recovery_step * 5),
        "diastolic_bp": min(76, 48 + recovery_step * 4),
        "temperature": max(37.0, 39.0 - recovery_step * 0.3),
        "respiratory_rate": max(17, 31 - recovery_step * 2),
    }

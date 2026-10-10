"""NEWS2 parameter scoring for synthetic software demonstrations only.

Scoring bands are transcribed from the Royal College of Physicians NEWS2 chart.
This module does not issue clinical escalation advice and requires explicit
authorization assertion before using oxygen saturation Scale 2.
"""
from __future__ import annotations

from typing import Any


def score_news2(values: dict[str, Any]) -> dict[str, Any]:
    rr = float(values["respiratory_rate"])
    spo2 = float(values["spo2"])
    systolic = float(values["systolic_bp"])
    pulse = float(values["heart_rate"])
    temperature = float(values["temperature"])
    oxygen = bool(values["supplemental_oxygen"])
    scale = int(values["spo2_scale"])
    consciousness = str(values["consciousness"])

    respiratory_score = 3 if rr <= 8 or rr >= 25 else 1 if 9 <= rr <= 11 else 2 if 21 <= rr <= 24 else 0
    if scale == 1:
        spo2_score = 3 if spo2 <= 91 else 2 if spo2 <= 93 else 1 if spo2 <= 95 else 0
    else:
        # Scale 2 is only available after an explicit clinician-authorization assertion.
        if oxygen:
            spo2_score = 3 if spo2 >= 97 else 2 if spo2 >= 95 else 1 if spo2 >= 93 else 0 if spo2 >= 88 else 1 if spo2 >= 86 else 2 if spo2 >= 84 else 3
        else:
            spo2_score = 0 if spo2 >= 88 else 1 if spo2 >= 86 else 2 if spo2 >= 84 else 3

    systolic_score = 3 if systolic <= 90 or systolic >= 220 else 2 if systolic <= 100 else 1 if systolic <= 110 else 0
    pulse_score = 3 if pulse <= 40 or pulse >= 131 else 1 if pulse <= 50 or pulse <= 110 and pulse >= 91 else 2 if pulse <= 130 and pulse >= 111 else 0
    consciousness_score = 0 if consciousness == "alert" else 3
    temperature_score = 3 if temperature <= 35.0 else 1 if temperature <= 36.0 else 0 if temperature <= 38.0 else 1 if temperature <= 39.0 else 2
    oxygen_score = 2 if oxygen else 0

    components = {
        "respiratory_rate": respiratory_score,
        "spo2": spo2_score,
        "supplemental_oxygen": oxygen_score,
        "systolic_bp": systolic_score,
        "heart_rate": pulse_score,
        "consciousness": consciousness_score,
        "temperature": temperature_score,
    }
    return {
        "score_name": "NEWS2",
        "score_version": "RCP NEWS2 chart (2017)",
        "parameter_scores": components,
        "total_score": sum(components.values()),
        "spo2_scale": scale,
        "supplemental_oxygen": oxygen,
        "demo_only": True,
        "clinically_validated_implementation": False,
        "disclaimer": "Software demonstration only. Verify any clinical scoring against the official RCP chart and local policy. Not for diagnosis, triage, escalation, or treatment.",
    }

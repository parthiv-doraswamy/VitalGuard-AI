"""Descriptive trends over persisted synthetic observations; not a clinical forecast."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

METRICS = {
    "heart_rate": 0.5,
    "spo2": 0.2,
    "systolic_bp": 0.5,
    "temperature": 0.05,
    "respiratory_rate": 0.2,
    "risk_score": 0.5,
}


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def summarize_observation_trends(patient_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(records, key=lambda item: int(item.get("id", 0)))
    metric_values: dict[str, list[float]] = {name: [] for name in METRICS}
    for record in ordered:
        inputs = record.get("inputs") or {}
        prediction = record.get("prediction") or {}
        for name in METRICS:
            value = prediction.get("risk_score") if name == "risk_score" else inputs.get(name)
            if value is not None:
                metric_values[name].append(float(value))

    trends = []
    for name, threshold in METRICS.items():
        values = metric_values[name]
        if len(values) < 2:
            trends.append({"metric": name, "sample_count": len(values), "status": "insufficient_data"})
            continue
        x_mean = (len(values) - 1) / 2
        y_mean = sum(values) / len(values)
        denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
        slope = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values)) / denominator if denominator else 0.0
        direction = "increasing" if slope > threshold else "decreasing" if slope < -threshold else "stable"
        trends.append({
            "metric": name,
            "sample_count": len(values),
            "first_value": round(values[0], 3),
            "latest_value": round(values[-1], 3),
            "absolute_change": round(values[-1] - values[0], 3),
            "slope_per_observation": round(slope, 4),
            "direction": direction,
            "stability_threshold": threshold,
        })

    timestamps = [_timestamp(item.get("created_at")) for item in ordered]
    valid_timestamps = [value for value in timestamps if value is not None]
    return {
        "patient_id": patient_id,
        "observation_count": len(ordered),
        "first_observed_at": valid_timestamps[0].isoformat() if valid_timestamps else None,
        "last_observed_at": valid_timestamps[-1].isoformat() if valid_timestamps else None,
        "trends": trends,
        "method": "ordinary least-squares slope over observation order",
        "interpretation": "Descriptive history only. No future values are forecast and no clinical meaning is inferred.",
        "demo_only": True,
        "clinically_validated": False,
    }

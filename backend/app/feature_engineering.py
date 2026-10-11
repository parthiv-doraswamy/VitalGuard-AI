"""Deterministic, time-aware feature engineering for fictional demo observations.

This module is intentionally not wired into the live model yet. The existing
seven-feature model remains the serving baseline until the candidate features
have separate evaluation and a reviewed model-version change.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

RAW_FEATURES = (
    "age", "heart_rate", "spo2", "systolic_bp", "diastolic_bp",
    "temperature", "respiratory_rate",
)
TREND_FEATURES = ("heart_rate", "spo2", "systolic_bp", "respiratory_rate")
FEATURE_SET_VERSION = "demo-temporal-features-0.1.0"


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at must be an ISO-8601 timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at must include a timezone offset")
    return value.astimezone(timezone.utc)


def build_temporal_features(
    observations: list[dict[str, Any]],
    *,
    prediction_time: str | datetime | None = None,
    window_size: int = 3,
    min_window_count: int = 2,
) -> dict[str, Any]:
    """Build a versioned feature row using only observations available by prediction time.

    Each row must contain an aware `observed_at` timestamp and the seven raw
    features. Duplicate timestamps are rejected to avoid ambiguous ordering.
    Trend deltas compare the latest eligible reading with the previous one.
    Rolling means use the latest `window_size` eligible readings and are
    emitted only when `min_window_count` readings are available.
    """
    if not observations:
        raise ValueError("at least one observation is required")
    if not 1 <= window_size <= 100:
        raise ValueError("window_size must be between 1 and 100")
    if not 1 <= min_window_count <= window_size:
        raise ValueError("min_window_count must be between 1 and window_size")

    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for item in observations:
        if not isinstance(item, dict):
            raise ValueError("each observation must be an object")
        if "observed_at" not in item:
            raise ValueError("each observation requires observed_at")
        timestamp = _parse_timestamp(item["observed_at"])
        missing = [name for name in RAW_FEATURES if name not in item or item[name] is None]
        if missing:
            raise ValueError(f"observation missing required features: {', '.join(missing)}")
        row: dict[str, Any] = {}
        for name in RAW_FEATURES:
            value = item[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            row[name] = value
        parsed.append((timestamp, row))

    parsed.sort(key=lambda entry: entry[0])
    timestamps = [entry[0] for entry in parsed]
    if len(set(timestamps)) != len(timestamps):
        raise ValueError("duplicate observation timestamps are not supported")

    cutoff = _parse_timestamp(prediction_time) if prediction_time is not None else timestamps[-1]
    eligible = [(ts, row) for ts, row in parsed if ts <= cutoff]
    if not eligible:
        raise ValueError("no observations are available at prediction_time")

    latest_ts, latest = eligible[-1]
    result: dict[str, Any] = {
        **latest,
        "feature_set_version": FEATURE_SET_VERSION,
        "observation_count": len(eligible),
        "latest_observed_at": latest_ts.isoformat().replace("+00:00", "Z"),
        "latest_observation_age_seconds": max(0.0, (cutoff - latest_ts).total_seconds()),
        "trend_deltas": {},
        "rolling_means": {},
    }

    if len(eligible) >= 2:
        previous = eligible[-2][1]
        result["elapsed_seconds_since_previous"] = (latest_ts - eligible[-2][0]).total_seconds()
        result["trend_deltas"] = {
            name: round(float(latest[name] - previous[name]), 6)
            for name in TREND_FEATURES
        }
    else:
        result["elapsed_seconds_since_previous"] = None

    window = eligible[-window_size:]
    if len(window) >= min_window_count:
        result["rolling_means"] = {
            name: round(sum(float(row[name]) for _, row in window) / len(window), 6)
            for name in TREND_FEATURES
        }
        result["rolling_window_count"] = len(window)
    else:
        result["rolling_window_count"] = len(window)

    return result

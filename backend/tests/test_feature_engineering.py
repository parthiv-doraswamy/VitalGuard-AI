from datetime import datetime, timezone, timedelta

import pytest

from app.feature_engineering import FEATURE_SET_VERSION, build_temporal_features


BASE = {
    "age": 58, "heart_rate": 80, "spo2": 97, "systolic_bp": 120,
    "diastolic_bp": 78, "temperature": 37.0, "respiratory_rate": 16,
}


def row(minutes, **updates):
    timestamp = datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return {**BASE, "observed_at": timestamp.isoformat(), **updates}


def test_features_are_deterministic_and_versioned():
    rows = [row(0), row(5, heart_rate=90, spo2=95)]
    first = build_temporal_features(rows)
    second = build_temporal_features(list(reversed(rows)))
    assert first == second
    assert first["feature_set_version"] == FEATURE_SET_VERSION
    assert first["trend_deltas"]["heart_rate"] == 10
    assert first["trend_deltas"]["spo2"] == -2
    assert first["rolling_means"]["heart_rate"] == 85
    assert first["elapsed_seconds_since_previous"] == 300


def test_prediction_time_excludes_future_observations():
    rows = [row(0), row(5, heart_rate=90), row(10, heart_rate=150)]
    result = build_temporal_features(rows, prediction_time=row(5)["observed_at"])
    assert result["heart_rate"] == 90
    assert result["observation_count"] == 2
    assert result["latest_observation_age_seconds"] == 0


def test_one_observation_does_not_fabricate_delta_or_rolling_mean():
    result = build_temporal_features([row(0)])
    assert result["trend_deltas"] == {}
    assert result["elapsed_seconds_since_previous"] is None
    assert result["rolling_means"] == {}
    assert result["rolling_window_count"] == 1


def test_naive_timestamp_is_rejected():
    bad = {**BASE, "observed_at": "2026-10-11T10:00:00"}
    with pytest.raises(ValueError, match="timezone"):
        build_temporal_features([bad])


def test_duplicate_timestamps_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        build_temporal_features([row(0), row(0, heart_rate=90)])


def test_missing_fields_and_unknown_prediction_window_fail_closed():
    missing = row(0)
    del missing["spo2"]
    with pytest.raises(ValueError, match="spo2"):
        build_temporal_features([missing])
    with pytest.raises(ValueError, match="no observations"):
        build_temporal_features([row(5)], prediction_time=row(0)["observed_at"])


def test_invalid_window_configuration_is_rejected():
    with pytest.raises(ValueError, match="window_size"):
        build_temporal_features([row(0)], window_size=0)
    with pytest.raises(ValueError, match="min_window_count"):
        build_temporal_features([row(0)], window_size=2, min_window_count=3)

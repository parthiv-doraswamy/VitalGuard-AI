from datetime import datetime, timezone, timedelta
from app.data_quality import assess_observations


def record(record_id, patient_id, created_at, inputs):
    return {"id": record_id, "patient_id": patient_id, "created_at": created_at.isoformat(),
            "inputs": inputs}


def test_quality_flags_stale_incomplete_and_fresh():
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    complete = {"heart_rate": 80, "spo2": 98, "systolic_bp": 120, "diastolic_bp": 75,
                "temperature": 37.0, "respiratory_rate": 16}
    rows = [
        record(1, "DEMO-STALE", now - timedelta(minutes=10), complete),
        record(2, "DEMO-FRESH", now - timedelta(seconds=20), complete),
        record(3, "DEMO-INCOMPLETE", now - timedelta(seconds=10), {"heart_rate": 80}),
    ]
    result = assess_observations(rows, stale_after_seconds=300, now=now)
    by_patient = {item["patient_id"]: item for item in result["items"]}
    assert by_patient["DEMO-STALE"]["status"] == "stale"
    assert by_patient["DEMO-FRESH"]["status"] == "fresh"
    assert by_patient["DEMO-INCOMPLETE"]["status"] == "incomplete"
    assert "spo2" in by_patient["DEMO-INCOMPLETE"]["missing_fields"]


def test_quality_uses_latest_observation_for_each_patient():
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    old = record(1, "DEMO-1", now - timedelta(hours=1), {})
    recent = record(2, "DEMO-1", now - timedelta(seconds=10),
                    {"heart_rate": 80, "spo2": 98, "systolic_bp": 120, "diastolic_bp": 75,
                     "temperature": 37.0, "respiratory_rate": 16})
    result = assess_observations([recent, old], now=now)
    assert result["count"] == 1
    assert result["items"][0]["latest_observation_id"] == 2
    assert result["items"][0]["status"] == "fresh"

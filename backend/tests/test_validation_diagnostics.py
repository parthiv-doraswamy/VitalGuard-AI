from app.validation_diagnostics import evaluate_synthetic_calibration_and_subgroups


def test_calibration_and_subgroup_report_is_reproducible_and_subject_disjoint():
    first = evaluate_synthetic_calibration_and_subgroups(seed=20261011)
    second = evaluate_synthetic_calibration_and_subgroups(seed=20261011)
    assert first == second
    assert first["subject_overlap"] == []
    assert first["train_subject_count"] + first["test_subject_count"] == 240
    assert first["demo_only"] is True
    assert first["clinically_validated"] is False
    assert 0 <= first["brier_score"] <= 1
    assert 0 <= first["roc_auc"] <= 1
    assert len(first["calibration_bins"]) == 5
    assert sum(item["count"] for item in first["calibration_bins"]) == first["test_row_count"]


def test_subgroups_always_report_counts_and_availability_reason_or_metrics():
    result = evaluate_synthetic_calibration_and_subgroups(seed=20261012)
    assert set(result["age_subgroups"]) == {"under_40", "age_40_to_64", "age_65_plus"}
    for group in result["age_subgroups"].values():
        assert group["count"] >= 0
        assert 0 <= group["positive_count"] <= group["count"]
        if group["available"]:
            assert 0 <= group["precision"] <= 1
            assert 0 <= group["recall"] <= 1
        else:
            assert group["reason"]

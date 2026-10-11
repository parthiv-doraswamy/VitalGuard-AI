from app.grouped_feature_evaluation import evaluate_grouped_temporal_features


def test_grouped_evaluation_is_reproducible_and_has_no_subject_overlap():
    first = evaluate_grouped_temporal_features(seed=20261011)
    second = evaluate_grouped_temporal_features(seed=20261011)
    assert first == second
    assert first["evaluation_type"] == "synthetic subject-grouped holdout"
    assert first["subject_overlap"] == []
    assert first["train_subject_count"] + first["test_subject_count"] == first["subject_count"]
    assert first["candidate_feature_count"] > first["baseline_feature_count"]
    assert first["train_row_count"] > 0 and first["test_row_count"] > 0
    assert first["demo_only"] is True
    assert first["clinically_validated"] is False


def test_evaluation_reports_both_candidates_without_claiming_clinical_validity():
    result = evaluate_grouped_temporal_features(seed=20261012)
    for key in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        assert 0 <= result["baseline_metrics"][key] <= 1
        assert 0 <= result["candidate_metrics"][key] <= 1
    assert any("not clinical performance" in item.lower() for item in result["limitations"])

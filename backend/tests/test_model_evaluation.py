from app.model_evaluation import coefficient_contributions, evaluate_synthetic_holdout


def test_synthetic_holdout_metrics_are_bounded_and_disclaimed():
    report = evaluate_synthetic_holdout()
    assert report["sample_count"] == 3000
    for metric in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        assert 0 <= report["metrics"][metric] <= 1
    assert report["demo_only"] is True
    assert report["clinically_validated"] is False
    assert report["confusion_matrix"]["rows_actual_columns_predicted"] == [[
        report["confusion_matrix"]["rows_actual_columns_predicted"][0][0],
        report["confusion_matrix"]["rows_actual_columns_predicted"][0][1],
    ], [
        report["confusion_matrix"]["rows_actual_columns_predicted"][1][0],
        report["confusion_matrix"]["rows_actual_columns_predicted"][1][1],
    ]]


def test_contributions_are_sorted_and_explicit_about_method():
    values = {"age": 58, "heart_rate": 82, "spo2": 98, "systolic_bp": 122,
              "diastolic_bp": 78, "temperature": 37.0, "respiratory_rate": 16}
    contributions = coefficient_contributions(values)
    assert len(contributions) == 7
    magnitudes = [abs(item["standardized_log_odds_contribution"]) for item in contributions]
    assert magnitudes == sorted(magnitudes, reverse=True)
    assert all(item["method"] == "standardized logistic-regression coefficient contribution" for item in contributions)

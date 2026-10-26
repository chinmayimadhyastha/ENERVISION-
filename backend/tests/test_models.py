import pytest

from backend.tests.helpers import SOLAR_PLANT_ID


def test_model_performance_separates_current_and_historical_metrics(client):
    response = client.get("/api/model-performance")
    assert response.status_code == 200
    body = response.get_json()

    assert body["frequency"] == "daily"
    assert body["target"] == "DailyGeneration_MU"
    assert body["unit"] == "MU/day"
    assert body["comparison_policy"][
        "historical_25_feature_metrics_comparable_to_current"
    ] is False

    rf = body["models"]["random_forest"]
    assert rf["feature_count"] == 24
    current = rf["metrics"]["current_leakage_free_24_feature"]
    assert current["MAE"] == pytest.approx(0.132150218240383)
    assert current["RMSE"] == pytest.approx(0.28278781980879913)
    assert current["R2"] == pytest.approx(0.8970816491056874)
    assert current["train_rows"] == 23268
    assert current["test_rows"] == 5842
    assert current["plants"] == 37
    assert current["features"] == 24

    historical = rf["metrics"]["historical_25_feature_reference"]
    assert historical["MAE"] == pytest.approx(0.11163797642553697)
    assert historical["leakage_affected"] is True
    assert historical["comparable_to_current_24_feature_model"] is False
    assert historical["usage"] == "provenance_only"
    assert "historical_25_feature_reference" != "current_leakage_free_24_feature"

    assert rf["prediction_stats"]["negative_count"] == 0
    assert rf["prediction_stats"]["finite"] is True

    solar = body["models"]["solar_lstm"]
    assert solar["feature_count"] == 12
    assert solar["sequence_length"] == 7
    assert solar["metrics"]["committed_actual"]["MAE"] == pytest.approx(
        0.14415674553172728
    )

    wind = body["models"]["wind_lstm"]
    assert wind["feature_count"] == 12
    assert wind["sequence_length"] == 7
    assert wind["metrics"]["committed_actual"]["MAE"] == pytest.approx(
        0.6832080933787058
    )


def test_feature_importance_uses_impurity_and_never_claims_shap(client):
    response = client.get("/api/feature-importance")
    assert response.status_code == 200
    body = response.get_json()

    assert body["method"] == "random_forest_impurity"
    assert body["shap_used"] is False
    assert "not SHAP" in body["method_description"]
    assert body["feature_count"] == 24
    assert body["importance_sum"] == pytest.approx(1.0)

    features = body["features"]
    assert len(features) == 24
    assert features[0]["feature"] == "Generation_lag_1"
    assert [row["rank"] for row in features] == list(range(1, 25))
    importances = [row["importance"] for row in features]
    assert importances == sorted(importances, reverse=True)
    assert "Generation_per_MW" not in {row["feature"] for row in features}
    assert "DailyGeneration_MU" not in {row["feature"] for row in features}

    historical = body["historical_25_feature_reference"]
    assert historical["leakage_affected"] is True
    assert historical["comparable_to_current"] is False
    assert "Generation_per_MW" in {
        row["feature"] for row in historical["features"]
    }


def test_feature_importance_missing_report_is_503(client, container, monkeypatch, tmp_path):
    monkeypatch.setattr(
        container.config, "FEATURE_IMPORTANCE_PATH", tmp_path / "missing.csv"
    )
    response = client.get("/api/feature-importance")
    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "REPORT_UNAVAILABLE"
    assert "generation_feature_importance.csv" in body["error"]["message"]


def test_feature_importance_invalid_report_is_503(client, container, monkeypatch, tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Feature,Importance\nGeneration_per_MW,1.0\n", encoding="utf-8")
    monkeypatch.setattr(container.config, "FEATURE_IMPORTANCE_PATH", path)
    response = client.get("/api/feature-importance")
    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "REPORT_INVALID"
    assert "Generation_per_MW" in body["error"]["message"]

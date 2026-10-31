"""Tests for SHAP explainability on production Solar and Wind LSTM models."""

from __future__ import annotations

import math
import pytest

from backend.tests.helpers import SOLAR_PLANT_ID, WIND_PLANT_ID, NEGATIVE_WIND_PLANT_ID


EXPECTED_LSTM_FEATURES = [
    "Capacity_MW",
    "Temperature",
    "Humidity",
    "WindSpeed",
    "GHI",
    "Pressure",
    "Month_sin",
    "Month_cos",
    "DayOfYear_sin",
    "DayOfYear_cos",
    "Lagged_Generation",
    "Rolling_Generation_7",
]


def test_solar_lstm_explanation_structure_and_efficiency(client):
    response = client.get(f"/api/forecast/explain?plant_id={SOLAR_PLANT_ID}")
    assert response.status_code == 200
    body = response.get_json()

    assert body["status"] == "ok"
    assert body["plant_id"] == SOLAR_PLANT_ID
    assert body["renewable_type"] == "Solar"
    assert body["model_id"] == "solar_lstm_daily"
    assert body["serving_model"] == "Solar LSTM (daily)"
    assert body["unit"] == "MU/day"
    assert body["explainer_method"] == "KernelExplainer (SHAP)"

    point_forecast = body["point_forecast"]
    baseline = body["baseline_forecast"]
    net_shift = body["net_feature_contribution"]

    assert math.isfinite(point_forecast)
    assert math.isfinite(baseline)
    assert math.isfinite(net_shift)

    # Shapley efficiency: Baseline + sum(attributions) == point_forecast
    assert abs((baseline + net_shift) - point_forecast) < 1e-4
    assert body["shapley_efficiency_diff"] < 1e-4

    # Feature attributions validation
    attributions = body["feature_attributions"]
    assert len(attributions) == 12

    returned_features = [item["feature"] for item in attributions]
    assert set(returned_features) == set(EXPECTED_LSTM_FEATURES)

    for item in attributions:
        assert math.isfinite(item["attribution"])
        assert math.isfinite(item["latest_value"])
        assert math.isfinite(item["mean_value"])
        assert item["direction"] in ("positive", "negative")
        assert 1 <= item["rank"] <= 12
        assert item["label"] is not None

    # Ranking must be in descending order of absolute impact
    abs_impacts = [item["abs_impact"] for item in attributions]
    assert abs_impacts == sorted(abs_impacts, reverse=True)

    # Temporal 7-day breakdown validation
    temporal = body["temporal_breakdown"]
    assert len(temporal) == 7
    for step in temporal:
        assert 1 <= step["step_index"] <= 7
        assert math.isfinite(step["net_impact"])
        assert len(step["feature_contributions"]) == 12

    # Verify limitations disclaimer exists and warns about P10/P50/P90
    assert any("P10/P50/P90" in lim for lim in body["limitations"])


def test_wind_lstm_explanation_structure_and_efficiency(client):
    response = client.get(f"/api/forecast/explain?plant_id={NEGATIVE_WIND_PLANT_ID}")
    assert response.status_code == 200
    body = response.get_json()

    assert body["status"] == "ok"
    assert body["plant_id"] == NEGATIVE_WIND_PLANT_ID
    assert body["renewable_type"] == "Wind"
    assert body["model_id"] == "wind_lstm_daily"
    assert body["serving_model"] == "Wind LSTM (daily)"
    assert body["unit"] == "MU/day"

    point_forecast = body["point_forecast"]
    baseline = body["baseline_forecast"]
    net_shift = body["net_feature_contribution"]

    assert math.isfinite(point_forecast)
    assert math.isfinite(baseline)
    assert math.isfinite(net_shift)

    # Shapley efficiency
    assert abs((baseline + net_shift) - point_forecast) < 1e-4

    attributions = body["feature_attributions"]
    assert len(attributions) == 12


def test_rf_model_is_excluded_from_shap(client):
    response = client.get(f"/api/forecast/explain?plant_id={SOLAR_PLANT_ID}&model=rf")
    assert response.status_code == 422
    body = response.get_json()
    assert body["error"]["code"] == "UNSUPPORTED_EXPLAINER_MODEL"
    assert "Random Forest SHAP is excluded by policy" in body["error"]["message"]


def test_invalid_plant_returns_404(client):
    response = client.get("/api/forecast/explain?plant_id=non-existent-plant")
    assert response.status_code == 404
    body = response.get_json()
    assert body["error"]["code"] == "PLANT_NOT_FOUND"


def test_explanation_by_path(client):
    response = client.get(f"/api/forecast/{SOLAR_PLANT_ID}/explain")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["plant_id"] == SOLAR_PLANT_ID


def test_post_explanation(client):
    response = client.post("/api/forecast/explain", json={"plant_id": SOLAR_PLANT_ID})
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["plant_id"] == SOLAR_PLANT_ID


def test_existing_forecast_endpoints_remain_backward_compatible(client):
    response = client.get(f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=auto&horizon=1&include_confidence=true")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert len(body["forecasts"]) == 1
    day1 = body["forecasts"][0]
    assert day1["p10"] is not None
    assert day1["p50"] is not None
    assert day1["p90"] is not None
    assert day1["p10"] <= day1["p50"] <= day1["p90"]

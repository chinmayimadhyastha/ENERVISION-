"""Unit and integration tests for enhanced endpoints, confidence, and explainability."""

from __future__ import annotations

from backend.services.weather_service import UnavailableFutureWeatherProvider

SOLAR_PLANT_ID = "koppal-tpsaurya-s"
WIND_PLANT_ID = "gadag-vena-w"


def test_models_registry_endpoints(client):
    res = client.get("/api/models")
    assert res.status_code == 200
    body = res.get_json()
    assert body["count"] >= 3
    ids = [m["model_id"] for m in body["models"]]
    assert "random_forest_daily" in ids
    assert "solar_lstm_daily" in ids
    assert "wind_lstm_daily" in ids

    # Specific model detail
    res_rf = client.get("/api/models/random_forest_daily")
    assert res_rf.status_code == 200
    rf_body = res_rf.get_json()
    assert rf_body["model_id"] == "random_forest_daily"
    assert "RandomForest" in rf_body["model_type"]
    assert rf_body["feature_count"] == 24

    # 404 for unknown model
    res_404 = client.get("/api/models/non_existent_model")
    assert res_404.status_code == 404
    assert res_404.get_json()["error"]["code"] == "MODEL_NOT_FOUND"


def test_forecast_confidence_intervals(client, container, observed_weather):
    container.weather.future_provider = observed_weather
    try:
        # 1. Random Forest forecast with confidence
        res = client.get(
            f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=rf&horizon=1&base_date=2026-08-01&include_confidence=true"
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["status"] == "ok"
        assert body["confidence"] is not None
        assert "lower_80" in body["confidence"]
        assert "upper_80" in body["confidence"]
        assert "lower_95" in body["confidence"]
        assert "upper_95" in body["confidence"]
        assert body["confidence"]["lower_95"] <= body["confidence"]["upper_95"]
        assert "p10" in body["confidence"]
        assert "p50" in body["confidence"]
        assert "p90" in body["confidence"]
        assert 0.0 <= body["confidence"]["p10"] <= body["confidence"]["p50"] <= body["confidence"]["p90"]
        assert body["confidence"]["method"] in ("ensemble_tree_quantiles", "conformalized_quantile_regression_pinball_loss")

        # 2. LSTM forecast with confidence
        res_lstm = client.get(
            f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=lstm&horizon=1&include_confidence=true"
        )
        assert res_lstm.status_code == 200
        body_lstm = res_lstm.get_json()
        assert body_lstm["status"] == "ok"
        assert body_lstm["confidence"] is not None
        assert "p10" in body_lstm["confidence"]
        assert "p50" in body_lstm["confidence"]
        assert "p90" in body_lstm["confidence"]
        assert 0.0 <= body_lstm["confidence"]["p10"] <= body_lstm["confidence"]["p50"] <= body_lstm["confidence"]["p90"]
        assert body_lstm["confidence"]["method"] in ("test_set_residual_error", "calibrated_residual_quantiles")
    finally:
        container.weather.future_provider = UnavailableFutureWeatherProvider()


def test_forecast_explainability_and_endpoint(client, container, observed_weather):
    container.weather.future_provider = observed_weather
    try:
        # 1. Query parameter include_explanation
        res = client.get(
            f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=rf&horizon=1&base_date=2026-08-01&include_explanation=true"
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["status"] == "ok"
        assert "explanation" in body["forecasts"][0]
        explanations = body["forecasts"][0]["explanation"]
        assert len(explanations) == 24
        assert "feature" in explanations[0]
        assert "impact" in explanations[0]
        assert "direction" in explanations[0]

        # 2. Dedicated explainability endpoint
        res_expl = client.get(f"/api/explainability/{SOLAR_PLANT_ID}")
        assert res_expl.status_code == 200
        expl_body = res_expl.get_json()
        assert expl_body["plant_id"] == SOLAR_PLANT_ID
        assert expl_body["model"] == "random_forest_daily"
        assert len(expl_body["top_features"]) == 10
        assert len(expl_body["all_features"]) == 24
    finally:
        container.weather.future_provider = UnavailableFutureWeatherProvider()


def test_post_forecast_and_plant_route_aliases(client, container, observed_weather):
    container.weather.future_provider = observed_weather
    try:
        # POST /api/forecast
        post_data = {
            "plant_id": SOLAR_PLANT_ID,
            "model": "rf",
            "horizon": 2,
            "base_date": "2026-08-01",
            "include_confidence": True,
        }
        res_post = client.post("/api/forecast", json=post_data)
        assert res_post.status_code == 200
        body_post = res_post.get_json()
        assert body_post["status"] == "ok"
        assert body_post["horizon_days"] == 2
        assert len(body_post["forecasts"]) == 2

        # GET /api/forecast/<plant_id>
        res_path = client.get(f"/api/forecast/{SOLAR_PLANT_ID}?model=rf&horizon=1&base_date=2026-08-01")
        assert res_path.status_code == 200
        body_path = res_path.get_json()
        assert body_path["status"] == "ok"

        # GET /api/weather/<plant_id>
        res_weather = client.get(f"/api/weather/{SOLAR_PLANT_ID}")
        assert res_weather.status_code == 200
        assert res_weather.get_json()["plant_id"] == SOLAR_PLANT_ID

        # GET /api/generation/<plant_id> and /api/generation/history
        res_gen_plant = client.get(f"/api/generation/{SOLAR_PLANT_ID}")
        assert res_gen_plant.status_code == 200
        res_gen_hist = client.get("/api/generation/history")
        assert res_gen_hist.status_code == 200
    finally:
        container.weather.future_provider = UnavailableFutureWeatherProvider()

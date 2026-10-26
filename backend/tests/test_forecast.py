import pytest

from backend.tests.helpers import (
    LATEST_FLEET_DATE,
    NEGATIVE_WIND_PLANT_ID,
    SOLAR_PLANT_ID,
    WIND_PLANT_ID,
)


def test_rf_forecast_reports_exact_missing_future_weather(client):
    response = client.get(
        f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=rf&horizon=3"
    )
    assert response.status_code == 200
    body = response.get_json()

    assert body["status"] == "weather_required"
    assert body["model"] == "random_forest_daily"
    assert body["model_family"] == "random_forest"
    assert body["model_requested"] == "rf"
    assert body["base_date"] == LATEST_FLEET_DATE.isoformat()
    assert body["forecast_dates"] == ["2026-08-06", "2026-08-07", "2026-08-08"]
    assert body["forecasts"] == []
    assert body["confidence"] is None
    assert body["frequency"] == "daily"
    assert body["unit"] == "MU/day"
    assert body["input_contract"]["feature_count"] == 24
    assert body["input_contract"]["target_day_weather_required"] is True
    assert body["input_contract"]["uses_prediction_day_target"] is False

    missing = body["missing_weather"]
    assert [item["date"] for item in missing] == [
        "2026-08-06",
        "2026-08-07",
        "2026-08-08",
    ]
    assert missing[0]["missing_inputs"] == [
        "Temperature",
        "Humidity",
        "WindSpeed",
        "GHI",
        "Pressure",
    ]
    assert body["missing_weather_summary"]["count"] == 3
    assert body["required_weather"]["target_day_weather_required"] is True
    assert body["required_weather"]["dates"] == [
        "2026-08-06",
        "2026-08-07",
        "2026-08-08",
    ]
    assert body["future_weather"]["provider_available"] is False
    assert body["future_weather"]["is_forecast"] is False


def test_solar_lstm_one_day_forecast_succeeds_without_future_weather(client):
    response = client.get(
        f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=lstm&horizon=1"
    )
    assert response.status_code == 200
    body = response.get_json()

    assert body["status"] == "ok"
    assert body["model"] == "solar_lstm_daily"
    assert body["model_family"] == "lstm"
    assert body["base_date"] == LATEST_FLEET_DATE.isoformat()
    assert body["forecast_dates"] == ["2026-08-06"]
    assert body["input_contract"] == {
        "model_family": "lstm",
        "input_shape": [7, 12],
        "sequence_length": 7,
        "feature_count": 12,
        "target_day_weather_required": False,
        "intermediate_day_weather_required": False,
        "uses_prediction_day_target": False,
        "observed_input_shape": [7, 12],
    }
    assert body["history_context"]["sequence_length"] == 7
    assert len(body["history_context"]["sequence_dates"]) == 7
    assert body["history_context"]["sequence_dates"][-1] == LATEST_FLEET_DATE.isoformat()
    assert body["history_context"]["sequence_calendar_consecutive"] is True
    assert body["history_context"]["target_day_weather_required"] is False
    assert body["history_context"]["target_day_target_used"] is False

    forecast = body["forecasts"][0]
    assert forecast["date"] == "2026-08-06"
    assert forecast["horizon_day"] == 1
    assert forecast["frequency"] == "daily"
    assert forecast["unit"] == "MU/day"
    assert forecast["confidence"] is None
    assert forecast["prediction"] == max(forecast["raw_prediction"], 0.0)
    assert "features" not in forecast
    assert body["post_processing"]["method"] == "max(raw_prediction, 0.0)"


def test_wind_lstm_one_day_forecast_succeeds_without_future_weather(client):
    response = client.get(
        f"/api/forecast?plant_id={WIND_PLANT_ID}&model=lstm&horizon=1"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["model"] == "wind_lstm_daily"
    assert body["model_family"] == "lstm"
    assert body["forecast_dates"] == ["2026-08-06"]
    assert len(body["forecasts"]) == 1
    assert body["forecasts"][0]["confidence"] is None
    assert "Wind LSTM" in " ".join(body["notes"])


def test_auto_model_selects_type_specific_lstm(client):
    solar = client.get(f"/api/forecast?plant_id={SOLAR_PLANT_ID}&horizon=1").get_json()
    assert solar["status"] == "ok"
    assert solar["model_requested"] == "auto"
    assert solar["model"] == "solar_lstm_daily"

    wind = client.get(f"/api/forecast?plant_id={WIND_PLANT_ID}&horizon=1").get_json()
    assert wind["status"] == "ok"
    assert wind["model_requested"] == "auto"
    assert wind["model"] == "wind_lstm_daily"


def test_lstm_multi_day_requires_only_intermediate_weather(client):
    response = client.get(
        f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=lstm&horizon=2"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "weather_required"
    assert body["model"] == "solar_lstm_daily"
    assert body["required_weather"]["target_day_weather_required"] is False
    assert body["required_weather"]["dates"] == ["2026-08-06"]
    assert body["missing_weather_summary"]["count"] == 1
    assert body["forecasts"] == []


def test_default_horizon_is_three_days(client):
    response = client.get(f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=rf")
    body = response.get_json()
    assert response.status_code == 200
    assert body["horizon_days"] == 3
    assert body["forecast_dates"] == ["2026-08-06", "2026-08-07", "2026-08-08"]


def test_historical_wind_inference_preserves_negative_raw_value(client):
    response = client.get(
        f"/api/forecast?plant_id={NEGATIVE_WIND_PLANT_ID}"
        "&model=lstm&horizon=1&base_date=2026-06-19"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["model"] == "wind_lstm_daily"
    assert body["base_date"] == "2026-06-19"
    assert body["forecast_dates"] == ["2026-06-20"]

    forecast = body["forecasts"][0]
    assert forecast["raw_prediction"] < 0
    assert forecast["prediction"] == 0.0
    assert forecast["clamp_applied"] is True
    assert body["post_processing"]["applied"] is True
    assert body["post_processing"]["affected_dates"] == ["2026-06-20"]
    assert "max(raw_prediction, 0.0)" in body["post_processing"]["method"]


def test_insufficient_history_returns_structured_state(client):
    response = client.get(
        f"/api/forecast?plant_id={SOLAR_PLANT_ID}"
        "&model=lstm&horizon=1&base_date=2026-05-03"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "insufficient_history"
    assert body["forecasts"] == []
    assert body["insufficient_history"]["available_rows"] == 3
    assert body["insufficient_history"]["required_rows"] == 7
    assert body["insufficient_history"]["reason"] == "lstm_requires_seven_feature_rows"
    assert "No prediction" in body["reason"]


def test_forecast_rejects_hourly_and_out_of_range_horizons(client):
    for horizon in ("0", "8", "3h", "24h", "abc", "-1"):
        response = client.get(
            f"/api/forecast?plant_id={SOLAR_PLANT_ID}&horizon={horizon}"
        )
        assert response.status_code == 400, horizon
        body = response.get_json()
        assert body["error"]["code"] == "INVALID_HORIZON"
        assert "Hourly horizons" in body["error"]["message"] or "between 1 and 7" in body["error"]["message"]


def test_forecast_rejects_invalid_model(client):
    response = client.get(
        f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=xgboost"
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "INVALID_MODEL"
    assert body["error"]["details"]["allowed_values"] == ["rf", "lstm", "auto"]


def test_forecast_requires_plant_id(client):
    response = client.get("/api/forecast?model=rf")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "MISSING_PARAMETER"


def test_forecast_unknown_plant_is_404(client):
    response = client.get("/api/forecast?plant_id=unknown-plant&model=rf")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "PLANT_NOT_FOUND"


def test_forecast_rejects_base_date_after_last_observation(client):
    response = client.get(
        f"/api/forecast?plant_id={SOLAR_PLANT_ID}&base_date=2026-08-06"
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "INVALID_BASE_DATE"
    assert body["error"]["details"]["last_observed_date"] == "2026-08-05"


def test_forecast_rejects_invalid_base_date_format(client):
    response = client.get(
        f"/api/forecast?plant_id={SOLAR_PLANT_ID}&base_date=06-08-2026"
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_DATE"


def test_no_hourly_labels_or_synthetic_hourly_values(client):
    body = client.get(
        f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=lstm&horizon=1"
    ).get_json()
    for row in body["forecasts"]:
        assert len(row["date"]) == 10
        assert row["frequency"] == "daily"
        assert row["unit"] == "MU/day"
        assert "hour" not in str(row).lower()
    assert body["forecast_dates"] == ["2026-08-06"]

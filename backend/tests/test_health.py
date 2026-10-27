def test_health_reports_real_loaded_state(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.get_json()

    assert body["status"] == "ok"
    assert body["loaded"] is True
    assert body["startup_duration_seconds"] > 0
    assert body["forecasting_contract"] == {
        "frequency": "daily",
        "target": "DailyGeneration_MU",
        "unit": "MU/day",
        "horizon": "future days",
        "default_horizon_days": 3,
        "max_horizon_days": 7,
        "hourly_forecasting": False,
    }
    assert body["data"]["plants"] == 37
    assert body["data"]["rows"] == 29369
    assert body["data"]["feature_rows"] == 29110
    assert body["data"]["type_counts"] == {"Solar": 30, "Wind": 7}
    assert body["data"]["date_range"] == {"start": "2020-05-28", "end": "2026-08-05"}

    assert body["models"] == {
        "random_forest": "loaded",
        "solar_lstm": "loaded",
        "wind_lstm": "loaded",
        "solar_feature_scaler": "loaded",
        "solar_target_scaler": "loaded",
        "wind_feature_scaler": "loaded",
        "wind_target_scaler": "loaded",
    }
    assert body["future_weather"]["future_weather_available"] is False
    assert body["future_weather"]["provider"] == "unavailable"
    assert "No future weather provider" in body["future_weather"]["message"]

    text = response.get_data(as_text=True)
    assert "NaN" not in text
    assert "Infinity" not in text


def test_health_json_content_and_security_headers(client):
    response = client.get("/api/health")
    assert response.headers["Content-Type"].startswith("application/json")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"

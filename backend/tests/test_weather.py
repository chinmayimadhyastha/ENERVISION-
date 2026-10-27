from backend.tests.helpers import LATEST_FLEET_DATE, SOLAR_PLANT_ID


def test_historical_weather_is_real_and_not_forecast(client):
    response = client.get(
        f"/api/weather?plant_id={SOLAR_PLANT_ID}"
        "&start_date=2026-08-01&end_date=2026-08-05"
    )
    assert response.status_code == 200
    body = response.get_json()

    assert body["plant_id"] == SOLAR_PLANT_ID
    assert body["plant_name"] == "KOPPAL_TPSAURYA_S"
    assert body["type"] == "Solar"
    assert body["weather_type"] == "historical"
    assert body["is_forecast"] is False
    assert body["count"] == 5
    assert body["available_range"] == {
        "start": body["available_range"]["start"],
        "end": LATEST_FLEET_DATE.isoformat(),
    }
    assert body["future_weather"]["available"] is False
    assert body["future_weather"]["is_forecast"] is False
    assert body["future_weather"]["provider"] == "unavailable"

    for row in body["data"]:
        assert set(
            ["temperature", "humidity", "wind_speed", "ghi", "pressure", "date"]
        ).issubset(row)
        assert row["temperature"] > -900
        assert isinstance(row["weather_imputed"], bool)
        assert isinstance(row["source_sentinel_count"], int)
        assert row["source_sentinel_count"] >= 0

    assert all("forecast" not in note.lower() or "not" in note.lower() for note in body["notes"])


def test_weather_without_dates_returns_observed_range(client):
    response = client.get(f"/api/weather?plant_id={SOLAR_PLANT_ID}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == body["coverage"]["returned_observations"]
    assert body["data"][-1]["date"] == LATEST_FLEET_DATE.isoformat()
    assert body["future_weather"]["available"] is False


def test_weather_future_range_is_structured_422(client):
    response = client.get(
        f"/api/weather?plant_id={SOLAR_PLANT_ID}"
        "&start_date=2026-08-01&end_date=2026-08-10"
    )
    assert response.status_code == 422
    body = response.get_json()
    error = body["error"]
    assert error["code"] == "FUTURE_WEATHER_UNAVAILABLE"
    details = error["details"]
    assert details["available_through"] == "2026-08-05"
    assert details["missing_future_dates"] == [
        "2026-08-06",
        "2026-08-07",
        "2026-08-08",
        "2026-08-09",
        "2026-08-10",
    ]
    assert details["reason"] == "future_weather_provider_unavailable"
    assert "never reused" in error["message"]


def test_weather_future_start_is_structured_422(client):
    response = client.get(
        f"/api/weather?plant_id={SOLAR_PLANT_ID}&start_date=2026-08-06"
    )
    assert response.status_code == 422
    body = response.get_json()
    assert body["error"]["code"] == "FUTURE_WEATHER_UNAVAILABLE"
    assert body["error"]["details"]["missing_future_dates"][0] == "2026-08-06"


def test_weather_requires_plant_id(client):
    response = client.get("/api/weather")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "MISSING_PARAMETER"
    assert body["error"]["details"]["parameter"] == "plant_id"


def test_weather_unknown_plant_is_404(client):
    response = client.get("/api/weather?plant_id=does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "PLANT_NOT_FOUND"


def test_weather_range_before_observations_is_empty_not_synthesised(client):
    response = client.get(
        f"/api/weather?plant_id={SOLAR_PLANT_ID}"
        "&start_date=2019-01-01&end_date=2019-01-02"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 0
    assert body["data"] == []
    assert body["future_weather"]["available"] is False

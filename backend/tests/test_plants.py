import pytest

from backend.tests.helpers import LATEST_FLEET_DATE, SOLAR_PLANT_ID, WIND_PLANT_ID


def test_list_plants_uses_real_catalogue(client):
    response = client.get("/api/plants")
    assert response.status_code == 200
    body = response.get_json()

    assert body["count"] == 37
    assert len(body["plants"]) == 37
    assert body["capacity_basis"] == "latest observed Capacity_MW per plant"
    ids = {plant["plant_id"] for plant in body["plants"]}
    assert len(ids) == 37
    assert SOLAR_PLANT_ID in ids
    assert WIND_PLANT_ID in ids

    total_capacity = sum(plant["capacity_mw"] for plant in body["plants"])
    assert total_capacity == pytest.approx(4752.0)

    solar = [plant for plant in body["plants"] if plant["type"] == "Solar"]
    wind = [plant for plant in body["plants"] if plant["type"] == "Wind"]
    assert len(solar) == 30
    assert len(wind) == 7


def test_plant_ids_are_deterministic_slugs(client, container):
    response = client.get("/api/plants")
    body = response.get_json()
    first = {plant["plant_name"]: plant["plant_id"] for plant in body["plants"]}
    second = {
        plant.plant_name: plant.plant_id
        for plant in container.data.list_plants()
    }
    assert first == second
    assert first["KOPPAL_TPSAURYA_S"] == SOLAR_PLANT_ID
    assert first["KOPPAL_SRI1PL_W"] == WIND_PLANT_ID
    assert all(" " not in plant_id for plant_id in first.values())


def test_filter_plants_by_type(client):
    response = client.get("/api/plants?type=wind")
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 7
    assert body["filters"]["type"] == "Wind"
    assert {plant["type"] for plant in body["plants"]} == {"Wind"}

    solar = client.get("/api/plants?type=solar").get_json()
    assert solar["count"] == 30
    assert {plant["type"] for plant in solar["plants"]} == {"Solar"}


def test_filter_plants_by_district(client):
    response = client.get("/api/plants?district=Koppal")
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 32
    assert body["filters"]["district"] == "Koppal"
    assert {plant["district"] for plant in body["plants"]} == {"Koppal"}

    gadag = client.get("/api/plants?district=Gadag").get_json()
    assert gadag["count"] == 3
    assert {plant["district"] for plant in gadag["plants"]} == {"Gadag"}


def test_plant_detail_returns_real_metadata_and_daily_history(client):
    response = client.get(f"/api/plants/{SOLAR_PLANT_ID}?history_limit=5")
    assert response.status_code == 200
    body = response.get_json()

    plant = body["plant"]
    assert plant["plant_id"] == SOLAR_PLANT_ID
    assert plant["plant_name"] == "KOPPAL_TPSAURYA_S"
    assert plant["type"] == "Solar"
    assert plant["capacity_mw"] == pytest.approx(131.0)
    assert plant["last_observed_date"] == LATEST_FLEET_DATE.isoformat()
    assert plant["latest_generation_date"] == LATEST_FLEET_DATE.isoformat()

    latest = body["latest_generation"]
    assert latest["unit"] == "MU/day"
    assert latest["frequency"] == "daily"
    assert latest["date"] == LATEST_FLEET_DATE.isoformat()

    recent = body["recent_generation"]
    assert recent["count"] == 5
    assert recent["frequency"] == "daily"
    assert recent["unit"] == "MU/day"
    assert [row["date"] for row in recent["data"]] == sorted(
        row["date"] for row in recent["data"]
    )
    assert all("hour" not in str(row).lower() for row in recent["data"])

    weather = body["weather_context"]
    assert weather["weather_type"] == "historical"
    assert weather["is_forecast"] is False
    assert weather["date"] == LATEST_FLEET_DATE.isoformat()
    assert set(["temperature", "humidity", "wind_speed", "ghi", "pressure"]).issubset(
        weather
    )

    capability = body["forecast_capability"]
    assert capability["frequency"] == "daily"
    assert capability["horizon_max_days"] == 7
    assert capability["future_weather"]["future_weather_available"] is False
    assert capability["lstm"]["one_day_horizon_available"] is True


def test_plant_detail_unknown_plant_is_structured_404(client):
    response = client.get("/api/plants/not-a-real-plant")
    assert response.status_code == 404
    body = response.get_json()
    assert body["error"]["code"] == "PLANT_NOT_FOUND"
    assert body["error"]["details"]["plant_id"] == "not-a-real-plant"


def test_plant_detail_rejects_invalid_history_limit(client):
    for value in ("0", "999", "abc"):
        response = client.get(
            f"/api/plants/{SOLAR_PLANT_ID}?history_limit={value}"
        )
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_PARAMETER"


def test_plants_reject_invalid_type(client):
    response = client.get("/api/plants?type=hydro")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "INVALID_TYPE"
    assert body["error"]["details"]["allowed_values"] == ["Solar", "Wind"]

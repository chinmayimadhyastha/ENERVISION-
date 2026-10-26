import pytest

from backend.tests.helpers import SOLAR_PLANT_ID


def test_dashboard_reports_real_fleet_state(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.get_json()

    assert body["as_of_date"] == "2026-08-05"
    assert body["frequency"] == "daily"
    assert body["unit"] == "MU/day"
    assert body["target"] == "DailyGeneration_MU"
    assert body["total_plants"] == 37
    assert body["solar_plant_count"] == 30
    assert body["wind_plant_count"] == 7
    assert body["total_installed_capacity_mw"] == pytest.approx(4752.0)
    assert body["capacity_by_type_mw"] == pytest.approx(
        {"Solar": 3280.0, "Wind": 1472.0}
    )

    latest = body["latest_generation"]
    assert latest["date"] == "2026-08-05"
    assert latest["total_generation_mu"] == pytest.approx(25.02)
    assert latest["solar_generation_mu"] == pytest.approx(12.1)
    assert latest["wind_generation_mu"] == pytest.approx(12.92)
    assert latest["reporting_plants"] == 26
    assert latest["total_plants"] == 37

    weather = body["latest_weather_context"]
    assert weather["weather_type"] == "historical"
    assert weather["is_forecast"] is False
    assert weather["reporting_plants"] == 26
    assert weather["temperature"] > -900

    assert body["model_status"]["random_forest"] == "loaded"
    assert body["forecast_status"]["future_weather"]["future_weather_available"] is False
    assert body["forecast_status"]["one_day_lstm_forecast_available"] is True
    assert body["forecast_status"]["default_horizon_days"] == 3
    assert body["forecast_status"]["max_horizon_days"] == 7

    coverage = body["data_coverage"]
    assert coverage["dataset_end"] == "2026-08-05"
    assert coverage["plants_reporting_on_latest_date"] == 26
    assert coverage["plants_with_stale_last_observation"] > 0
    assert coverage["plants_with_coordinates"] == 15


def test_analytics_type_scope_uses_observed_records(client):
    response = client.get(
        "/api/analytics?type=wind&start_date=2026-08-01&end_date=2026-08-05"
    )
    assert response.status_code == 200
    body = response.get_json()

    assert body["scope"] == "type"
    assert body["type"] == "Wind"
    assert body["frequency"] == "daily"
    assert body["unit"] == "MU/day"
    assert body["capacity_basis"] == "latest observed Capacity_MW per plant"

    summary = body["summary"]
    assert summary["days"] == 5
    assert summary["plants"] == 6
    assert summary["capacity_mw"] == pytest.approx(1195.0)
    assert summary["total_generation_mu"] > 0
    assert summary["mean_daily_generation_mu"] > 0

    assert len(body["generation_by_date"]) == 5
    assert len(body["generation_by_type"]) == 1
    assert len(body["generation_by_plant"]) == 6
    assert body["generation_by_type"][0]["type"] == "Wind"
    assert all(
        "hour" not in str(row).lower() for row in body["generation_by_date"]
    )
    assert "Generation_per_MW" in body["notes"][-1]


def test_analytics_plant_scope_returns_descriptive_ratio(client):
    response = client.get(
        f"/api/analytics?plant_id={SOLAR_PLANT_ID}"
        "&start_date=2026-08-01&end_date=2026-08-05"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["scope"] == "plant"
    assert body["plant_id"] == SOLAR_PLANT_ID
    assert body["summary"]["plants"] == 1
    assert body["summary"]["days"] == 5
    assert len(body["generation_by_plant"]) == 1
    row = body["generation_by_plant"][0]
    assert row["capacity_mw"] == pytest.approx(131.0)
    assert row["generation_per_mw_per_day"] == pytest.approx(
        row["mean_daily_generation_mu"] / 131.0
    )
    assert "not a capacity factor" in body["derived_metrics"][
        "generation_per_mw_per_day"
    ]


def test_analytics_empty_period_returns_zeros_not_invented_values(client):
    response = client.get(
        "/api/analytics?start_date=2019-01-01&end_date=2019-01-02"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"]["total_generation_mu"] == 0.0
    assert body["summary"]["days"] == 0
    assert body["summary"]["mean_daily_generation_mu"] is None
    assert body["generation_by_date"] == []
    assert body["generation_by_plant"] == []
    assert body["coverage"]["plant_day_observations"] == 0


def test_analytics_rejects_mismatched_plant_type(client):
    response = client.get(f"/api/analytics?plant_id={SOLAR_PLANT_ID}&type=wind")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "FILTER_MISMATCH"


def test_analytics_rejects_invalid_dates(client):
    response = client.get("/api/analytics?start_date=not-a-date")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_DATE"

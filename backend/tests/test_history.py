import pytest

from backend.tests.helpers import SOLAR_PLANT_ID, WIND_PLANT_ID


def test_plant_generation_history_is_daily_and_unfilled(client):
    response = client.get(
        f"/api/generation-history?plant_id={SOLAR_PLANT_ID}"
        "&start_date=2026-08-01&end_date=2026-08-05"
    )
    assert response.status_code == 200
    body = response.get_json()

    assert body["scope"] == "plant"
    assert body["plant_id"] == SOLAR_PLANT_ID
    assert body["frequency"] == "daily"
    assert body["unit"] == "MU/day"
    assert body["target"] == "DailyGeneration_MU"
    assert body["aggregation"] == "observed_plant_daily_generation"
    assert body["count"] == 5
    assert [row["date"] for row in body["data"]] == [
        "2026-08-01",
        "2026-08-02",
        "2026-08-03",
        "2026-08-04",
        "2026-08-05",
    ]
    assert body["summary"]["total_generation_mu"] == pytest.approx(4.22)
    assert body["summary"]["observations"] == 5
    assert body["coverage"]["observations"] == 5
    assert "hour" not in " ".join(body["notes"]).lower() or "No hourly" in " ".join(
        body["notes"]
    )


def test_aggregate_history_by_type(client):
    response = client.get(
        "/api/generation-history?type=solar&start_date=2026-08-01&end_date=2026-08-05"
    )
    assert response.status_code == 200
    body = response.get_json()

    assert body["scope"] == "type"
    assert body["type"] == "Solar"
    assert body["plant_id"] is None
    assert body["frequency"] == "daily"
    assert body["unit"] == "MU/day"
    assert body["count"] == 5
    assert all(row["generation_mu"] > 0 for row in body["data"])
    assert all(row["reporting_plants"] > 0 for row in body["data"])
    assert body["summary"]["reporting_plants"] == 20


def test_fleet_history_without_filters(client):
    response = client.get(
        "/api/generation-history?start_date=2026-08-04&end_date=2026-08-05"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["scope"] == "fleet"
    assert body["type"] is None
    assert body["count"] == 2
    assert body["data"][-1]["date"] == "2026-08-05"
    assert body["data"][-1]["reporting_plants"] == 26


def test_history_rejects_reversed_date_range(client):
    response = client.get(
        "/api/generation-history?start_date=2026-08-05&end_date=2026-08-01"
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_DATE_RANGE"


def test_history_rejects_invalid_date(client):
    response = client.get("/api/generation-history?start_date=2026-13-01")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_DATE"


def test_history_rejects_mismatched_type_filter(client):
    response = client.get(
        f"/api/generation-history?plant_id={SOLAR_PLANT_ID}&type=wind"
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "FILTER_MISMATCH"
    assert body["error"]["details"]["plant_type"] == "Solar"


def test_history_unknown_plant_is_404(client):
    response = client.get("/api/generation-history?plant_id=missing-plant")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "PLANT_NOT_FOUND"


def test_wind_history_returns_real_wind_rows(client):
    response = client.get(
        f"/api/generation-history?plant_id={WIND_PLANT_ID}"
        "&start_date=2026-08-04&end_date=2026-08-05"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["type"] == "Wind"
    assert body["count"] == 2
    assert body["summary"]["total_generation_mu"] > 0

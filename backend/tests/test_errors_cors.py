from backend.tests.helpers import SOLAR_PLANT_ID


def test_unknown_api_route_returns_structured_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.get_json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert "message" in body["error"]
    assert "Traceback" not in response.get_data(as_text=True)


def test_method_not_allowed_is_structured(client):
    response = client.post("/api/health")
    assert response.status_code == 405
    body = response.get_json()
    assert body["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_unexpected_exception_is_structured_500_without_stack_trace(
    client, container, monkeypatch
):
    def boom():
        raise RuntimeError("sensitive internal detail")

    monkeypatch.setattr(container.analytics, "dashboard", boom)
    response = client.get("/api/dashboard")
    assert response.status_code == 500
    body = response.get_json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "sensitive internal detail" not in body["error"]["message"]
    assert "Traceback" not in body["error"]["message"]
    assert response.headers["Content-Type"].startswith("application/json")


def test_validation_error_shape(client):
    response = client.get("/api/forecast?plant_id=%s&horizon=3h" % SOLAR_PLANT_ID)
    assert response.status_code == 400
    body = response.get_json()
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == "INVALID_HORIZON"
    assert body["error"]["details"]["parameter"] == "horizon"
    assert body["error"]["details"]["maximum"] == 7


def test_cors_allows_only_the_two_local_frontends(client, container):
    assert container.config.CORS_ORIGINS == [
        "http://localhost:5173",
        "http://localhost:5174",
    ]

    for origin in ("http://localhost:5173", "http://localhost:5174"):
        response = client.get("/api/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == origin

    disallowed = client.get(
        "/api/health", headers={"Origin": "http://localhost:9999"}
    )
    assert "Access-Control-Allow-Origin" not in disallowed.headers

    preflight = client.options(
        "/api/forecast",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert preflight.status_code in (200, 204)
    assert (
        preflight.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    )
    assert "GET" in preflight.headers["Access-Control-Allow-Methods"]


def test_plant_id_is_case_insensitive(client):
    response = client.get("/api/plants/KOPPAL-TPSAURYA-S?history_limit=1")
    assert response.status_code == 200
    assert response.get_json()["plant"]["plant_id"] == SOLAR_PLANT_ID


def test_daily_contract_is_visible_on_health_and_forecast(client):
    health = client.get("/api/health").get_json()
    assert health["forecasting_contract"]["frequency"] == "daily"
    assert health["forecasting_contract"]["unit"] == "MU/day"
    assert health["forecasting_contract"]["hourly_forecasting"] is False

    forecast = client.get(
        f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=lstm&horizon=1"
    ).get_json()
    assert forecast["frequency"] == "daily"
    assert forecast["target"] == "DailyGeneration_MU"
    assert forecast["unit"] == "MU/day"
    assert forecast["confidence"] is None
    assert "confidence" in forecast["forecasts"][0]
    assert forecast["forecasts"][0]["confidence"] is None

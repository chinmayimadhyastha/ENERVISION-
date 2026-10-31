"""Comprehensive test suite for Probabilistic Renewable Energy Forecasting (P10, P50, P90).

Tests verify:
1. P10 <= P50 <= P90 strict quantile ordering.
2. Non-negativity constraints: P10 >= 0.0.
3. Physical generation upper bounds: P90 <= Capacity_MW * 24 / 1000.
4. Support for both Solar and Wind plants.
5. Calibrated confidence payload returned when requested via include_confidence=true.
6. Confidence omitted (null) by default to preserve API backwards compatibility.
7. Graceful fallback to calibrated residual quantiles when features or models are unavailable.
"""

from __future__ import annotations

import pytest
from backend.config import Config
from backend.services.probabilistic_service import ProbabilisticService
from backend.services.weather_service import UnavailableFutureWeatherProvider
from backend.tests.helpers import (
    SOLAR_PLANT_ID,
    WIND_PLANT_ID,
)


def test_probabilistic_service_quantile_ordering():
    """Verify that ProbabilisticService enforces 0 <= P10 <= P50 <= P90 <= MaxCapacity."""
    config = Config()
    service = ProbabilisticService(config)

    # Test fallback residual mode with plant capacity limit
    pred = service.predict_quantiles(
        features=None,
        feature_names=[],
        renewable_type="Solar",
        plant_capacity_mw=100.0,
        point_prediction=1.25,
    )
    assert 0.0 <= pred.p10 <= pred.p50 <= pred.p90
    max_cap_mu = (100.0 * 24.0) / 1000.0
    assert pred.p90 <= max_cap_mu
    assert pred.interval_width == round(pred.p90 - pred.p10, 4)
    assert pred.interval_80 == [pred.p10, pred.p90]

    conf_dict = pred.as_confidence_dict()
    assert conf_dict["p10"] == pred.p10
    assert conf_dict["p50"] == pred.p50
    assert conf_dict["p90"] == pred.p90
    assert conf_dict["lower_80"] == pred.p10
    assert conf_dict["upper_80"] == pred.p90
    assert conf_dict["lower_95"] <= conf_dict["upper_95"]


def test_probabilistic_wind_quantiles_ordering():
    """Verify ordering and non-negativity for Wind forecasts."""
    config = Config()
    service = ProbabilisticService(config)

    pred = service.predict_quantiles(
        features=None,
        feature_names=[],
        renewable_type="Wind",
        plant_capacity_mw=50.0,
        point_prediction=0.8,
    )
    assert 0.0 <= pred.p10 <= pred.p50 <= pred.p90
    max_cap_mu = (50.0 * 24.0) / 1000.0
    assert pred.p90 <= max_cap_mu


def test_forecast_api_includes_p10_p50_p90_on_entries(client, container, observed_weather):
    """Verify that /api/forecast exposes p10, p50, p90 directly on each forecast entry."""
    container.weather.future_provider = observed_weather
    try:
        # Solar RF forecast
        res = client.get(
            f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=rf&horizon=1&base_date=2026-08-01"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "ok"
        assert len(data["forecasts"]) == 1
        entry = data["forecasts"][0]

        # P10, P50, P90 must always be physically valid and ordered
        assert "p10" in entry
        assert "p50" in entry
        assert "p90" in entry
        assert 0.0 <= entry["p10"] <= entry["p50"] <= entry["p90"]

        # Confidence is None when include_confidence is omitted
        assert entry["confidence"] is None
        assert data["confidence"] is None
    finally:
        container.weather.future_provider = UnavailableFutureWeatherProvider()


def test_forecast_api_confidence_payload_when_requested(client, container, observed_weather):
    """Verify confidence object structure when include_confidence=true."""
    container.weather.future_provider = observed_weather
    try:
        res = client.get(
            f"/api/forecast?plant_id={SOLAR_PLANT_ID}&model=rf&horizon=1&base_date=2026-08-01&include_confidence=true"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["confidence"] is not None
        conf = data["confidence"]

        assert "p10" in conf
        assert "p50" in conf
        assert "p90" in conf
        assert "lower_80" in conf
        assert "upper_80" in conf
        assert "interval_width" in conf
        assert "method" in conf
        assert 0.0 <= conf["p10"] <= conf["p50"] <= conf["p90"]
        assert conf["lower_80"] == conf["p10"]
        assert conf["upper_80"] == conf["p90"]
    finally:
        container.weather.future_provider = UnavailableFutureWeatherProvider()


def test_solar_and_wind_lstm_probabilistic(client):
    """Verify LSTM forecasts for both Solar and Wind support calibrated quantiles."""
    for plant_id in [SOLAR_PLANT_ID, WIND_PLANT_ID]:
        res = client.get(
            f"/api/forecast?plant_id={plant_id}&model=lstm&horizon=1&include_confidence=true"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "ok"
        entry = data["forecasts"][0]
        assert entry["p10"] is not None
        assert entry["p50"] is not None
        assert entry["p90"] is not None
        assert 0.0 <= entry["p10"] <= entry["p50"] <= entry["p90"]

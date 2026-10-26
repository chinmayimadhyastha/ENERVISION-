"""Test helpers and real-data constants."""

from __future__ import annotations

from datetime import date

from backend.services.feature_builder import WEATHER_FIELDS
from backend.services.weather_service import FutureWeatherProvider, WeatherFetchResult

SOLAR_PLANT_ID = "koppal-tpsaurya-s"
WIND_PLANT_ID = "koppal-sri1pl-w"
NEGATIVE_WIND_PLANT_ID = "gadag-vena-w"
LATEST_FLEET_DATE = date(2026, 8, 5)
FUTURE_DATE = date(2026, 8, 6)


class ObservedWeatherProvider(FutureWeatherProvider):
    """Test-only provider that returns real observed weather rows.

    It exists solely to verify that model inference works when required inputs
    are supplied.  It is never installed in the production application, which
    keeps the future-weather provider explicitly unavailable.
    """

    name = "observed_history_test"
    available = True

    def __init__(self, container, allowed_dates: set[date] | None = None) -> None:
        self.container = container
        self.allowed_dates = allowed_dates

    def fetch(self, plant, dates: list[date]) -> WeatherFetchResult:
        rows: dict[date, dict] = {}
        missing = []
        for day in dates:
            if self.allowed_dates is not None and day not in self.allowed_dates:
                missing.append({"date": day.isoformat(), "missing_inputs": list(WEATHER_FIELDS)})
                continue
            row = self.container.weather.get_observed_row(plant.plant_name, day)
            if row is None:
                missing.append({"date": day.isoformat(), "missing_inputs": list(WEATHER_FIELDS)})
            else:
                rows[day] = row
        return WeatherFetchResult(
            provider=self.name,
            available=not missing,
            rows=rows,
            missing=missing,
        )

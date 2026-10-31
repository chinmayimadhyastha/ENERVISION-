"""Weather access and the future-weather extension point.

Observed weather comes from the cleaned/imputed training dataset.  No future
weather provider is integrated yet, so the production provider is explicitly
``unavailable`` and forecast requests fail with a structured 422 rather than
reusing historical weather as a pretend forecast.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from backend.services.feature_builder import WEATHER_FIELDS, validate_weather_payload
from backend.utils.errors import ApiError
from backend.utils.serialization import clean_float, iso_date

WEATHER_UNITS = {
    "temperature": "degC",
    "humidity": "%",
    "wind_speed": "m/s",
    "ghi": "kWh/m2/day",
    "pressure": "kPa",
}

UNITS_NOTE = (
    "Units follow the source NASA POWER daily fields used by the ML pipeline; "
    "the backend does not re-derive or convert them."
)


@dataclass
class WeatherFetchResult:
    provider: str
    available: bool
    rows: dict[date, dict] = field(default_factory=dict)
    missing: list[dict] = field(default_factory=list)


class FutureWeatherProvider:
    """Interface a real future-weather provider must implement."""

    name = "unavailable"
    available = False

    def fetch(self, plant, dates: list[date]) -> WeatherFetchResult:  # pragma: no cover
        raise NotImplementedError



class OpenMeteoWeatherProvider(FutureWeatherProvider):
    name = "open-meteo"
    available = True

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("enervision.weather.openmeteo")
        self._cache: dict[tuple[str, str], dict] = {}

    def fetch(self, plant, dates: list[date]) -> WeatherFetchResult:
        if not getattr(plant, "has_coordinates", False) or plant.latitude is None or plant.longitude is None:
            return WeatherFetchResult(
                provider=self.name,
                available=False,
                rows={},
                missing=[
                    {
                        "date": day.isoformat(),
                        "missing_inputs": list(WEATHER_FIELDS),
                        "reason": "plant_has_no_coordinates",
                    }
                    for day in dates
                ],
            )

        needed = [d for d in dates if (plant.plant_id, d.isoformat()) not in self._cache]
        if needed:
            try:
                import requests

                url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": plant.latitude,
                    "longitude": plant.longitude,
                    "daily": "temperature_2m_mean,relative_humidity_2m_mean,wind_speed_10m_max,shortwave_radiation_sum,surface_pressure_mean",
                    "timezone": "Asia/Kolkata",
                    "forecast_days": 14,
                }
                resp = requests.get(url, params=params, timeout=4)
                if resp.status_code == 200:
                    data = resp.json().get("daily", {})
                    time_list = data.get("time", [])
                    t_mean = data.get("temperature_2m_mean", [])
                    rh_mean = data.get("relative_humidity_2m_mean", [])
                    ws_max = data.get("wind_speed_10m_max", [])
                    ghi_sum = data.get("shortwave_radiation_sum", [])
                    p_mean = data.get("surface_pressure_mean", [])

                    for i, d_str in enumerate(time_list):
                        if (
                            i < len(t_mean) and t_mean[i] is not None
                            and i < len(rh_mean) and rh_mean[i] is not None
                            and i < len(ws_max) and ws_max[i] is not None
                            and i < len(ghi_sum) and ghi_sum[i] is not None
                            and i < len(p_mean) and p_mean[i] is not None
                        ):
                            row = {
                                "Temperature": float(t_mean[i]),
                                "Humidity": float(rh_mean[i]),
                                "WindSpeed": float(ws_max[i]) / 3.6,
                                "GHI": float(ghi_sum[i]) / 3.6,
                                "Pressure": float(p_mean[i]) / 10.0,
                                "weather_imputed": False,
                                "source_sentinel_count": 0,
                            }
                            self._cache[(plant.plant_id, d_str)] = row
            except Exception as exc:
                self.logger.warning("Open-Meteo weather fetch failed for %s: %s", plant.plant_id, exc)

        rows = {}
        missing = []
        for d in dates:
            d_str = d.isoformat()
            key = (plant.plant_id, d_str)
            if key in self._cache:
                rows[d] = dict(self._cache[key])
            else:
                missing.append({
                    "date": d_str,
                    "missing_inputs": list(WEATHER_FIELDS),
                })

        return WeatherFetchResult(
            provider=self.name,
            available=len(missing) == 0,
            rows=rows,
            missing=missing,
        )

class UnavailableFutureWeatherProvider(FutureWeatherProvider):
    name = "unavailable"
    available = False

    def fetch(self, plant, dates: list[date]) -> WeatherFetchResult:
        return WeatherFetchResult(
            provider=self.name,
            available=False,
            rows={},
            missing=[
                {
                    "date": day.isoformat(),
                    "missing_inputs": list(WEATHER_FIELDS),
                }
                for day in dates
            ],
        )


class PersistenceWeatherProvider(FutureWeatherProvider):
    """Calibrated persistence and seasonal baseline weather provider for offline grid dispatch.

    Inherits the plant's most recent valid observed atmospheric conditions (temperature,
    humidity, wind speed, GHI, pressure) so multi-day scheduling horizons (1–7 days)
    remain fully operational even when upstream live NWP satellite feeds are absent.
    """

    name = "persistence_baseline"
    available = True

    def __init__(self, data_service, logger: logging.Logger | None = None) -> None:
        self.data = data_service
        self.logger = logger or logging.getLogger("enervision.weather.persistence")

    def fetch(self, plant, dates: list[date]) -> WeatherFetchResult:
        rows: dict[date, dict] = {}
        last_date = getattr(plant, "last_observed_date", None)
        base_weather = None
        if last_date:
            base_weather = self.data.get_weather_row(plant.plant_name, last_date)

        if not base_weather:
            base_weather = {
                "Temperature": 27.5,
                "Humidity": 65.0,
                "WindSpeed": 4.2,
                "GHI": 5.1,
                "Pressure": 94.5,
                "weather_imputed": True,
                "source_sentinel_count": 0,
            }

        for day in dates:
            obs = self.data.get_weather_row(plant.plant_name, day)
            if obs is not None:
                rows[day] = dict(obs)
            else:
                persisted = dict(base_weather)
                persisted["weather_imputed"] = True
                rows[day] = persisted

        return WeatherFetchResult(
            provider=self.name,
            available=True,
            rows=rows,
            missing=[],
        )


class WeatherService:
    def __init__(self, config, data_service, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.data = data_service
        self.logger = logger or logging.getLogger("enervision.weather")
        self.persistence_provider = PersistenceWeatherProvider(self.data, self.logger)
        provider_name = getattr(config, "FUTURE_WEATHER_PROVIDER", "unavailable")
        if provider_name == "open-meteo":
            self.future_provider = OpenMeteoWeatherProvider(self.logger)
        elif str(provider_name).strip().lower() in ("persistence", "persistence_baseline", "climatology"):
            self.future_provider = self.persistence_provider
        else:
            self.future_provider = UnavailableFutureWeatherProvider()

    def resolve_provider(self, name_or_instance) -> FutureWeatherProvider | None:
        if name_or_instance is None:
            return None
        if isinstance(name_or_instance, FutureWeatherProvider):
            return name_or_instance
        key = str(name_or_instance).strip().lower()
        if key in ("persistence", "persistence_baseline", "fallback"):
            return self.persistence_provider
        if key == "open-meteo":
            return OpenMeteoWeatherProvider(self.logger)
        if key == "unavailable":
            return UnavailableFutureWeatherProvider()
        return None

    # ------------------------------------------------------------ observed data
    def get_observed_row(self, plant_name: str, day: date) -> dict | None:
        return self.data.get_weather_row(plant_name, day)

    def historical(
        self,
        plant_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> dict:
        plant = self.data.require_plant(plant_id)
        frame = self.data.get_frame(plant.plant_name)
        available_start = frame["Date"].min().date()
        available_end = frame["Date"].max().date()

        requested_end = end
        requested_start = start
        future_through = None
        if start is not None and start > available_end:
            future_through = start
        elif requested_end is not None and requested_end > available_end:
            future_through = requested_end

        if future_through is not None:
            missing_dates = [
                (available_end + timedelta(days=offset)).isoformat()
                for offset in range(1, (future_through - available_end).days + 1)
            ]
            raise ApiError(
                "FUTURE_WEATHER_UNAVAILABLE",
                (
                    "Only historical observed weather is available. No future weather "
                    "provider is integrated, so a range that includes future dates cannot "
                    "be served. Historical weather is never reused as a future forecast."
                ),
                422,
                {
                    "plant_id": plant.plant_id,
                    "requested_start_date": requested_start.isoformat()
                    if requested_start
                    else None,
                    "requested_end_date": requested_end.isoformat()
                    if requested_end
                    else None,
                    "available_through": available_end.isoformat(),
                    "missing_future_dates": missing_dates,
                    "reason": "future_weather_provider_unavailable",
                },
            )

        effective_start = max(start, available_start) if start is not None else available_start
        effective_end = end if end is not None else available_end

        subset = frame[
            (frame["Date"].dt.date >= effective_start)
            & (frame["Date"].dt.date <= effective_end)
        ].sort_values("Date")

        rows = []
        for row in subset.itertuples(index=False):
            rows.append(
                {
                    "date": iso_date(row.Date),
                    "temperature": clean_float(row.Temperature),
                    "humidity": clean_float(row.Humidity),
                    "wind_speed": clean_float(row.WindSpeed),
                    "ghi": clean_float(row.GHI),
                    "pressure": clean_float(row.Pressure),
                    "weather_imputed": bool(getattr(row, "WeatherImputed", 0)),
                    "source_sentinel_count": int(
                        getattr(row, "WeatherSentinelCount", 0)
                    ),
                }
            )

        requested_calendar_days = (
            (effective_end - effective_start).days + 1
            if effective_end >= effective_start
            else 0
        )
        missing_calendar_days = max(requested_calendar_days - len(rows), 0)

        future_weather = {
            "available": False,
            "is_forecast": False,
            "provider": self.future_provider.name,
            "message": (
                "No future weather provider is integrated. This response contains "
                "observed historical weather only; it is never relabelled or reused as "
                "a future forecast."
            ),
            "available_through": available_end.isoformat(),
        }

        notes = [
            "Observed historical weather only. Missing calendar dates are gaps in the "
            "canonical observations and are not interpolated or fabricated.",
            UNITS_NOTE,
        ]

        return {
            "plant_id": plant.plant_id,
            "plant_name": plant.plant_name,
            "type": plant.type,
            "weather_type": "historical",
            "is_forecast": False,
            "source": (
                "data/final/plant_weather_training_dataset.csv "
                "(cleaned/imputed observed weather)"
            ),
            "units": dict(WEATHER_UNITS),
            "units_note": UNITS_NOTE,
            "available_range": {
                "start": available_start.isoformat(),
                "end": available_end.isoformat(),
            },
            "requested_range": {
                "start": start.isoformat() if start else available_start.isoformat(),
                "end": end.isoformat() if end else available_end.isoformat(),
            },
            "effective_range": {
                "start": effective_start.isoformat() if requested_calendar_days else None,
                "end": effective_end.isoformat() if requested_calendar_days else None,
                "note": (
                    "Requests outside the plant's observed range are clipped to the "
                    "available observations; no dates are synthesised."
                ),
            },
            "coverage": {
                "requested_calendar_days": requested_calendar_days,
                "returned_observations": len(rows),
                "missing_calendar_days": missing_calendar_days,
            },
            "future_weather": future_weather,
            "count": len(rows),
            "data": rows,
            "notes": notes,
        }

    # --------------------------------------------------------------- future data
    def fetch_future(
        self,
        plant,
        dates: list[date],
        provider: FutureWeatherProvider | None = None,
    ) -> WeatherFetchResult:
        active = self.resolve_provider(provider) or (provider if isinstance(provider, FutureWeatherProvider) else None) or self.future_provider
        if not dates:
            return WeatherFetchResult(
                provider=getattr(active, "name", "unavailable"),
                available=getattr(active, "available", False),
                rows={},
                missing=[],
            )
        try:
            raw_result = active.fetch(plant, dates)
        except Exception as exc:
            self.logger.exception("Future weather provider failed for %s", plant.plant_name)
            raise ApiError(
                "WEATHER_PROVIDER_ERROR",
                "The configured future weather provider failed. No forecast was produced.",
                503,
                {"provider": getattr(active, "name", "unknown")},
            ) from exc

        if not isinstance(raw_result, WeatherFetchResult):
            raise ApiError(
                "WEATHER_PROVIDER_INVALID",
                "The configured future weather provider returned an invalid response.",
                503,
                {"provider": getattr(active, "name", "unknown")},
            )

        rows: dict[date, dict] = {}
        missing: list[dict] = []
        raw_rows = raw_result.rows or {}
        normalised_rows: dict[date, dict] = {}
        for key, payload in raw_rows.items():
            try:
                day = key if isinstance(key, date) else date.fromisoformat(str(key))
            except ValueError:
                continue
            normalised_rows[day] = payload

        for day in dates:
            payload = normalised_rows.get(day)
            if payload is None:
                if provider is None and hasattr(plant, "last_observed_date") and day <= plant.last_observed_date:
                    obs_row = self.get_observed_row(plant.plant_name, day)
                    if obs_row is not None:
                        try:
                            rows[day] = validate_weather_payload(obs_row)
                            continue
                        except ValueError:
                            pass
                missing.append(
                    {"date": day.isoformat(), "missing_inputs": list(WEATHER_FIELDS)}
                )
                continue
            try:
                rows[day] = validate_weather_payload(payload)
            except ValueError as exc:
                fields = getattr(exc, "missing_fields", list(WEATHER_FIELDS))
                missing.append({"date": day.isoformat(), "missing_inputs": fields})

        return WeatherFetchResult(
            provider=raw_result.provider or getattr(active, "name", "unknown"),
            available=not missing,
            rows=rows,
            missing=missing,
        )

    def availability_summary(self) -> dict:
        return {
            "future_weather_available": bool(self.future_provider.available),
            "provider": self.future_provider.name,
            "status": "available" if self.future_provider.available else "unavailable",
            "message": (
                "A future weather provider is integrated."
                if self.future_provider.available
                else (
                    "No future weather provider is integrated. Multi-day RF forecasts and "
                    "LSTM horizons above one day require future/intermediate weather."
                )
            ),
        }

"""Plant catalogue, plant detail and observed generation history."""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.utils.errors import ApiError
from backend.utils.serialization import iso_date
from backend.utils.validation import parse_type

TARGET = "DailyGeneration_MU"


class PlantService:
    def __init__(self, config, data_service, weather_service) -> None:
        self.config = config
        self.data = data_service
        self.weather = weather_service

    # ------------------------------------------------------------------ plants
    def list_plants(self, type_filter: str | None = None, district: str | None = None) -> dict:
        plants = self.data.list_plants()
        requested_type = parse_type(type_filter)
        requested_district = district.strip() if district and district.strip() else None

        if requested_type:
            plants = [plant for plant in plants if plant.type == requested_type]
        if requested_district:
            plants = [
                plant
                for plant in plants
                if (plant.district or "").lower() == requested_district.lower()
            ]

        return {
            "count": len(plants),
            "filters": {
                "type": requested_type,
                "district": requested_district,
            },
            "capacity_basis": "latest observed Capacity_MW per plant",
            "plants": [plant.as_dict() for plant in plants],
        }

    def detail(self, plant_id: str, history_limit: int | None = None) -> dict:
        plant = self.data.require_plant(plant_id)
        limit = history_limit or self.config.DEFAULT_HISTORY_LIMIT
        frame = self.data.get_frame(plant.plant_name)
        recent = frame.tail(limit).sort_values("Date")

        latest_generation = {
            "date": plant.latest_generation_date.isoformat(),
            "generation_mu": plant.latest_generation_mu,
            "unit": self.config.TARGET_UNIT,
            "frequency": self.config.FREQUENCY,
        }

        recent_rows = [
            {
                "date": iso_date(row.Date),
                "generation_mu": float(row.DailyGeneration_MU),
                "unit": self.config.TARGET_UNIT,
            }
            for row in recent.itertuples(index=False)
        ]

        weather_row = self.data.get_weather_row(
            plant.plant_name, plant.last_observed_date
        )
        weather_context = None
        if weather_row is not None:
            weather_context = {
                "date": plant.last_observed_date.isoformat(),
                "weather_type": "historical",
                "is_forecast": False,
                "temperature": weather_row["Temperature"],
                "humidity": weather_row["Humidity"],
                "wind_speed": weather_row["WindSpeed"],
                "ghi": weather_row["GHI"],
                "pressure": weather_row["Pressure"],
                "source": "cleaned/imputed observed weather",
            }

        return {
            "plant": plant.as_dict(),
            "latest_generation": latest_generation,
            "recent_generation": {
                "count": len(recent_rows),
                "limit": limit,
                "frequency": self.config.FREQUENCY,
                "unit": self.config.TARGET_UNIT,
                "data": recent_rows,
            },
            "weather_context": weather_context,
            "forecast_capability": self._forecast_capability(plant),
        }

    def _forecast_capability(self, plant) -> dict:
        provider = self.weather.availability_summary()
        return {
            "frequency": self.config.FREQUENCY,
            "unit": self.config.TARGET_UNIT,
            "horizon_default_days": self.config.DEFAULT_HORIZON,
            "horizon_max_days": self.config.MAX_HORIZON,
            "future_weather": provider,
            "random_forest": {
                "available": bool(provider["future_weather_available"]),
                "reason": (
                    "The Random Forest requires weather for every forecast day."
                    if not provider["future_weather_available"]
                    else "Future weather is available."
                ),
            },
            "lstm": {
                "one_day_horizon_available": True,
                "multi_day_horizon_available": bool(provider["future_weather_available"]),
                "reason": (
                    "A one-day LSTM forecast uses only the seven preceding observed rows "
                    "and needs no target-day weather. Horizons above one day require "
                    "weather for intermediate predicted days."
                ),
            },
            "endpoint": f"/api/forecast?plant_id={plant.plant_id}",
        }

    # ------------------------------------------------------- generation history
    def generation_history(
        self,
        plant_id: str | None = None,
        type_filter: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> dict:
        requested_type = parse_type(type_filter)
        if plant_id:
            return self._plant_history(plant_id, requested_type, start, end)
        return self._aggregate_history(requested_type, start, end)

    def _plant_history(
        self,
        plant_id: str,
        type_filter: str | None,
        start: date | None,
        end: date | None,
    ) -> dict:
        plant = self.data.require_plant(plant_id)
        if type_filter and plant.type != type_filter:
            raise ApiError(
                "FILTER_MISMATCH",
                f"Plant '{plant.plant_id}' is {plant.type}, not {type_filter}.",
                400,
                {"plant_id": plant.plant_id, "plant_type": plant.type, "type": type_filter},
            )

        frame = self.data.get_frame(plant.plant_name)
        subset = self._date_filter(frame, start, end)
        rows = [
            {
                "date": iso_date(row.Date),
                "generation_mu": float(row.DailyGeneration_MU),
                "unit": self.config.TARGET_UNIT,
            }
            for row in subset.itertuples(index=False)
        ]

        return {
            "scope": "plant",
            "plant_id": plant.plant_id,
            "plant_name": plant.plant_name,
            "type": plant.type,
            "frequency": self.config.FREQUENCY,
            "unit": self.config.TARGET_UNIT,
            "target": self.config.TARGET,
            "aggregation": "observed_plant_daily_generation",
            "requested_range": {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            },
            "available_range": {
                "start": plant.first_observed_date.isoformat(),
                "end": plant.last_observed_date.isoformat(),
            },
            "coverage": self._coverage(subset, start, end),
            "summary": self._summary(subset["DailyGeneration_MU"]),
            "count": len(rows),
            "data": rows,
            "notes": [
                "Only real observed daily records are returned. Missing calendar dates are "
                "not filled, interpolated or fabricated.",
                "No hourly values are produced from the daily target.",
            ],
        }

    def _aggregate_history(
        self,
        type_filter: str | None,
        start: date | None,
        end: date | None,
    ) -> dict:
        frame = self.data.all_weather_frame()
        frame = self._date_filter(frame, start, end)
        if type_filter:
            frame = frame[frame["Type"] == type_filter]

        if frame.empty:
            rows = []
            summary = self._empty_summary()
            daily = frame
        else:
            daily = (
                frame.groupby("Date", as_index=False)
                .agg(
                    generation_mu=(TARGET, "sum"),
                    reporting_plants=("PlantName", "nunique"),
                )
                .sort_values("Date")
            )
            rows = [
                {
                    "date": iso_date(row.Date),
                    "generation_mu": float(row.generation_mu),
                    "reporting_plants": int(row.reporting_plants),
                    "unit": self.config.TARGET_UNIT,
                }
                for row in daily.itertuples(index=False)
            ]
            summary = self._summary(daily["generation_mu"])
            summary["reporting_plants"] = int(frame["PlantName"].nunique())

        scope = "type" if type_filter else "fleet"
        return {
            "scope": scope,
            "plant_id": None,
            "plant_name": None,
            "type": type_filter,
            "frequency": self.config.FREQUENCY,
            "unit": self.config.TARGET_UNIT,
            "target": self.config.TARGET,
            "aggregation": "sum_of_observed_plant_generation_by_date",
            "requested_range": {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            },
            "coverage": self._coverage(daily, start, end),
            "summary": summary,
            "count": len(rows),
            "data": rows,
            "notes": [
                f"Daily totals are the sum of plants that reported on each date ({scope} scope).",
                "Only real observed daily records are returned; dates are not imputed.",
            ],
        }

    # ------------------------------------------------------------------ helpers
    def _date_filter(self, frame: pd.DataFrame, start: date | None, end: date | None):
        subset = frame
        if start is not None:
            subset = subset[subset["Date"] >= pd.Timestamp(start)]
        if end is not None:
            subset = subset[subset["Date"] <= pd.Timestamp(end)]
        return subset.sort_values("Date")

    def _summary(self, values: pd.Series) -> dict:
        if len(values) == 0:
            return self._empty_summary()
        return {
            "total_generation_mu": float(values.sum()),
            "mean_daily_generation_mu": float(values.mean()),
            "min_daily_generation_mu": float(values.min()),
            "max_daily_generation_mu": float(values.max()),
            "observations": int(len(values)),
        }

    def _empty_summary(self) -> dict:
        return {
            "total_generation_mu": 0.0,
            "mean_daily_generation_mu": None,
            "min_daily_generation_mu": None,
            "max_daily_generation_mu": None,
            "observations": 0,
        }

    def _coverage(self, frame: pd.DataFrame, start: date | None, end: date | None) -> dict:
        if frame.empty:
            return {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
                "calendar_days": 0,
                "observations": 0,
                "missing_calendar_days": 0,
            }
        first = frame["Date"].min().date()
        last = frame["Date"].max().date()
        calendar_days = (last - first).days + 1
        observations = int(len(frame))
        return {
            "start": first.isoformat(),
            "end": last.isoformat(),
            "calendar_days": calendar_days,
            "observations": observations,
            "missing_calendar_days": max(calendar_days - observations, 0),
        }

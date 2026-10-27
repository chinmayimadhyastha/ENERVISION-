"""Dashboard aggregates and descriptive analytics from the real datasets."""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.utils.errors import ApiError
from backend.utils.serialization import clean_float, iso_date
from backend.utils.validation import parse_type

TARGET = "DailyGeneration_MU"
WEATHER_FIELDS = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]


class AnalyticsService:
    def __init__(self, config, data_service, model_service, weather_service) -> None:
        self.config = config
        self.data = data_service
        self.models = model_service
        self.weather = weather_service

    # --------------------------------------------------------------- dashboard
    def dashboard(self) -> dict:
        plants = self.data.list_plants()
        type_counts = self.data.type_counts()
        capacity_by_type: dict[str, float] = {}
        for plant in plants:
            capacity_by_type[plant.type] = (
                capacity_by_type.get(plant.type, 0.0) + plant.capacity_mw
            )

        latest_date = self.data.latest_fleet_date()
        weather_frame = self.data.all_weather_frame()
        latest_rows = weather_frame[weather_frame["Date"].dt.date == latest_date]

        solar_rows = latest_rows[latest_rows["Type"] == "Solar"]
        wind_rows = latest_rows[latest_rows["Type"] == "Wind"]
        latest_generation = {
            "date": latest_date.isoformat(),
            "total_generation_mu": float(latest_rows[TARGET].sum()),
            "solar_generation_mu": float(solar_rows[TARGET].sum()),
            "wind_generation_mu": float(wind_rows[TARGET].sum()),
            "reporting_plants": int(latest_rows["PlantName"].nunique()),
            "total_plants": len(plants),
            "coverage_note": (
                "Only plants with an observed record on the latest fleet date are included."
            ),
        }

        latest_weather = None
        if not latest_rows.empty:
            latest_weather = {
                "date": latest_date.isoformat(),
                "scope": "fleet_mean_on_latest_fleet_date",
                "weather_type": "historical",
                "is_forecast": False,
                "reporting_plants": int(latest_rows["PlantName"].nunique()),
                "temperature": clean_float(latest_rows["Temperature"].mean()),
                "humidity": clean_float(latest_rows["Humidity"].mean()),
                "wind_speed": clean_float(latest_rows["WindSpeed"].mean()),
                "ghi": clean_float(latest_rows["GHI"].mean()),
                "pressure": clean_float(latest_rows["Pressure"].mean()),
                "units": {
                    "temperature": "degC",
                    "humidity": "%",
                    "wind_speed": "m/s",
                    "ghi": "kWh/m2/day",
                    "pressure": "kPa",
                },
                "note": (
                    "Arithmetic mean of the observed weather values for plants reporting "
                    "on this date. This is not a future-weather forecast."
                ),
            }

        last_dates = [plant.last_observed_date for plant in plants]
        stale_plants = sum(1 for last_date in last_dates if last_date < latest_date)
        stale_examples = [
            {
                "plant_id": plant.plant_id,
                "plant_name": plant.plant_name,
                "last_observed_date": plant.last_observed_date.isoformat(),
            }
            for plant in sorted(plants, key=lambda item: item.last_observed_date)[:5]
        ]
        provider = self.weather.availability_summary()

        return {
            "as_of_date": latest_date.isoformat(),
            "frequency": self.config.FREQUENCY,
            "unit": self.config.TARGET_UNIT,
            "target": self.config.TARGET,
            "total_plants": len(plants),
            "solar_plant_count": type_counts.get("Solar", 0),
            "wind_plant_count": type_counts.get("Wind", 0),
            "total_installed_capacity_mw": float(sum(plant.capacity_mw for plant in plants)),
            "capacity_by_type_mw": capacity_by_type,
            "capacity_basis": "latest observed Capacity_MW per plant",
            "latest_generation": latest_generation,
            "latest_weather_context": latest_weather,
            "model_status": self.models.status(),
            "forecast_status": {
                "frequency": self.config.FREQUENCY,
                "unit": self.config.TARGET_UNIT,
                "future_weather": provider,
                "random_forest_forecast_available": bool(
                    provider["future_weather_available"]
                ),
                "one_day_lstm_forecast_available": True,
                "multi_day_lstm_forecast_available": bool(
                    provider["future_weather_available"]
                ),
                "default_horizon_days": self.config.DEFAULT_HORIZON,
                "max_horizon_days": self.config.MAX_HORIZON,
            },
            "data_coverage": {
                "dataset_start": self.data.weather["Date"].min().date().isoformat(),
                "dataset_end": latest_date.isoformat(),
                "plants_reporting_on_latest_date": int(
                    latest_rows["PlantName"].nunique()
                ),
                "plants_with_stale_last_observation": stale_plants,
                "oldest_last_observation": min(last_dates).isoformat(),
                "plants_with_coordinates": sum(
                    1
                    for plant in plants
                    if plant.latitude is not None and plant.longitude is not None
                ),
                "rows_with_imputed_weather": int(
                    (self.data.weather["WeatherImputed"] == 1).sum()
                ),
                "stale_plant_examples": stale_examples,
            },
            "notes": [
                "All values are computed from the real canonical/cleaned datasets.",
                "No frontend demo values, synthetic plants or fabricated metrics are used.",
                "No future weather provider is integrated; forecast availability is reported "
                "honestly.",
            ],
        }

    # ---------------------------------------------------------------- analytics
    def analytics(
        self,
        plant_id: str | None = None,
        type_filter: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> dict:
        requested_type = parse_type(type_filter)
        frame = self.data.all_weather_frame()
        scope = "fleet"
        focus_plant = None

        if plant_id:
            focus_plant = self.data.require_plant(plant_id)
            if requested_type and focus_plant.type != requested_type:
                raise ApiError(
                    "FILTER_MISMATCH",
                    f"Plant '{focus_plant.plant_id}' is {focus_plant.type}, "
                    f"not {requested_type}.",
                    400,
                    {
                        "plant_id": focus_plant.plant_id,
                        "plant_type": focus_plant.type,
                        "type": requested_type,
                    },
                )
            frame = frame[frame["PlantName"] == focus_plant.plant_name]
            scope = "plant"
        elif requested_type:
            frame = frame[frame["Type"] == requested_type]
            scope = "type"

        frame = self._date_filter(frame, start, end)
        plant_names = sorted(frame["PlantName"].unique().tolist()) if not frame.empty else []
        capacity_mw = self._capacity_for_plants(plant_names)

        daily_totals = frame.groupby("Date")[TARGET].sum() if not frame.empty else pd.Series(dtype=float)

        summary = {
            "total_generation_mu": float(frame[TARGET].sum()) if not frame.empty else 0.0,
            "mean_daily_generation_mu": (
                float(daily_totals.mean()) if len(daily_totals) else None
            ),
            "min_daily_generation_mu": (
                float(daily_totals.min()) if len(daily_totals) else None
            ),
            "max_daily_generation_mu": (
                float(daily_totals.max()) if len(daily_totals) else None
            ),
            "days": int(len(daily_totals)),
            "plant_day_observations": int(len(frame)),
            "plants": len(plant_names),
            "capacity_mw": capacity_mw,
            "unit": self.config.TARGET_UNIT,
        }

        return {
            "scope": scope,
            "plant_id": focus_plant.plant_id if focus_plant else None,
            "plant_name": focus_plant.plant_name if focus_plant else None,
            "type": requested_type,
            "frequency": self.config.FREQUENCY,
            "unit": self.config.TARGET_UNIT,
            "target": self.config.TARGET,
            "capacity_basis": "latest observed Capacity_MW per plant",
            "requested_range": {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            },
            "coverage": self._analytics_coverage(frame),
            "summary": summary,
            "generation_by_date": self._by_date(frame),
            "generation_by_type": self._by_type(frame),
            "generation_by_plant": self._by_plant(frame),
            "derived_metrics": {
                "generation_per_mw_per_day": (
                    "Descriptive analytics ratio equal to mean daily generation divided by "
                    "the plant's latest observed capacity. It is not a model feature, is "
                    "not used by the Random Forest, and is not a capacity factor."
                )
            },
            "notes": [
                "Sums and means use only observed plant-day records.",
                "Dates without observations are not interpolated or fabricated.",
                "Plant capacity comes from the latest observed Capacity_MW; it is not "
                "reconstructed for each historical date.",
                "The removed leaked feature Generation_per_MW is never used for inference.",
            ],
        }

    # ------------------------------------------------------------------ helpers
    def _date_filter(self, frame: pd.DataFrame, start: date | None, end: date | None):
        subset = frame
        if start is not None:
            subset = subset[subset["Date"] >= pd.Timestamp(start)]
        if end is not None:
            subset = subset[subset["Date"] <= pd.Timestamp(end)]
        return subset.sort_values(["Date", "PlantName"])

    def _capacity_for_plants(self, plant_names: list[str]) -> float:
        total = 0.0
        for name in plant_names:
            record = self.data.plants_by_name.get(name)
            if record is not None:
                total += record.capacity_mw
        return float(total)

    def _by_date(self, frame: pd.DataFrame) -> list[dict]:
        if frame.empty:
            return []
        grouped = frame.groupby("Date", as_index=False).agg(
            total_generation_mu=(TARGET, "sum"),
            reporting_plants=("PlantName", "nunique"),
        )
        solar = (
            frame[frame["Type"] == "Solar"].groupby("Date")[TARGET].sum().rename("solar")
        )
        wind = (
            frame[frame["Type"] == "Wind"].groupby("Date")[TARGET].sum().rename("wind")
        )
        merged = (
            grouped.set_index("Date")
            .join(solar, how="left")
            .join(wind, how="left")
            .fillna({"solar": 0.0, "wind": 0.0})
            .reset_index()
            .sort_values("Date")
        )
        return [
            {
                "date": iso_date(row.Date),
                "total_generation_mu": float(row.total_generation_mu),
                "solar_generation_mu": float(row.solar),
                "wind_generation_mu": float(row.wind),
                "reporting_plants": int(row.reporting_plants),
            }
            for row in merged.itertuples(index=False)
        ]

    def _by_type(self, frame: pd.DataFrame) -> list[dict]:
        if frame.empty:
            return []
        type_daily = (
            frame.groupby(["Type", "Date"], as_index=False)[TARGET].sum()
        )
        rows = []
        for renewable_type, group in frame.groupby("Type", sort=True):
            daily = type_daily[type_daily["Type"] == renewable_type][TARGET]
            plant_names = sorted(group["PlantName"].unique().tolist())
            rows.append(
                {
                    "type": renewable_type,
                    "total_generation_mu": float(group[TARGET].sum()),
                    "mean_daily_generation_mu": float(daily.mean()),
                    "observations": int(len(group)),
                    "days": int(daily.count()),
                    "plant_count": len(plant_names),
                    "capacity_mw": self._capacity_for_plants(plant_names),
                }
            )
        return rows

    def _by_plant(self, frame: pd.DataFrame) -> list[dict]:
        if frame.empty:
            return []
        rows = []
        for plant_name, group in frame.groupby("PlantName", sort=True):
            record = self.data.plants_by_name.get(plant_name)
            observations = int(len(group))
            mean_daily = float(group[TARGET].mean())
            capacity = float(record.capacity_mw) if record else None
            ratio = (
                mean_daily / capacity
                if capacity is not None and capacity > 0
                else None
            )
            rows.append(
                {
                    "plant_id": record.plant_id if record else None,
                    "plant_name": plant_name,
                    "type": str(group["Type"].iloc[0]),
                    "capacity_mw": capacity,
                    "total_generation_mu": float(group[TARGET].sum()),
                    "mean_daily_generation_mu": mean_daily,
                    "generation_per_mw_per_day": ratio,
                    "observations": observations,
                    "first_observed_date": iso_date(group["Date"].min()),
                    "last_observed_date": iso_date(group["Date"].max()),
                }
            )
        return rows

    def _analytics_coverage(self, frame: pd.DataFrame) -> dict:
        if frame.empty:
            return {
                "start": None,
                "end": None,
                "calendar_days": 0,
                "dates_observed": 0,
                "missing_calendar_days": 0,
                "plant_day_observations": 0,
            }
        start = frame["Date"].min().date()
        end = frame["Date"].max().date()
        dates_observed = int(frame["Date"].nunique())
        calendar_days = (end - start).days + 1
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "calendar_days": calendar_days,
            "dates_observed": dates_observed,
            "missing_calendar_days": max(calendar_days - dates_observed, 0),
            "plant_day_observations": int(len(frame)),
        }

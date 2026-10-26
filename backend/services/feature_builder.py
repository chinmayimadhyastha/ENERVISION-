"""Construction of the exact daily model feature vectors.

The rules mirror ``scripts/engineer_plant_features.py`` and
``scripts/train_lstm_model(ABR).py``:

* weather lags use the preceding row's weather;
* generation lags 1/2/3/7 use preceding observed/predicted generation;
* rolling generation is the mean of the preceding 3/7 generation rows;
* the prediction-day target is never an input.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np

WEATHER_FIELDS = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
WEATHER_LAG_FIELDS = ["Temperature", "Humidity", "WindSpeed", "GHI"]


class WeatherInputError(ValueError):
    """Raised when a weather payload is missing or physically invalid fields."""

    def __init__(self, missing_fields: list[str], message: str | None = None) -> None:
        self.missing_fields = missing_fields
        super().__init__(
            message
            or f"Weather input is missing or invalid for: {', '.join(missing_fields)}"
        )


def validate_weather_payload(weather: dict | None) -> dict[str, float]:
    if not isinstance(weather, dict):
        raise WeatherInputError(list(WEATHER_FIELDS), "Weather payload is absent.")

    missing: list[str] = []
    clean: dict[str, float] = {}
    for field in WEATHER_FIELDS:
        value = weather.get(field)
        try:
            number = float(value)
        except (TypeError, ValueError):
            missing.append(field)
            continue
        if not math.isfinite(number) or number <= -900:
            missing.append(field)
            continue
        clean[field] = number

    if missing:
        raise WeatherInputError(missing)
    return clean


def validate_generation_history(values: list[float], minimum: int = 7) -> list[float]:
    if len(values) < minimum:
        raise ValueError(
            f"At least {minimum} preceding generation values are required; "
            f"received {len(values)}."
        )
    clean = []
    for value in values[-minimum:]:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Generation history contains a non-finite value.")
        clean.append(max(number, 0.0))
    return clean


def calendar_features(day: date) -> dict[str, float | int]:
    month = day.month
    day_of_year = day.timetuple().tm_yday
    return {
        "Year": day.year,
        "Month": month,
        "DayOfYear": day_of_year,
        "DayOfWeek": day.weekday(),
        "Month_sin": math.sin(2 * math.pi * month / 12),
        "Month_cos": math.cos(2 * math.pi * month / 12),
        "DayOfYear_sin": math.sin(2 * math.pi * day_of_year / 365.25),
        "DayOfYear_cos": math.cos(2 * math.pi * day_of_year / 365.25),
    }


class FeatureBuilder:
    def __init__(
        self,
        rf_features: list[str],
        lstm_features: list[str],
        lstm_column_map: dict[str, str],
    ) -> None:
        self.rf_features = list(rf_features)
        self.lstm_features = list(lstm_features)
        self.lstm_column_map = dict(lstm_column_map)

    def rf_row(
        self,
        day: date,
        capacity_mw: float,
        weather: dict,
        previous_weather: dict | None,
        generation_history: list[float],
    ) -> list[float]:
        """Build one leakage-free 24-feature Random Forest row."""
        clean_weather = validate_weather_payload(weather)
        if previous_weather is None:
            raise WeatherInputError(
                list(WEATHER_LAG_FIELDS),
                "Previous-row weather is required for the weather lag features.",
            )
        clean_previous = validate_weather_payload(previous_weather)
        history = validate_generation_history(generation_history, minimum=7)

        values: dict[str, float | int] = {
            "Capacity_MW": float(capacity_mw),
            **clean_weather,
            **{f"{field}_lag_1": clean_previous[field] for field in WEATHER_LAG_FIELDS},
            "Generation_lag_1": history[-1],
            "Generation_lag_2": history[-2],
            "Generation_lag_3": history[-3],
            "Generation_lag_7": history[-7],
            "Generation_roll_3": float(np.mean(history[-3:])),
            "Generation_roll_7": float(np.mean(history[-7:])),
            **calendar_features(day),
        }
        missing = [feature for feature in self.rf_features if feature not in values]
        if missing:
            raise ValueError(f"RF feature contract cannot be satisfied: missing {missing}")
        if "Generation_per_MW" in self.rf_features:
            raise ValueError("Generation_per_MW is forbidden in the RF contract.")
        return [float(values[feature]) for feature in self.rf_features]

    def lstm_row(
        self,
        day: date,
        capacity_mw: float,
        weather: dict,
        generation_history: list[float],
    ) -> list[float]:
        """Build one 12-feature LSTM row for an intermediate forecast day."""
        clean_weather = validate_weather_payload(weather)
        history = validate_generation_history(generation_history, minimum=7)
        calendar = calendar_features(day)

        values: dict[str, float | int] = {
            "Capacity_MW": float(capacity_mw),
            **clean_weather,
            **calendar,
            "Lagged_Generation": history[-1],
            "Rolling_Generation_7": float(np.mean(history[-7:])),
        }
        missing = [feature for feature in self.lstm_features if feature not in values]
        if missing:
            raise ValueError(f"LSTM feature contract cannot be satisfied: missing {missing}")
        return [float(values[feature]) for feature in self.lstm_features]

    def lstm_row_from_dataset(self, row) -> list[float]:
        """Read an observed row using the manifest's LSTM column mapping."""
        values = []
        for feature in self.lstm_features:
            column = self.lstm_column_map.get(feature, feature)
            if column not in row:
                raise ValueError(
                    f"Feature dataset is missing LSTM source column {column!r} "
                    f"for {feature!r}."
                )
            values.append(float(row[column]))
        return values

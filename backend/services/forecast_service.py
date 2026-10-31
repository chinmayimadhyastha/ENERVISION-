"""Daily forecast orchestration.

The service deliberately separates three states:

``ok``
    All required inputs exist and the model produced a daily prediction.
``weather_required``
    The request is structurally valid but future/intermediate weather is absent.
    No prediction is fabricated.
``insufficient_history``
    The plant does not have enough preceding observations for the selected model.

Model inference is never attempted when required inputs are missing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from backend.services.feature_builder import WEATHER_FIELDS, FeatureBuilder
from backend.utils.errors import ApiError
from backend.utils.serialization import iso_date

TARGET = "DailyGeneration_MU"


@dataclass
class ForecastEntry:
    date: date
    prediction: float
    raw_prediction: float
    clamp_applied: bool
    confidence: dict | None = None
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None
    features: dict[str, float] | None = field(default=None, repr=False)
    sequence_shape: list[int] | None = field(default=None, repr=False)
    sequence_dates: list[str] | None = field(default=None, repr=False)
    explanation: list[dict] | None = field(default=None, repr=False)


@dataclass
class ForecastResult:
    status: str
    plant: object
    horizon_days: int
    model_requested: str
    model: str | None
    model_family: str | None
    base_date: date | None
    forecast_dates: list[date]
    entries: list[ForecastEntry]
    required_weather: dict | None
    missing_weather: list[dict]
    history_context: dict
    notes: list[str]
    provider: str
    future_weather_available: bool
    insufficient_history: dict | None = None


class ForecastService:
    def __init__(
        self,
        config,
        data_service,
        model_service,
        weather_service,
        feature_builder: FeatureBuilder,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.data = data_service
        self.models = model_service
        self.weather = weather_service
        self.feature_builder = feature_builder
        self.logger = logger or logging.getLogger("enervision.forecast")
        self._cache = {}

    # ------------------------------------------------------------------ public
    def forecast(
        self,
        plant_id: str,
        model_requested: str,
        horizon: int,
        *,
        base_date: date | None = None,
        weather_provider=None,
    ) -> ForecastResult:
        cache_key = (plant_id, model_requested, horizon, base_date, str(weather_provider))
        if cache_key in self._cache:
            return self._cache[cache_key]
        plant = self.data.require_plant(plant_id)
        model_id, model_family, lstm_type = self._resolve_model(plant, model_requested)

        frame = self.data.get_frame(plant.plant_name)
        if base_date is not None and base_date > plant.last_observed_date:
            raise ApiError(
                "INVALID_BASE_DATE",
                (
                    "A forecast base date cannot be later than the plant's last observed "
                    "date."
                ),
                400,
                {
                    "base_date": base_date.isoformat(),
                    "last_observed_date": plant.last_observed_date.isoformat(),
                },
            )

        cutoff = pd.Timestamp(base_date) if base_date is not None else None
        observed = frame if cutoff is None else frame[frame["Date"] <= cutoff]
        if observed.empty:
            return ForecastResult(
                status="insufficient_history",
                plant=plant,
                horizon_days=horizon,
                model_requested=model_requested,
                model=model_id,
                model_family=model_family,
                base_date=base_date,
                forecast_dates=[],
                entries=[],
                required_weather=None,
                missing_weather=[],
                history_context={},
                notes=["No observed rows exist on or before the requested base date."],
                provider=self._provider_name(weather_provider),
                future_weather_available=False,
                insufficient_history={
                    "required_observed_rows": 7,
                    "available_observed_rows": 0,
                    "reason": "no_observations_on_or_before_base_date",
                },
            )

        effective_base = observed["Date"].max().date()
        forecast_dates = [
            effective_base + timedelta(days=offset) for offset in range(1, horizon + 1)
        ]

        # RF needs weather for every forecast day.  LSTM needs weather only for
        # intermediate predicted days, because the target day itself is not an
        # input row; horizon 1 therefore needs no future weather at all.
        if model_family == "random_forest":
            required_dates = list(forecast_dates)
        else:
            required_dates = list(forecast_dates[:-1])

        fetch = self.weather.fetch_future(
            plant, required_dates, provider=weather_provider
        )
        active_provider = self.weather.resolve_provider(weather_provider) or weather_provider or self.weather.future_provider

        if fetch.missing:
            return ForecastResult(
                status="weather_required",
                plant=plant,
                horizon_days=horizon,
                model_requested=model_requested,
                model=model_id,
                model_family=model_family,
                base_date=effective_base,
                forecast_dates=forecast_dates,
                entries=[],
                required_weather={
                    "provider": fetch.provider,
                    "provider_available": bool(
                        getattr(active_provider, "available", False)
                    ),
                    "dates": [day.isoformat() for day in required_dates],
                    "inputs": list(WEATHER_FIELDS),
                    "missing": fetch.missing,
                    "target_day_weather_required": model_family == "random_forest",
                    "note": self._weather_note(model_family),
                },
                missing_weather=fetch.missing,
                history_context={
                    "last_observed_date": effective_base.isoformat(),
                    "observed_rows_used": int(len(observed)),
                    "forecast_dates": [day.isoformat() for day in forecast_dates],
                },
                notes=self._base_notes(model_family, plant, effective_base),
                provider=fetch.provider,
                future_weather_available=False,
            )

        if model_family == "random_forest":
            return self._forecast_rf(
                plant=plant,
                model_requested=model_requested,
                model_id=model_id,
                horizon=horizon,
                observed=observed,
                base_date=effective_base,
                forecast_dates=forecast_dates,
                weather_rows=fetch.rows,
                provider=fetch.provider,
                provider_available=bool(
                    getattr(active_provider, "available", False)
                ),
            )

        return self._forecast_lstm(
            plant=plant,
            model_requested=model_requested,
            model_id=model_id,
            lstm_type=lstm_type,
            horizon=horizon,
            observed=observed,
            base_date=effective_base,
            forecast_dates=forecast_dates,
            weather_rows=fetch.rows,
            required_dates=required_dates,
            provider=fetch.provider,
            provider_available=bool(
                getattr(active_provider, "available", False)
            ),
        )

    # --------------------------------------------------------------- RF branch
    def _forecast_rf(
        self,
        *,
        plant,
        model_requested: str,
        model_id: str,
        horizon: int,
        observed: pd.DataFrame,
        base_date: date,
        forecast_dates: list[date],
        weather_rows: dict,
        provider: str,
        provider_available: bool,
    ) -> ForecastResult:
        if len(observed) < 7:
            return self._insufficient(
                plant=plant,
                model_requested=model_requested,
                model_id=model_id,
                model_family="random_forest",
                horizon=horizon,
                base_date=base_date,
                forecast_dates=forecast_dates,
                provider=provider,
                observed_rows=int(len(observed)),
                required_rows=7,
                reason="rf_requires_seven_preceding_generation_rows",
            )

        generation_history = [
            float(value) for value in observed[TARGET].tolist()[-7:]
        ]
        context_rows = observed.tail(7)
        capacity_mw = float(observed.iloc[-1]["Capacity_MW"])
        last_observed = observed.iloc[-1]
        previous_weather = {
            field: float(last_observed[field]) for field in WEATHER_FIELDS
        }

        entries: list[ForecastEntry] = []
        for day in forecast_dates:
            weather_payload = weather_rows[day]
            vector = self.feature_builder.rf_row(
                day,
                capacity_mw,
                weather_payload,
                previous_weather,
                generation_history,
            )
            prediction = self.models.predict_rf(
                vector,
                renewable_type=plant.type,
                plant_capacity_mw=capacity_mw,
            )
            entries.append(
                ForecastEntry(
                    date=day,
                    prediction=prediction.served,
                    raw_prediction=prediction.raw,
                    clamp_applied=prediction.clamp_applied,
                    confidence=prediction.confidence,
                    p10=prediction.p10,
                    p50=prediction.p50,
                    p90=prediction.p90,
                    features=dict(zip(self.models.rf_features, vector)),
                    explanation=prediction.explanation,
                )
            )
            generation_history.append(prediction.served)
            previous_weather = dict(weather_payload)

        history_context = {
            "last_observed_date": base_date.isoformat(),
            "observed_rows_used": int(len(observed)),
            "capacity_mw": capacity_mw,
            "generation_lag_window": [
                {
                    "date": iso_date(row.Date),
                    "generation_mu": float(row.DailyGeneration_MU),
                }
                for row in context_rows.itertuples(index=False)
            ],
            "weather_lag_source_date": iso_date(last_observed["Date"]),
            "target_day_weather_required": True,
            "target_day_target_used": False,
            "note": (
                "RF lag/rolling features use only preceding observed generation. The "
                "prediction-day DailyGeneration_MU is never supplied to the model."
            ),
        }

        res = ForecastResult(
            status="ok",
            plant=plant,
            horizon_days=horizon,
            model_requested=model_requested,
            model=model_id,
            model_family="random_forest",
            base_date=base_date,
            forecast_dates=forecast_dates,
            entries=entries,
            required_weather=None,
            missing_weather=[],
            history_context=history_context,
            notes=self._base_notes("random_forest", plant, base_date)
            + [
                "Random Forest lag and rolling generation features are computed only from "
                "preceding observed or previously predicted generation.",
                "Generation_per_MW is not created and is never supplied to the Random Forest.",
            ],
            provider=provider,
            future_weather_available=provider_available,
        )
        self._cache[(plant.plant_id, model_requested, horizon, base_date, str(provider))] = res
        return res

    # ------------------------------------------------------------- LSTM branch
    def _forecast_lstm(
        self,
        *,
        plant,
        model_requested: str,
        model_id: str,
        lstm_type: str,
        horizon: int,
        observed: pd.DataFrame,
        base_date: date,
        forecast_dates: list[date],
        weather_rows: dict,
        required_dates: list[date],
        provider: str,
        provider_available: bool,
    ) -> ForecastResult:
        feature_frame = self.data.get_feature_frame(plant.plant_name)
        feature_frame = feature_frame[feature_frame["Date"] <= pd.Timestamp(base_date)]
        if len(feature_frame) < self.config.LSTM_SEQUENCE_LENGTH:
            return self._insufficient(
                plant=plant,
                model_requested=model_requested,
                model_id=model_id,
                model_family="lstm",
                horizon=horizon,
                base_date=base_date,
                forecast_dates=forecast_dates,
                provider=provider,
                observed_rows=int(len(feature_frame)),
                required_rows=self.config.LSTM_SEQUENCE_LENGTH,
                reason="lstm_requires_seven_feature_rows",
                extra={
                    "observed_rows": int(len(observed)),
                    "required_feature_rows": self.config.LSTM_SEQUENCE_LENGTH,
                },
            )

        sequence_rows = feature_frame.tail(self.config.LSTM_SEQUENCE_LENGTH)
        sequence = np.asarray(
            [
                self.feature_builder.lstm_row_from_dataset(row._asdict())
                for row in sequence_rows.itertuples(index=False)
            ],
            dtype=float,
        )
        sequence_dates = [iso_date(value) for value in sequence_rows["Date"].tolist()]

        generation_history = [
            float(value) for value in observed[TARGET].tolist()[-7:]
        ]
        if len(generation_history) < 7:
            return self._insufficient(
                plant=plant,
                model_requested=model_requested,
                model_id=model_id,
                model_family="lstm",
                horizon=horizon,
                base_date=base_date,
                forecast_dates=forecast_dates,
                provider=provider,
                observed_rows=int(len(observed)),
                required_rows=7,
                reason="lstm_requires_seven_preceding_generation_rows",
            )

        context_rows = observed.tail(7)
        capacity_mw = float(observed.iloc[-1]["Capacity_MW"])
        entries: list[ForecastEntry] = []
        last_date = base_date

        for step in range(horizon):
            prediction = self.models.predict_lstm(
                lstm_type,
                sequence,
                plant_capacity_mw=capacity_mw,
            )
            predicted_date = last_date + timedelta(days=1)
            if predicted_date != forecast_dates[step]:
                raise ApiError(
                    "FORECAST_DATE_MISMATCH",
                    "Internal forecast date sequence is inconsistent.",
                    500,
                )
            entries.append(
                ForecastEntry(
                    date=predicted_date,
                    prediction=prediction.served,
                    raw_prediction=prediction.raw,
                    clamp_applied=prediction.clamp_applied,
                    confidence=prediction.confidence,
                    p10=prediction.p10,
                    p50=prediction.p50,
                    p90=prediction.p90,
                    sequence_shape=list(sequence.shape),
                    sequence_dates=list(sequence_dates),
                )
            )

            if step < horizon - 1:
                weather_payload = weather_rows[predicted_date]
                next_row = self.feature_builder.lstm_row(
                    predicted_date,
                    capacity_mw,
                    weather_payload,
                    generation_history,
                )
                sequence = np.vstack([sequence[1:], np.asarray(next_row, dtype=float)])
                sequence_dates = sequence_dates[1:] + [predicted_date.isoformat()]
                generation_history.append(prediction.served)
                last_date = predicted_date

        consecutive = self._is_calendar_consecutive(sequence_dates)

        history_context = {
            "last_observed_date": base_date.isoformat(),
            "observed_rows_used": int(len(observed)),
            "capacity_mw": capacity_mw,
            "sequence_length": self.config.LSTM_SEQUENCE_LENGTH,
            "sequence_dates": list(sequence_dates),
            "sequence_start_date": sequence_dates[0],
            "sequence_end_date": sequence_dates[-1],
            "sequence_calendar_consecutive": consecutive,
            "generation_context": [
                {
                    "date": iso_date(row.Date),
                    "generation_mu": float(row.DailyGeneration_MU),
                }
                for row in context_rows.itertuples(index=False)
            ],
            "intermediate_weather_dates": [day.isoformat() for day in required_dates],
            "target_day_weather_required": False,
            "target_day_target_used": False,
            "note": (
                "LSTM inference follows the committed training convention: the seven "
                "feature rows preceding the target day form the input window. The target "
                "day's own weather is not an input."
            ),
        }

        res = ForecastResult(
            status="ok",
            plant=plant,
            horizon_days=horizon,
            model_requested=model_requested,
            model=model_id,
            model_family="lstm",
            base_date=base_date,
            forecast_dates=forecast_dates,
            entries=entries,
            required_weather=None,
            missing_weather=[],
            history_context=history_context,
            notes=self._base_notes("lstm", plant, base_date)
            + [
                "LSTM input shape is (7, 12), matching the frozen model contract.",
                "A one-day LSTM horizon uses only the seven preceding observed feature "
                "rows and does not require target-day weather.",
                "For horizons above one day, intermediate predicted days require weather "
                "because they enter the next input window.",
            ],
            provider=provider,
            future_weather_available=provider_available,
        )
        self._cache[(plant.plant_id, model_requested, horizon, base_date, str(provider))] = res
        return res

    # ------------------------------------------------------------------ helpers
    def _resolve_model(self, plant, model_requested: str):
        if model_requested == "rf":
            return "random_forest_daily", "random_forest", None
        renewable_type = str(plant.type).strip().lower()
        if renewable_type == "solar":
            return "solar_lstm_daily", "lstm", "Solar"
        if renewable_type == "wind":
            return "wind_lstm_daily", "lstm", "Wind"
        raise ApiError(
            "UNSUPPORTED_PLANT_TYPE",
            f"No LSTM model exists for plant type {plant.type!r}.",
            422,
            {"plant_id": plant.plant_id, "type": plant.type},
        )

    def _insufficient(
        self,
        *,
        plant,
        model_requested: str,
        model_id: str,
        model_family: str,
        horizon: int,
        base_date: date,
        forecast_dates: list[date],
        provider: str,
        observed_rows: int,
        required_rows: int,
        reason: str,
        extra: dict | None = None,
    ) -> ForecastResult:
        details = {
            "required_rows": required_rows,
            "available_rows": observed_rows,
            "reason": reason,
        }
        if extra:
            details.update(extra)
        return ForecastResult(
            status="insufficient_history",
            plant=plant,
            horizon_days=horizon,
            model_requested=model_requested,
            model=model_id,
            model_family=model_family,
            base_date=base_date,
            forecast_dates=forecast_dates,
            entries=[],
            required_weather=None,
            missing_weather=[],
            history_context={
                "last_observed_date": base_date.isoformat(),
                "observed_rows_used": observed_rows,
            },
            notes=self._base_notes(model_family, plant, base_date),
            provider=provider,
            future_weather_available=False,
            insufficient_history=details,
        )

    def _base_notes(self, model_family: str, plant, base_date: date) -> list[str]:
        notes = [
            "Daily forecast only. Frequency is daily and the unit is MU/day.",
            "No hourly values are produced: no interpolation, division by 24, synthetic "
            "timestamps, or +3H/+6H/+12H/+24H outputs.",
            "Confidence is null by default; calibrated quantiles (P10, P50, P90) are provided when requested.",
        ]
        if model_family == "lstm":
            notes.append(
                "LSTM inference follows the frozen seven-row sequence contract (7 timesteps, "
                "12 features)."
            )
            if str(plant.type).strip().lower() == "wind":
                notes.append(
                    "Wind LSTM: raw_prediction is preserved. The served prediction is "
                    "max(raw_prediction, 0) as a serving-layer physical constraint; the "
                    "neural network itself is not constrained to non-negative outputs."
                )
        else:
            notes.append(
                "Random Forest: exactly 24 leakage-free features. The prediction-day target "
                "is not an input."
            )
        if base_date < plant.last_observed_date:
            notes.append(
                "The requested base date is earlier than the plant's last observation; this "
                "is a historical one-step inference, not a current future forecast."
            )
        return notes

    def _weather_note(self, model_family: str) -> str:
        if model_family == "random_forest":
            return (
                "The Random Forest requires observed or forecast weather for every forecast "
                "day. No future weather provider is integrated, so no prediction is made."
            )
        return (
            "The LSTM requires weather only for intermediate predicted days (all forecast "
            "days before the final target day). A one-day horizon needs no future weather."
        )

    def _provider_name(self, provider) -> str:
        active = provider or self.weather.future_provider
        return getattr(active, "name", "unavailable")

    @staticmethod
    def _is_calendar_consecutive(sequence_dates: list[str]) -> bool:
        if len(sequence_dates) < 2:
            return True
        parsed = [date.fromisoformat(value) for value in sequence_dates]
        return all(
            (parsed[index] - parsed[index - 1]).days == 1
            for index in range(1, len(parsed))
        )

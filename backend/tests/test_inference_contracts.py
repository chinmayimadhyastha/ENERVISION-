import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from backend.services.feature_builder import WEATHER_FIELDS
from backend.services.weather_service import FutureWeatherProvider, WeatherFetchResult
from backend.tests.helpers import (
    NEGATIVE_WIND_PLANT_ID,
    SOLAR_PLANT_ID,
    WIND_PLANT_ID,
    ObservedWeatherProvider,
)


def test_rf_contract_is_exactly_24_target_free_features(container):
    rf_features = container.models.rf_features
    assert rf_features == container.contracts["rf_features"]
    assert len(rf_features) == 24
    assert "Generation_per_MW" not in rf_features
    assert "DailyGeneration_MU" not in rf_features
    assert container.models.rf.n_features_in_ == 24
    assert list(container.models.rf.feature_names_in_) == rf_features


def test_rf_inference_with_real_observed_weather_and_exact_feature_parity(
    container, observed_weather
):
    result = container.forecast.forecast(
        plant_id=SOLAR_PLANT_ID,
        model_requested="rf",
        horizon=3,
        base_date=date(2026, 8, 1),
        weather_provider=observed_weather,
    )
    assert result.status == "ok"
    assert result.model_family == "random_forest"
    assert result.model == "random_forest_daily"
    assert len(result.entries) == 3
    assert [entry.date.isoformat() for entry in result.entries] == [
        "2026-08-02",
        "2026-08-03",
        "2026-08-04",
    ]

    first = result.entries[0]
    assert list(first.features.keys()) == container.models.rf_features
    assert "DailyGeneration_MU" not in first.features
    assert "Generation_per_MW" not in first.features
    assert first.prediction == max(first.raw_prediction, 0.0)
    assert math.isfinite(first.raw_prediction)

    plant = container.data.require_plant(SOLAR_PLANT_ID)
    feature_frame = container.data.get_feature_frame(plant.plant_name)
    dataset_row = feature_frame[
        feature_frame["Date"].dt.date == date(2026, 8, 2)
    ].iloc[0]
    for feature in container.models.rf_features:
        assert first.features[feature] == pytest.approx(
            float(dataset_row[feature]), abs=1e-9
        ), feature

    for entry in result.entries[1:]:
        assert math.isfinite(entry.raw_prediction)
        assert entry.prediction >= 0.0


def test_lstm_contracts_are_7_by_12_for_solar_and_wind(container):
    for plant_id, expected_model, expected_type in (
        (SOLAR_PLANT_ID, "solar_lstm_daily", "Solar"),
        (WIND_PLANT_ID, "wind_lstm_daily", "Wind"),
    ):
        plant = container.data.require_plant(plant_id)
        assert plant.type == expected_type
        assert container.models.lstm_features == container.contracts["lstm_features"]
        assert len(container.models.lstm_features) == 12
        assert container.models.sequence_length == 7

        feature_frame = container.data.get_feature_frame(plant.plant_name)
        sequence_rows = feature_frame.tail(7)
        sequence = np.asarray(
            [
                container.feature_builder.lstm_row_from_dataset(row._asdict())
                for row in sequence_rows.itertuples(index=False)
            ],
            dtype=float,
        )
        assert sequence.shape == (7, 12)

        model = (
            container.models.solar_lstm
            if expected_type == "Solar"
            else container.models.wind_lstm
        )
        assert tuple(model.input_shape) == (None, 7, 12)
        assert tuple(model.output_shape) == (None, 1)

        scaler = (
            container.models.solar_feature_scaler
            if expected_type == "Solar"
            else container.models.wind_feature_scaler
        )
        assert list(scaler.feature_names_in_) == container.models.lstm_features

        prediction = container.models.predict_lstm(expected_type, sequence)
        assert math.isfinite(prediction.raw)
        assert prediction.served == max(prediction.raw, 0.0)

        result = container.forecast.forecast(
            plant_id=plant_id,
            model_requested="lstm",
            horizon=1,
        )
        assert result.status == "ok"
        assert result.model == expected_model
        assert len(result.entries) == 1
        assert result.entries[0].sequence_shape == [7, 12]
        assert result.entries[0].raw_prediction == pytest.approx(
            prediction.raw, abs=1e-12
        )


def test_lstm_horizon_two_does_not_need_target_day_weather(container):
    provider = ObservedWeatherProvider(
        container, allowed_dates={date(2026, 8, 2)}
    )
    result = container.forecast.forecast(
        plant_id=SOLAR_PLANT_ID,
        model_requested="lstm",
        horizon=2,
        base_date=date(2026, 8, 1),
        weather_provider=provider,
    )
    assert result.status == "ok"
    assert len(result.entries) == 2
    assert [entry.date.isoformat() for entry in result.entries] == [
        "2026-08-02",
        "2026-08-03",
    ]
    # Weather was required and supplied only for the intermediate predicted day,
    # not for the final target day.
    assert result.history_context["intermediate_weather_dates"] == ["2026-08-02"]
    assert result.history_context["target_day_weather_required"] is False


def test_rf_requires_weather_for_every_forecast_day(container):
    class EmptyProvider(FutureWeatherProvider):
        name = "empty_test_provider"
        available = True

        def fetch(self, plant, dates):
            return WeatherFetchResult(
                provider=self.name,
                available=False,
                rows={},
                missing=[
                    {"date": day.isoformat(), "missing_inputs": list(WEATHER_FIELDS)}
                    for day in dates
                ],
            )

    result = container.forecast.forecast(
        plant_id=SOLAR_PLANT_ID,
        model_requested="rf",
        horizon=2,
        base_date=date(2026, 8, 1),
        weather_provider=EmptyProvider(),
    )
    assert result.status == "weather_required"
    assert result.entries == []
    assert result.required_weather["target_day_weather_required"] is True
    assert result.required_weather["dates"] == ["2026-08-02", "2026-08-03"]
    assert [item["date"] for item in result.missing_weather] == [
        "2026-08-02",
        "2026-08-03",
    ]


def test_wind_raw_negative_is_preserved_internally_and_clamped_for_serving(container):
    result = container.forecast.forecast(
        plant_id=NEGATIVE_WIND_PLANT_ID,
        model_requested="lstm",
        horizon=1,
        base_date=date(2026, 6, 19),
    )
    assert result.status == "ok"
    entry = result.entries[0]
    assert entry.raw_prediction < 0
    assert entry.prediction == 0.0
    assert entry.clamp_applied is True


def test_forecast_scaler_feature_names_match_manifest(container):
    for scaler in (
        container.models.solar_feature_scaler,
        container.models.wind_feature_scaler,
    ):
        assert list(scaler.feature_names_in_) == container.models.lstm_features
    for scaler in (
        container.models.solar_target_scaler,
        container.models.wind_target_scaler,
    ):
        assert list(scaler.feature_names_in_) == ["DailyGeneration_MU"]


def test_feature_dataset_does_not_contain_leaked_target_feature(container):
    assert "Generation_per_MW" not in container.data.features.columns
    assert "DailyGeneration_MU" in container.data.features.columns
    assert "Generation_per_MW" not in container.data.rf_features

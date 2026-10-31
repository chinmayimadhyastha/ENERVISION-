"""Central configuration for the ENERVISION backend.

All paths are resolved from the repository root (the parent directory of
``backend/``), never from the current shell directory.  No user-specific
absolute path is embedded anywhere in the codebase.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Environment variable {name} must be an integer, got {raw!r}") from exc


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:
    """Runtime configuration.

    Attributes may be overridden with the ``overrides`` mapping passed to the
    application factory.  Environment variables provide the normal deployment
    controls.
    """

    TARGET = "DailyGeneration_MU"
    TARGET_UNIT = "MU/day"
    FREQUENCY = "daily"
    DEFAULT_HORIZON = 3
    MAX_HORIZON = 7
    LSTM_SEQUENCE_LENGTH = 7
    RF_FEATURE_COUNT = 24
    LSTM_FEATURE_COUNT = 12

    WEATHER_FIELDS = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
    WEATHER_LAG_FIELDS = ["Temperature", "Humidity", "WindSpeed", "GHI"]

    DEFAULT_HISTORY_LIMIT = 30
    MAX_HISTORY_LIMIT = 365

    def __init__(self, overrides: dict | None = None) -> None:
        self.ENV = os.environ.get("ENV", os.environ.get("FLASK_ENV", "development")).strip().lower()
        self.DEBUG = _env_bool("FLASK_DEBUG", False)
        self.TESTING = False
        self.HOST = os.environ.get("HOST", "0.0.0.0")
        self.PORT = _env_int("PORT", 5000)
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

        default_origins = ["http://localhost:5173", "http://localhost:5174"]
        self.CORS_ORIGINS = _env_list("CORS_ORIGINS", default_origins)

        self.PROJECT_ROOT = PROJECT_ROOT
        self.DATA_DIR = PROJECT_ROOT / "data" / "final"
        self.MODELS_DIR = PROJECT_ROOT / "models"
        self.REPORTS_DIR = PROJECT_ROOT / "reports"

        self.MANIFEST_PATH = self.MODELS_DIR / "model_manifest.json"
        self.CANONICAL_DATA_PATH = self.DATA_DIR / "full_generation_weather_dataset.csv"
        self.WEATHER_DATA_PATH = self.DATA_DIR / "plant_weather_training_dataset.csv"
        self.FEATURE_DATA_PATH = self.DATA_DIR / "plant_features_dataset.csv"
        self.TRAIN_DATA_PATH = self.DATA_DIR / "plant_train.csv"
        self.TEST_DATA_PATH = self.DATA_DIR / "plant_test.csv"

        self.RF_MODEL_PATH = self.MODELS_DIR / "random_forest_model.pkl"
        self.SOLAR_MODEL_PATH = self.MODELS_DIR / "solar_lstm.keras"
        self.WIND_MODEL_PATH = self.MODELS_DIR / "wind_lstm.keras"
        self.SOLAR_FEATURE_SCALER_PATH = self.MODELS_DIR / "solar_scaler_features.joblib"
        self.SOLAR_TARGET_SCALER_PATH = self.MODELS_DIR / "solar_scaler_target.joblib"
        self.WIND_FEATURE_SCALER_PATH = self.MODELS_DIR / "wind_scaler_features.joblib"
        self.WIND_TARGET_SCALER_PATH = self.MODELS_DIR / "wind_scaler_target.joblib"

        self.RF_METRICS_PATH = self.REPORTS_DIR / "generation_metrics_leakage_free.csv"
        self.HISTORICAL_RF_METRICS_PATH = self.REPORTS_DIR / "generation_metrics.csv"
        self.LSTM_METRICS_PATH = self.REPORTS_DIR / "lstm_metrics.csv"
        self.FEATURE_IMPORTANCE_PATH = self.REPORTS_DIR / "generation_feature_importance.csv"

        # A real future-weather provider is deliberately not wired in.  The
        # weather service is the single extension point when one is added.
                # A real future-weather provider is configurable (e.g. open-meteo).
        self.FUTURE_WEATHER_PROVIDER = os.environ.get("FUTURE_WEATHER_PROVIDER", "unavailable")
        self.DATABASE_URL = os.environ.get("DATABASE_URL")
        self.REPO_ROOT = PROJECT_ROOT

        if overrides:
            for key, value in overrides.items():
                setattr(self, key, value)

        self._coerce_paths()
        self.validate()

    def _coerce_paths(self) -> None:
        path_attributes = [
            "PROJECT_ROOT",
            "DATA_DIR",
            "MODELS_DIR",
            "REPORTS_DIR",
            "MANIFEST_PATH",
            "CANONICAL_DATA_PATH",
            "WEATHER_DATA_PATH",
            "FEATURE_DATA_PATH",
            "TRAIN_DATA_PATH",
            "TEST_DATA_PATH",
            "RF_MODEL_PATH",
            "SOLAR_MODEL_PATH",
            "WIND_MODEL_PATH",
            "SOLAR_FEATURE_SCALER_PATH",
            "SOLAR_TARGET_SCALER_PATH",
            "WIND_FEATURE_SCALER_PATH",
            "WIND_TARGET_SCALER_PATH",
            "RF_METRICS_PATH",
            "HISTORICAL_RF_METRICS_PATH",
            "LSTM_METRICS_PATH",
            "FEATURE_IMPORTANCE_PATH",
        ]
        for attribute in path_attributes:
            value = getattr(self, attribute)
            if not isinstance(value, Path):
                setattr(self, attribute, Path(value))

    def validate(self) -> None:
        if self.FREQUENCY != "daily":
            raise ValueError("ENERVISION only supports daily forecasting.")
        if not 1 <= self.DEFAULT_HORIZON <= self.MAX_HORIZON:
            raise ValueError("DEFAULT_HORIZON must be between 1 and MAX_HORIZON.")
        if self.MAX_HORIZON < 1:
            raise ValueError("MAX_HORIZON must be positive.")
        if not self.CORS_ORIGINS:
            raise ValueError("At least one CORS origin must be configured.")
        if not 1 <= self.PORT <= 65535:
            raise ValueError(f"PORT must be a valid TCP port, got {self.PORT}")

    def artifact_paths(self) -> dict[str, Path]:
        """Required model artefacts, used by startup validation and health."""
        return {
            "model_manifest": self.MANIFEST_PATH,
            "random_forest_model": self.RF_MODEL_PATH,
            "solar_lstm": self.SOLAR_MODEL_PATH,
            "wind_lstm": self.WIND_MODEL_PATH,
            "solar_scaler_features": self.SOLAR_FEATURE_SCALER_PATH,
            "solar_scaler_target": self.SOLAR_TARGET_SCALER_PATH,
            "wind_scaler_features": self.WIND_FEATURE_SCALER_PATH,
            "wind_scaler_target": self.WIND_TARGET_SCALER_PATH,
        }

    def data_paths(self) -> dict[str, Path]:
        return {
            "canonical_dataset": self.CANONICAL_DATA_PATH,
            "weather_dataset": self.WEATHER_DATA_PATH,
            "feature_dataset": self.FEATURE_DATA_PATH,
            "rf_metrics": self.RF_METRICS_PATH,
            "historical_rf_metrics": self.HISTORICAL_RF_METRICS_PATH,
            "lstm_metrics": self.LSTM_METRICS_PATH,
            "feature_importance": self.FEATURE_IMPORTANCE_PATH,
        }

    def to_public_dict(self) -> dict:
        return {
            "environment": self.ENV,
            "debug": self.DEBUG,
            "testing": self.TESTING,
            "host": self.HOST,
            "port": self.PORT,
            "cors_origins": list(self.CORS_ORIGINS),
            "forecasting_contract": {
                "frequency": self.FREQUENCY,
                "target": self.TARGET,
                "unit": self.TARGET_UNIT,
                "horizon": "future days",
                "default_horizon_days": self.DEFAULT_HORIZON,
                "max_horizon_days": self.MAX_HORIZON,
                "hourly_forecasting": False,
            },
            "future_weather_provider": self.FUTURE_WEATHER_PROVIDER,
        }

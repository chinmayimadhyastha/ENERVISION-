from __future__ import annotations

from backend.db.database import Database
from backend.db.seed import seed_database
"""Application service container.

Everything expensive is constructed and loaded once per process: the manifest,
the datasets, the Random Forest, both LSTMs, all four scalers and the feature
builder.  Route handlers never reload artifacts.
"""


import logging
import time
from datetime import datetime, timezone

from backend.services.analytics_service import AnalyticsService
from backend.services.data_service import DataService
from backend.services.explanation_service import ExplanationService
from backend.services.feature_builder import FeatureBuilder
from backend.services.forecast_service import ForecastService
from backend.services.model_report_service import ModelReportService
from backend.services.model_service import ModelService
from backend.services.plant_service import PlantService
from backend.services.weather_service import WeatherService
from backend.utils.artifacts import load_manifest, validate_manifest


class ServiceContainer:
    def __init__(self, config) -> None:
        self.config = config
        self.logger = logging.getLogger("enervision")
        self.started_at = time.perf_counter()
        self.loaded_at: datetime | None = None
        self.load_seconds: float | None = None
        self.loaded = False

        self.manifest = load_manifest(config.MANIFEST_PATH)
        self.contracts = validate_manifest(self.manifest, config)
        self.db = Database(getattr(config, "DATABASE_URL", None), getattr(config, "REPO_ROOT", getattr(config, "PROJECT_ROOT", None)))

        self.data = DataService(config, self.contracts, logging.getLogger("enervision.data"))
        self.models = ModelService(
            config, self.contracts, logging.getLogger("enervision.models")
        )
        self.feature_builder = FeatureBuilder(
            self.contracts["rf_features"],
            self.contracts["lstm_features"],
            self.contracts["lstm_column_map"],
        )
        self.weather = WeatherService(
            config, self.data, logging.getLogger("enervision.weather")
        )
        self.plants = PlantService(config, self.data, self.weather)
        self.forecast = ForecastService(
            config,
            self.data,
            self.models,
            self.weather,
            self.feature_builder,
            logging.getLogger("enervision.forecast"),
        )
        self.analytics = AnalyticsService(
            config, self.data, self.models, self.weather
        )
        self.reports = ModelReportService(config, self.contracts)
        self.explanation = ExplanationService(
            config,
            self.data,
            self.models,
            self.feature_builder,
            logging.getLogger("enervision.explanation"),
        )

    def load(self) -> None:
        started = time.perf_counter()
        self.logger.info("Loading canonical datasets and validating contracts...")
        self.data.load()
        self.logger.info("Loading production model artifacts...")
        self.models.load()
        self.load_seconds = round(time.perf_counter() - started, 3)
        self.loaded_at = datetime.now(timezone.utc)
        self.loaded = True
        self.logger.info(
            "ENERVISION backend ready in %.2fs (37 plants expected; see data summary).",
            self.load_seconds,
        )

    def health(self) -> dict:
        report_status = {
            "current_metrics": self.config.RF_METRICS_PATH.exists(),
            "historical_metrics": self.config.HISTORICAL_RF_METRICS_PATH.exists(),
            "lstm_metrics": self.config.LSTM_METRICS_PATH.exists(),
            "feature_importance": self.config.FEATURE_IMPORTANCE_PATH.exists(),
        }
        return {
            "status": "ok" if self.loaded else "starting",
            "service": "ENERVISION daily forecasting API",
            "api_version": "1.0.0",
            "loaded": self.loaded,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "startup_duration_seconds": self.load_seconds,
            "forecasting_contract": self.config.to_public_dict()[
                "forecasting_contract"
            ],
            "models": self.models.status(),
            "data": self.data.dataset_summary(),
            "future_weather": self.weather.availability_summary(),
            "reports": report_status,
            "limitations": [
                "No future weather provider is integrated; no future forecast is "
                "fabricated.",
                "All outputs are daily (MU/day). No hourly output exists.",
                "Confidence values are null because no calibrated probabilistic model "
                "exists.",
            ],
        }

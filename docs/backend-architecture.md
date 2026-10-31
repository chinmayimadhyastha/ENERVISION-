# ENERVISION — Backend Architecture & System Design

This document details the architectural layers, data flows, machine learning inference contracts, database schema, and external integrations for the ENERVISION backend.

---

## 1. System Architecture Overview

```mermaid
flowchart TD
    subgraph ClientLayer ["Frontend & Client Layer (Port 5173 / 5174)"]
        UI["React / Vite Dashboard (Dashboard, Forecast, Plants, Analytics, Models)"]
        ApiClient["API Client (frontend/src/services/api.js)"]
        UI --> ApiClient
    end

    subgraph ApiLayer ["API & Routing Layer (Flask 3.1 REST API, Port 5000)"]
        HealthRoute["GET /api/health"]
        PlantsRoute["GET /api/plants\nGET /api/plants/{id}"]
        HistoryRoute["GET /api/generation-history\nGET /api/generation/{id}"]
        WeatherRoute["GET /api/weather\nGET /api/weather/{id}"]
        ForecastRoute["GET /api/forecast\nPOST /api/forecast\nGET /api/forecast/{id}"]
        ModelsRoute["GET /api/models\nGET /api/models/{id}\nGET /api/model-performance\nGET /api/feature-importance\nGET /api/explainability/{id}"]
        DashboardRoute["GET /api/dashboard"]
        AnalyticsRoute["GET /api/analytics"]
        
        ApiClient -->|HTTP / CORS| ApiLayer
    end

    subgraph ServiceLayer ["Service Container & Domain Logic (container.py)"]
        ForecastSvc["ForecastService\n(Multi-day Orchestration & Gating)"]
        PlantSvc["PlantService\n(Catalogue, Lat/Lon, Generation)"]
        WeatherSvc["WeatherService\n(Historical & Live Open-Meteo)"]
        AnalyticsSvc["AnalyticsService\n(Descriptive Fleet Aggregations)"]
        ReportSvc["ModelReportService\n(Metrics Provenance & Importance)"]
        FeatureBld["FeatureBuilder\n(24 RF Features / 12 LSTM Sequence)"]
        DataSvc["DataService\n(In-Memory Canonical Data & Indexing)"]

        ForecastRoute --> ForecastSvc
        PlantsRoute --> PlantSvc
        HistoryRoute --> PlantSvc
        WeatherRoute --> WeatherSvc
        ModelsRoute --> ReportSvc
        ModelsRoute --> ForecastSvc
        DashboardRoute --> AnalyticsSvc
        AnalyticsRoute --> AnalyticsSvc

        ForecastSvc --> FeatureBld
        ForecastSvc --> DataSvc
        PlantSvc --> DataSvc
        WeatherSvc --> DataSvc
        AnalyticsSvc --> DataSvc
    end

    subgraph MLLayer ["Machine Learning Layer (Frozen Artifacts)"]
        RFModel["Random Forest Regressor\n(24 features, leakage-free, 554 MB)"]
        SolarLSTM["Solar LSTM Model\n(Sequence [7, 12] -> [1], 293 KB)"]
        WindLSTM["Wind LSTM Model\n(Sequence [7, 12] -> [1], 106 KB)"]
        Scalers["StandardScalers\n(Solar & Wind Feature/Target Scalers)"]
        ConfidenceEst["Confidence & Uncertainty Estimator\n(Ensemble Quantiles & Test Residuals)"]
        Explainer["Prediction Feature Contributor\n(Tree-Path Decomposition)"]

        FeatureBld --> RFModel
        FeatureBld --> Scalers
        Scalers --> SolarLSTM
        Scalers --> WindLSTM
        RFModel --> ConfidenceEst
        RFModel --> Explainer
        SolarLSTM --> ConfidenceEst
        WindLSTM --> ConfidenceEst
    end

    subgraph StorageLayer ["Persistence & External Services Layer"]
        RelationalDB[("SQLAlchemy Relational Database\n(SQLite / PostgreSQL)\nplants, weather_observations,\ngeneration_records, forecasts,\npredictions, models_registry")]
        CanonicalCSVs[("Canonical CSV Datasets\nfull_generation_weather_dataset.csv\nplant_weather_training_dataset.csv\nplant_features_dataset.csv")]
        OpenMeteo["Open-Meteo Live API\n(7-14 Day Future Forecast Weather)"]
        
        DataSvc --> CanonicalCSVs
        ForecastSvc --> RelationalDB
        WeatherSvc --> OpenMeteo
        ContainerInit["Database Seeder\n(seed.py)"] --> RelationalDB
        CanonicalCSVs --> ContainerInit
    end
```

---

## 2. Layer Descriptions

### 1. API & Routing Layer
- **Framework:** Flask 3.1 with Flask-CORS.
- **Serialization & Error Envelope:** All responses are structured JSON conforming to `API_CONTRACT.md`.
- **CORS:** Restricted to `http://localhost:5173` and `http://localhost:5174` by default (configurable via `CORS_ORIGINS`).
- **Endpoints:**
  - `GET /api/health`: Health, readiness, data summary, model status.
  - `GET /api/plants`, `GET /api/plants/<plant_id>`: Plant catalogue, location, capacity.
  - `GET /api/generation-history`, `GET /api/generation/<plant_id>`: Historical observed generation.
  - `GET /api/weather`, `GET /api/weather/<plant_id>`: Observed historical weather.
  - `GET /api/forecast`, `POST /api/forecast`, `GET /api/forecast/<plant_id>`: Daily forecast generation with optional confidence (`include_confidence=true`) and explainability (`include_explanation=true`).
  - `GET /api/models`, `GET /api/models/<model_id>`: Model registry and metadata.
  - `GET /api/model-performance`: Verified evaluation metrics (MAE, RMSE, R²).
  - `GET /api/feature-importance`: Gini impurity feature importance.
  - `GET /api/explainability/<plant_id>`: Local decision tree feature contributions.
  - `GET /api/dashboard`: Aggregated fleet metrics for latest observed date.
  - `GET /api/analytics`: Descriptive generation analytics across plant, type, or fleet.

### 2. Service Layer
- **Container (`container.py`):** Singleton dependency injection container. Datasets, trained ML models, scalers, and database connections are initialized once at startup.
- **Forecast Service (`forecast_service.py`):** Orchestrates multi-day (1–7 day) daily forecasts. Enforces historical minimum requirement (7 preceding days) and gates on weather availability.
- **Weather Service (`weather_service.py`):** Accesses cleaned historical weather (`plant_weather_training_dataset.csv`). Provides `OpenMeteoWeatherProvider` for real future weather forecasts based on plant latitude and longitude with in-memory caching.
- **Plant Service (`plant_service.py`):** Resolves plant identities, manages coordinates, and aggregates recent generation windows.
- **Data Service (`data_service.py`):** Loads canonical datasets into memory, validates data integrity, and generates deterministic slugs for plant IDs.

### 3. Machine Learning Layer
- **Random Forest (`models/random_forest_model.pkl`):**
  - Algorithm: scikit-learn 1.6.1 `RandomForestRegressor` (300 estimators, max_features="sqrt").
  - Features: 24 strictly leakage-free features (Generation lags 1/2/3/7, Rolling means 3/7, Weather lags, Calendar cyclic terms).
  - Target: `DailyGeneration_MU` (MU/day).
- **LSTMs (`models/solar_lstm.keras`, `models/wind_lstm.keras`):**
  - Architecture: Keras 3.10 / TensorFlow sequential LSTM with input shape `(7, 12)`.
  - Normalization: 4 fitted StandardScaler instances (`solar_scaler_features`, `solar_scaler_target`, `wind_scaler_features`, `wind_scaler_target`).
- **Confidence & Uncertainty:**
  - Random Forest: Empirical quantile distribution across 100 decision trees (80% and 95% confidence intervals, standard deviation).
  - LSTMs: Residual prediction interval based on verified test-set RMSE (Solar RMSE: 0.2346 MU/day; Wind RMSE: 1.0040 MU/day).
- **Explainability:**
  - Local tree-path decomposition: Traces decision paths across all estimators to compute exact feature contribution (magnitude and positive/negative direction).

### 4. Database Layer (SQLAlchemy)
- **Engine:** SQLAlchemy 2.0 with connection pooling and session management.
- **Storage:** SQLite file at `data/enervision.db` by default; PostgreSQL compatible via `DATABASE_URL`.
- **Entities:**
  - `plants`: Plant identifier, name, type, district, capacity, coordinates, date boundaries.
  - `weather_observations`: Historical and forecast daily weather observations per plant.
  - `generation_records`: Historical daily generation observations.
  - `forecast_records`: Stored forecast requests (plant, model, horizon, base date).
  - `prediction_items`: Individual daily predictions (date, served value, raw value, confidence interval).
  - `prediction_explanations`: Top feature contributions per prediction.
  - `models_registry`: Registered models, algorithms, features, and evaluation metrics.

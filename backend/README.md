# ENERVISION Backend — Daily Forecasting REST API

Flask REST API serving the frozen ENERVISION **daily** renewable-generation
forecasting artifacts. It exposes real plant metadata, observed daily
generation and weather, daily model forecasts, model metrics and descriptive
analytics.

This backend is a serving layer only. It does not train, retrain or tune models,
and it does not modify the frontend.

---

## 1. Scope and non-negotiable forecasting contract

| Item | Value |
| --- | --- |
| Forecast frequency | **daily** |
| Target | `DailyGeneration_MU` |
| Unit | **MU/day** |
| Horizon | future **days** (1–7, default 3) |
| Hourly forecasting | **not supported and not implemented** |
| Confidence intervals | **none**; API returns `confidence: null` |
| Future weather provider | **not integrated**; requests needing it return `status: "weather_required"` |

The artifacts contain no hourly model, no hourly training data and no future
weather feed. The API therefore never:

- produces hourly timestamps, hourly values or `+3H/+6H/+12H/+24H` labels;
- interpolates daily values into finer resolution;
- reuses historical weather as future weather;
- silently falls back to mock, demo or synthetic data;
- invents confidence, SHAP values or metrics.

All data returned is loaded from committed CSV/report files and all predictions
come from the committed model artifacts.

---

## 2. Frozen artifacts consumed

Loaded once at process startup from the repository root:

| Artifact | Path | Contract |
| --- | --- | --- |
| Manifest | `models/model_manifest.json` | feature lists, model metadata, metrics provenance |
| Random Forest | `models/random_forest_model.pkl` | 24 features, target-free |
| Solar LSTM | `models/solar_lstm.keras` | input `(7, 12)`, output `(1,)` |
| Wind LSTM | `models/wind_lstm.keras` | input `(7, 12)`, output `(1,)` |
| Solar scalers | `models/solar_scaler_features.joblib`, `models/solar_scaler_target.joblib` | 12 / 1 features |
| Wind scalers | `models/wind_scaler_features.joblib`, `models/wind_scaler_target.joblib` | 12 / 1 features |
| Canonical data | `data/final/full_generation_weather_dataset.csv` | observed generation + metadata |
| Cleaned weather | `data/final/plant_weather_training_dataset.csv` | observed/imputed weather, no `-999` |
| Feature data | `data/final/plant_features_dataset.csv` | engineered daily features |
| Current RF metrics | `reports/generation_metrics_leakage_free.csv` | 24-feature model |
| Historical RF metrics | `reports/generation_metrics.csv` | leaked 25-feature model, provenance only |
| LSTM metrics | `reports/lstm_metrics.csv` | committed LSTM actuals |
| Feature importance | `reports/generation_feature_importance.csv` | 24-feature impurity importance |

Validation at startup covers file presence, manifest agreement on feature names
and order, scikit-learn `n_features_in_`, scaler feature names, Keras input/output
shapes, required dataset columns and absence of leaked features. If anything is
missing or inconsistent the process **fails to start** with a clear
`ArtifactError`; it never degrades to a mock model.

---

## 3. Model contracts

### Random Forest (`random_forest_daily`)

- Exactly **24** features, taken from the manifest in manifest order.
- `Generation_per_MW` was removed because it leaked the target; it is never
  recreated, recomputed or used.
- The prediction-day `DailyGeneration_MU` is never an input. It exists in the
  dataset only as the training label and evaluation target.
- Requires weather for **every** forecast day (`Temperature`, `Humidity`,
  `WindSpeed`, `GHI`, `Pressure`), plus calendar, capacity and generation
  lag/rolling features derived from strictly preceding observations.
- Calendar features (`Year`, `Month`, `DayOfYear`, `DayOfWeek`, cyclic terms) are
  derived from the forecast date. Generation lags/rolling windows carry forward
  from observed history and previously predicted days.

### LSTMs (`solar_lstm_daily`, `wind_lstm_daily`)

- Exactly **12** features and a sequence length of **7**.
- Manifest column mapping is honoured:
  `Lagged_Generation → Generation_lag_1`,
  `Rolling_Generation_7 → Generation_roll_7`.
- The model and scalers are selected by plant type: Solar uses the Solar LSTM
  and Solar scalers; Wind uses the Wind LSTM and Wind scalers.
- The training/inference convention is seven **preceding** rows predicting the
  next day. Target-day weather is therefore **not** an input.
- Horizon 1 needs no future weather. Horizon > 1 needs weather for the
  intermediate predicted days so their features can be built, but still not for
  the final target day.

### Physical post-processing

Daily generation cannot be negative. The serving layer applies:

```
prediction = max(raw_prediction, 0.0)
```

The unmodified model output is preserved as `raw_prediction`, and
`clamp_applied` / `post_processing` explain exactly which dates were affected.
This is deterministic post-processing, not a new model.

### `auto` selection

`model=auto` (the default) selects the type-specific LSTM:

- Solar plant → `solar_lstm_daily`
- Wind plant → `wind_lstm_daily`

`model=rf` always selects the Random Forest. `model=lstm` selects the LSTM that
matches the plant type.

---

## 4. Setup

Validated with Python 3.12.10 on Windows. Run from the repository root.

```powershell
# 1. Create and activate an environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install the pinned dependencies
python -m pip install -r requirements.txt
```

`requirements.txt` pins `scikit-learn==1.6.1` and `keras==3.10.0` because the
committed artifacts were produced with those versions. Do not upgrade them
blindly.

### Start the API

```powershell
python backend/app.py
```

Defaults: host `0.0.0.0`, port `5000`, debug off. Startup loads the data and all
models, which typically takes 20–30 seconds on a first TensorFlow load.

Flask CLI alternative:

```powershell
flask --app backend.app_factory:create_app run --host 0.0.0.0 --port 5000
```

Production WSGI entry point:

```text
backend.wsgi:app
```

Environment overrides: `HOST`, `PORT`, `FLASK_DEBUG`, `LOG_LEVEL`, `CORS_ORIGINS`
(comma-separated), `ENV`.

### CORS

Only the two local frontends are allowed:

- `http://localhost:5173`
- `http://localhost:5174`

Methods `GET` and `OPTIONS` are allowed on `/api/*`.

---

## 5. Architecture

```text
backend/
  app.py                    # python backend/app.py entry point
  app_factory.py            # create_app(), CORS, logging, security headers
  wsgi.py                   # WSGI app object
  config.py                 # paths, ports, horizon bounds, daily contract
  container.py              # loads data/models once; exposes services
  schemas/
    forecast_schema.py      # forecast response serialization
  routes/
    health.py plants.py history.py weather.py
    forecasts.py models.py dashboard.py analytics.py
  services/
    data_service.py         # once-only data load, validation, plant IDs
    model_service.py        # artifact loading, RF/LSTM inference, clamp
    feature_builder.py      # exact daily feature vectors
    forecast_service.py     # RF/LSTM orchestration, weather gate
    weather_service.py      # historical weather + provider extension point
    plant_service.py        # catalogue, detail, generation history
    analytics_service.py    # dashboard + descriptive analytics
    model_report_service.py # metrics separation + impurity importance
  utils/
    errors.py validation.py serialization.py artifacts.py
  tests/                    # pytest suite against real artifacts/data
```

Request flow: `route → validation → service → loaded artifacts/data →
JSON serialization`. No route loads a model or CSV, and no service mutates the
loaded datasets.

### Plant IDs

Plant IDs are deterministic slugs generated from the real `PlantName`
(e.g. `KOPPAL_TPSAURYA_S → koppal-tpsaurya-s`). They are stable across restarts.
Collisions are resolved deterministically using type, district and capacity.
Frontend synthetic IDs are never used.

### Weather source

Weather responses and inference use the cleaned/imputed
`data/final/plant_weather_training_dataset.csv`, because the canonical dataset
still contains `-999` sentinel values. Provenance is exposed per row via
`weather_imputed` and `source_sentinel_count`. Missing calendar dates are never
interpolated or fabricated.

---

## 6. Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | readiness, contracts, loaded models, data summary |
| GET | `/api/plants` | plant catalogue, optional `type` / `district` filters |
| GET | `/api/plants/<plant_id>` | plant metadata, latest and recent daily generation |
| GET | `/api/generation-history` | observed daily generation, plant/type/fleet scope |
| GET | `/api/weather` | observed historical daily weather |
| GET | `/api/forecast` | daily forecast (`rf`, `lstm`, `auto`) |
| GET | `/api/model-performance` | current and historical metrics, separated |
| GET | `/api/feature-importance` | Random Forest impurity importance |
| GET | `/api/dashboard` | fleet summary for the latest observed date |
| GET | `/api/analytics` | descriptive daily analytics by plant/type/fleet |

Full parameters, payloads and status codes are in
[`API_CONTRACT.md`](API_CONTRACT.md).

---

## 7. Tests

The suite uses the real committed artifacts and real data; there are no model
mocks.

```powershell
python -m pytest backend/tests -q
```

Current result: **65 passed**. Coverage includes:

- all 10 endpoints and their response contracts;
- validation errors (missing/invalid `plant_id`, model, horizon, dates, ranges);
- hourly-horizon rejection such as `horizon=3h`;
- missing future weather returning `weather_required` with exact dates/inputs;
- insufficient LSTM history returning a structured state;
- RF target-free inference with exact 24-feature parity against the dataset;
- both LSTM `(7, 12)` contracts, scaler names and type-specific selection;
- wind negative raw value preserved and served as `0.0`;
- CORS allow-list and preflight;
- structured 400/404/405/422/500/503 errors with no tracebacks.

Tests may install a test-only observed-weather provider to verify RF/LSTM
inference. The production application never installs it and keeps the future
weather provider unavailable.

---

## 8. Known limitations and out of scope

1. **No future weather provider.** RF forecasts and LSTM horizons > 1 return
   `status: "weather_required"` with the exact missing dates and inputs. Only a
   one-day LSTM forecast can succeed in production, because it needs no future
   weather.
2. **Daily only.** No hourly data, model, endpoint or transformation exists.
3. **No calibrated confidence.** `confidence` is always `null`.
4. **No SHAP.** Feature importance is Random Forest mean-decrease-in-impurity;
   it is explicitly labelled `random_forest_impurity`.
5. **Historical 25-feature RF metrics are not comparable** to the current
   24-feature model. They are exposed only as provenance (`leakage_affected`,
   `usage: "provenance_only"`).
6. **LSTM regenerated reference metrics** are reported separately from the
   committed actuals and are not a reproduction of them.
7. **Stale plants.** 11 of 37 plants have an older last observation; the latest
   fleet date (2026-08-05) has 26 reporting plants. Dashboard fields state this
   explicitly rather than filling gaps.
8. **Frontend integration is out of scope** for this backend change.

# ENERVISION API Contract

Base URL: `http://localhost:5000`

All endpoints are **read-only** (`GET`, plus `OPTIONS` preflight) and return
`application/json`. Responses are `Cache-Control: no-store` and
`X-Content-Type-Options: nosniff`.

The API is a **daily** forecasting API:

- frequency: `daily`
- target: `DailyGeneration_MU`
- unit: **MU/day**
- horizon: number of **future days** (1–7, default 3)

No endpoint returns hourly data, hourly timestamps, synthetic finer-resolution
values or `+3H/+6H/+12H/+24H` labels.

---

## 1. Common conventions

### Dates

- Dates are ISO `YYYY-MM-DD` calendar days.
- `start_date` / `end_date` are inclusive.
- A missing `end_date` means “through the plant's last observed date”.
- Observations are returned as stored. Missing calendar days are **not**
  interpolated or fabricated; coverage objects report the gaps.

### Valid plant IDs

Plant IDs are deterministic lowercase slugs generated from the real
`PlantName`, e.g. `KOPPAL_TPSAURYA_S → koppal-tpsaurya-s`. They are case
insensitive on input and stable across restarts.

### Units

| Field | Unit |
| --- | --- |
| `generation_mu`, `total_generation_mu`, `prediction` | MU/day |
| `capacity_mw` | MW |
| `temperature` | °C |
| `humidity` | % |
| `wind_speed` | m/s |
| `ghi` | kWh/m²/day |
| `pressure` | kPa |

### CORS

Allowed origins only:

- `http://localhost:5173`
- `http://localhost:5174`

### Error envelope

Every non-2xx response uses:

```json
{
  "error": {
    "code": "INVALID_HORIZON",
    "message": "Query parameter 'horizon' must be between 1 and 7 future days.",
    "details": {
      "parameter": "horizon",
      "minimum": 1,
      "maximum": 7
    }
  }
}
```

`details` is omitted only when there is nothing useful to add. Internal
exception text and tracebacks are never returned.

### Error codes

| HTTP | `error.code` | Meaning |
| --- | --- | --- |
| 400 | `MISSING_PARAMETER` | A required query parameter is absent or empty |
| 400 | `INVALID_PARAMETER` | Malformed value (e.g. non-integer limit) |
| 400 | `INVALID_MODEL` | `model` not in `rf`, `lstm`, `auto` |
| 400 | `INVALID_HORIZON` | Horizon non-integer, `0`, negative, `> 7`, or hourly (`3h`) |
| 400 | `INVALID_TYPE` | `type` not `solar` / `wind` |
| 400 | `INVALID_DATE` | Not a valid `YYYY-MM-DD` calendar date |
| 400 | `INVALID_DATE_RANGE` | `start_date` is after `end_date` |
| 400 | `INVALID_BASE_DATE` | `base_date` is after the plant's last observed date |
| 400 | `FILTER_MISMATCH` | `plant_id` and `type` refer to different plant types |
| 404 | `NOT_FOUND` | Unknown route |
| 404 | `PLANT_NOT_FOUND` | Unknown `plant_id` |
| 405 | `METHOD_NOT_ALLOWED` | Non-GET/OPTIONS method |
| 422 | `FUTURE_WEATHER_UNAVAILABLE` | `/api/weather` range reaches beyond observed weather |
| 500 | `INTERNAL_ERROR` | Unexpected server error (details logged server-side) |
| 503 | `MODEL_SERVICE_UNAVAILABLE` | Models not loaded |
| 503 | `MODEL_INFERENCE_FAILED` | Inference failed |
| 503 | `REPORT_UNAVAILABLE` | Required report file missing |
| 503 | `REPORT_INVALID` | Report content violates the contract |
| 503 | `WEATHER_PROVIDER_ERROR` | Future-weather provider failed |
| 503 | `WEATHER_PROVIDER_INVALID` | Future-weather provider returned invalid data |

---

## 2. `GET /api/health`

Readiness and contract summary. HTTP 200 when the app has loaded.

**Response (abridged):**

```json
{
  "status": "ok",
  "service": "ENERVISION daily forecasting API",
  "api_version": "1.0.0",
  "loaded": true,
  "loaded_at": "2026-10-26T11:19:20+00:00",
  "startup_duration_seconds": 26.756,
  "forecasting_contract": {
    "frequency": "daily",
    "target": "DailyGeneration_MU",
    "unit": "MU/day",
    "horizon": "future days",
    "default_horizon_days": 3,
    "max_horizon_days": 7,
    "hourly_forecasting": false
  },
  "models": {
    "random_forest": "loaded",
    "solar_lstm": "loaded",
    "wind_lstm": "loaded",
    "solar_feature_scaler": "loaded",
    "solar_target_scaler": "loaded",
    "wind_feature_scaler": "loaded",
    "wind_target_scaler": "loaded"
  },
  "data": {
    "rows": 29369,
    "plants": 37,
    "feature_rows": 29110,
    "date_range": {"start": "2020-05-28", "end": "2026-08-05"},
    "type_counts": {"Solar": 30, "Wind": 7},
    "weather_fields": ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"],
    "cleaned_weather_dataset": "plant_weather_training_dataset.csv"
  },
  "future_weather": {
    "future_weather_available": false,
    "provider": "unavailable",
    "status": "unavailable",
    "message": "No future weather provider is integrated. ..."
  },
  "reports": {
    "current_metrics": true,
    "historical_metrics": true,
    "lstm_metrics": true,
    "feature_importance": true
  },
  "limitations": ["..."]
}
```

---

## 3. `GET /api/plants`

Plant catalogue with latest observed capacity.

**Query parameters**

| Name | Required | Values | Notes |
| --- | --- | --- | --- |
| `type` | no | `solar`, `wind` | case insensitive; invalid → 400 `INVALID_TYPE` |
| `district` | no | text, e.g. `Koppal` | substring/exact comparison from real data |

**Response:**

```json
{
  "count": 30,
  "filters": {"type": "Solar", "district": null},
  "capacity_basis": "latest observed Capacity_MW per plant",
  "plants": [
    {
      "plant_id": "koppal-tpsaurya-s",
      "plant_name": "KOPPAL_TPSAURYA_S",
      "type": "Solar",
      "district": "Koppal",
      "state": "Karnataka",
      "owner": "Private IPP",
      "latitude": 15.574824,
      "longitude": 76.311849,
      "capacity_mw": 131.0,
      "commission_date": null,
      "first_observed_date": "2026-04-24",
      "last_observed_date": "2026-08-05",
      "observations": 104,
      "latest_generation_mu": 0.79,
      "latest_generation_date": "2026-08-05",
      "has_coordinates": true
    }
  ]
}
```

`latitude` / `longitude` are `null` when the source has no coordinates. 15 of
37 plants currently have coordinates.

Fleet totals: 37 plants (30 Solar, 7 Wind), 4,752.0 MW
(Solar 3,280.0 / Wind 1,472.0).

---

## 4. `GET /api/plants/<plant_id>`

Plant metadata, latest generation, a recent daily history window and observed
weather context.

**Path parameter:** `plant_id` (case insensitive)

**Query parameters**

| Name | Required | Default | Bounds |
| --- | --- | --- | --- |
| `history_limit` | no | 30 | 1–365 |

**Response (abridged):**

```json
{
  "plant": { "...": "same shape as /api/plants entry" },
  "latest_generation": {
    "date": "2026-08-05",
    "generation_mu": 0.79,
    "unit": "MU/day",
    "frequency": "daily"
  },
  "recent_generation": {
    "count": 2,
    "limit": 2,
    "frequency": "daily",
    "unit": "MU/day",
    "data": [
      {"date": "2026-08-04", "generation_mu": 0.7, "unit": "MU/day"},
      {"date": "2026-08-05", "generation_mu": 0.79, "unit": "MU/day"}
    ]
  },
  "weather_context": {
    "date": "2026-08-05",
    "weather_type": "historical",
    "is_forecast": false,
    "temperature": 24.74,
    "humidity": 84.61,
    "wind_speed": 4.01,
    "ghi": 4.1808,
    "pressure": 94.62,
    "source": "cleaned/imputed observed weather"
  },
  "forecast_capability": {
    "frequency": "daily",
    "unit": "MU/day",
    "horizon_default_days": 3,
    "horizon_max_days": 7,
    "future_weather": { "future_weather_available": false, "provider": "unavailable" },
    "random_forest": {
      "available": false,
      "reason": "The Random Forest requires weather for every forecast day."
    },
    "lstm": {
      "one_day_horizon_available": true,
      "multi_day_horizon_available": false,
      "reason": "A one-day LSTM forecast uses only the seven preceding observed rows ..."
    },
    "endpoint": "/api/forecast?plant_id=koppal-tpsaurya-s"
  }
}
```

Errors: `PLANT_NOT_FOUND` 404, `INVALID_PARAMETER` 400.

---

## 5. `GET /api/generation-history`

Observed daily generation, optionally plant-scoped or type-scoped.

**Query parameters**

| Name | Required | Notes |
| --- | --- | --- |
| `plant_id` | no | plant scope |
| `type` | no | `solar` / `wind` type scope |
| `start_date` | no | inclusive |
| `end_date` | no | inclusive |

If both are omitted, fleet scope is used. `plant_id` and `type` must agree; a
mismatch returns 400 `FILTER_MISMATCH`.

**Scope values:** `plant`, `type`, `fleet`.

**Plant-scope response:**

```json
{
  "scope": "plant",
  "plant_id": "koppal-tpsaurya-s",
  "plant_name": "KOPPAL_TPSAURYA_S",
  "type": "Solar",
  "frequency": "daily",
  "unit": "MU/day",
  "target": "DailyGeneration_MU",
  "aggregation": "observed_plant_daily_generation",
  "requested_range": {"start": "2026-08-04", "end": "2026-08-05"},
  "available_range": {"start": "2026-04-24", "end": "2026-08-05"},
  "coverage": {
    "start": "2026-08-04",
    "end": "2026-08-05",
    "calendar_days": 2,
    "observations": 2,
    "missing_calendar_days": 0
  },
  "summary": {
    "total_generation_mu": 1.49,
    "mean_daily_generation_mu": 0.745,
    "min_daily_generation_mu": 0.7,
    "max_daily_generation_mu": 0.79,
    "observations": 2
  },
  "count": 2,
  "data": [
    {"date": "2026-08-04", "generation_mu": 0.7, "unit": "MU/day"},
    {"date": "2026-08-05", "generation_mu": 0.79, "unit": "MU/day"}
  ],
  "notes": ["..."]
}
```

Type/fleet scope returns the same envelope with `scope`, `type`, and daily rows
containing `total_generation_mu`, `solar_generation_mu`, `wind_generation_mu`
and `reporting_plants`. `aggregation` is
`sum_of_observed_plant_generation_by_date`; missing plants are not filled.

---

## 6. `GET /api/weather`

Observed historical daily weather for one plant. **Historical only.**

**Query parameters**

| Name | Required | Notes |
| --- | --- | --- |
| `plant_id` | **yes** | missing → 400 `MISSING_PARAMETER` |
| `start_date` | no | inclusive |
| `end_date` | no | inclusive |

**Success response:**

```json
{
  "plant_id": "koppal-tpsaurya-s",
  "plant_name": "KOPPAL_TPSAURYA_S",
  "type": "Solar",
  "weather_type": "historical",
  "is_forecast": false,
  "source": "data/final/plant_weather_training_dataset.csv (cleaned/imputed observed weather)",
  "units": {
    "temperature": "degC",
    "humidity": "%",
    "wind_speed": "m/s",
    "ghi": "kWh/m2/day",
    "pressure": "kPa"
  },
  "available_range": {"start": "2026-04-24", "end": "2026-08-05"},
  "requested_range": {"start": "2026-08-04", "end": "2026-08-05"},
  "effective_range": {"start": "2026-08-04", "end": "2026-08-05", "note": "..."},
  "coverage": {
    "requested_calendar_days": 2,
    "returned_observations": 2,
    "missing_calendar_days": 0
  },
  "future_weather": {
    "available": false,
    "is_forecast": false,
    "provider": "unavailable",
    "message": "No future weather provider is integrated. This response contains observed historical weather only; ...",
    "available_through": "2026-08-05"
  },
  "count": 2,
  "data": [
    {
      "date": "2026-08-04",
      "temperature": 24.74,
      "humidity": 84.61,
      "wind_speed": 4.01,
      "ghi": 4.1808,
      "pressure": 94.62,
      "weather_imputed": true,
      "source_sentinel_count": 5
    }
  ],
  "notes": ["..."]
}
```

`weather_imputed` and `source_sentinel_count` expose provenance because the
cleaned dataset imputes some source `-999` sentinels. No `-999` value is
returned.

**Future range → HTTP 422**

If the requested range extends beyond the plant's last observed weather date,
the entire request fails rather than being silently truncated:

```json
{
  "error": {
    "code": "FUTURE_WEATHER_UNAVAILABLE",
    "message": "Only historical observed weather is available. No future weather provider is integrated, so a range that includes future dates cannot be served. Historical weather is never reused as a future forecast.",
    "details": {
      "plant_id": "koppal-tpsaurya-s",
      "requested_start_date": "2026-08-01",
      "requested_end_date": "2026-08-10",
      "available_through": "2026-08-05",
      "missing_future_dates": [
        "2026-08-06", "2026-08-07", "2026-08-08", "2026-08-09", "2026-08-10"
      ],
      "reason": "future_weather_provider_unavailable"
    }
  }
}
```

Ranges wholly before observations return `count: 0` with an empty `data` array;
nothing is synthesised.

---

## 7. `GET /api/forecast`

Daily forecast for one plant.

**Query parameters**

| Name | Required | Default | Values |
| --- | --- | --- | --- |
| `plant_id` | **yes** | — | valid plant slug |
| `model` | no | `auto` | `rf`, `lstm`, `auto` |
| `horizon` | no | `3` | integer 1–7 **future days** |
| `base_date` | no | plant's last observed date | ISO date, must not exceed last observation |

`auto` selects the type-specific LSTM (`solar_lstm_daily` / `wind_lstm_daily`).
`rf` selects `random_forest_daily`.

### Status values

Every forecast response is HTTP 200. The body `status` distinguishes outcomes:

| `status` | Meaning | `forecasts` |
| --- | --- | --- |
| `ok` | Prediction produced | populated |
| `weather_required` | Required weather missing; nothing fabricated | `[]` |
| `insufficient_history` | Not enough preceding rows for the selected model | `[]` |

Invalid inputs (bad model/horizon/date/plant) are HTTP 4xx, not body states.

### Success response (`status: "ok"`, LSTM horizon 1)

```json
{
  "status": "ok",
  "frequency": "daily",
  "target": "DailyGeneration_MU",
  "unit": "MU/day",
  "horizon_days": 1,
  "model_requested": "lstm",
  "model": "solar_lstm_daily",
  "model_family": "lstm",
  "plant": { "...": "plant object" },
  "base_date": "2026-08-05",
  "forecast_dates": ["2026-08-06"],
  "confidence": null,
  "confidence_note": "No calibrated probabilistic forecasting model exists ...",
  "input_contract": {
    "model_family": "lstm",
    "input_shape": [7, 12],
    "sequence_length": 7,
    "feature_count": 12,
    "target_day_weather_required": false,
    "intermediate_day_weather_required": false,
    "uses_prediction_day_target": false,
    "observed_input_shape": [7, 12]
  },
  "future_weather": {
    "provider": "unavailable",
    "provider_available": false,
    "is_forecast": false,
    "required_for_this_request": false
  },
  "post_processing": {
    "applied": false,
    "method": "max(raw_prediction, 0.0)",
    "reason": "Daily energy generation cannot be negative. ...",
    "affected_dates": []
  },
  "forecast_count": 1,
  "forecasts": [
    {
      "date": "2026-08-06",
      "horizon_day": 1,
      "frequency": "daily",
      "unit": "MU/day",
      "prediction": 0.9801583284118001,
      "raw_prediction": 0.9801583284118001,
      "clamp_applied": false,
      "confidence": null
    }
  ],
  "history_context": {
    "last_observed_date": "2026-08-05",
    "observed_rows_used": 104,
    "capacity_mw": 131.0,
    "sequence_length": 7,
    "sequence_dates": ["2026-07-30", "...", "2026-08-05"],
    "sequence_start_date": "2026-07-30",
    "sequence_end_date": "2026-08-05",
    "sequence_calendar_consecutive": true,
    "generation_context": [
      {"date": "2026-07-30", "generation_mu": 0.74}
    ],
    "intermediate_weather_dates": [],
    "target_day_weather_required": false,
    "target_day_target_used": false,
    "note": "LSTM inference follows the committed training convention: the seven preceding rows ..."
  },
  "notes": ["..."]
}
```

For the Random Forest, `input_contract` instead reports:

```json
{
  "model_family": "random_forest",
  "input_shape": [24],
  "feature_count": 24,
  "target_day_weather_required": true,
  "uses_prediction_day_target": false,
  "forbidden_features": ["Generation_per_MW"]
}
```

RF success responses additionally include `features` on each forecast entry —
the exact 24 model inputs in manifest order. The target
`DailyGeneration_MU` and the leaked `Generation_per_MW` are never present.

### `weather_required` response

Returned when required future weather is unavailable (currently every RF request
and every LSTM request with horizon > 1).

```json
{
  "status": "weather_required",
  "model": "random_forest_daily",
  "model_family": "random_forest",
  "base_date": "2026-08-05",
  "forecast_dates": ["2026-08-06", "2026-08-07"],
  "forecast_count": 0,
  "forecasts": [],
  "required_weather": {
    "provider": "unavailable",
    "provider_available": false,
    "dates": ["2026-08-06", "2026-08-07"],
    "inputs": ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"],
    "missing": [
      {
        "date": "2026-08-06",
        "missing_inputs": ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
      }
    ],
    "target_day_weather_required": true,
    "note": "The Random Forest requires observed or forecast weather for every forecast day. ..."
  },
  "missing_weather": [
    {
      "date": "2026-08-06",
      "missing_inputs": ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
    }
  ],
  "missing_weather_summary": {
    "dates": ["2026-08-06", "2026-08-07"],
    "inputs": ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"],
    "count": 2
  },
  "reason": "Required weather is unavailable. No prediction was generated and no weather value was fabricated or reused from another date."
}
```

Weather requirements by model:

| Model | Horizon | Weather dates required |
| --- | --- | --- |
| `rf` | any | **every** forecast day |
| `lstm` | 1 | none |
| `lstm` | 2–7 | intermediate forecast days only (all but the final target day) |

### `insufficient_history` response

Returned when the plant lacks preceding rows (7 is the standard minimum).

```json
{
  "status": "insufficient_history",
  "model": "solar_lstm_daily",
  "base_date": "2026-05-03",
  "forecast_dates": ["2026-05-04"],
  "forecasts": [],
  "insufficient_history": {
    "required_rows": 7,
    "available_rows": 3,
    "reason": "lstm_requires_seven_feature_rows",
    "observed_rows": 10,
    "required_feature_rows": 7
  },
  "reason": "The plant does not have enough preceding observations to build the model input. No prediction was generated."
}
```

Possible `insufficient_history.reason` values:

- `no_observations_on_or_before_base_date`
- `rf_requires_seven_preceding_generation_rows`
- `lstm_requires_seven_feature_rows`
- `lstm_requires_seven_preceding_generation_rows`

### Wind negative-value handling

The Wind LSTM can emit a negative raw value. The response preserves it and
serves the physical value:

```json
{
  "raw_prediction": -0.10550108,
  "prediction": 0.0,
  "clamp_applied": true,
  "post_processing": {
    "applied": true,
    "method": "max(raw_prediction, 0.0)",
    "affected_dates": ["2026-06-20"]
  }
}
```

### Forecast errors

| Condition | HTTP | Code |
| --- | --- | --- |
| Missing `plant_id` | 400 | `MISSING_PARAMETER` |
| Unknown `plant_id` | 404 | `PLANT_NOT_FOUND` |
| `model` not in `rf/lstm/auto` | 400 | `INVALID_MODEL` |
| `horizon` `0`, `8`, `3h`, `24h`, non-integer, negative | 400 | `INVALID_HORIZON` |
| Malformed `base_date` | 400 | `INVALID_DATE` |
| `base_date` after last observation | 400 | `INVALID_BASE_DATE` |

---

## 8. `GET /api/model-performance`

Returns committed metrics with explicit provenance separation.

```json
{
  "frequency": "daily",
  "target": "DailyGeneration_MU",
  "unit": "MU/day",
  "metric_definitions": {
    "MAE": "Mean absolute error in MU/day on the chronological test split.",
    "RMSE": "Root mean squared error in MU/day on the chronological test split.",
    "R2": "Coefficient of determination on the chronological test split."
  },
  "comparison_policy": {
    "historical_25_feature_metrics_comparable_to_current": false,
    "reason": "The historical Random Forest used the leaked Generation_per_MW feature ...",
    "current_random_forest_features": 24,
    "historical_random_forest_features": 25
  },
  "models": {
    "random_forest": {
      "model_id": "random_forest_daily",
      "status": "production_candidate",
      "feature_count": 24,
      "metrics": {
        "current_leakage_free_24_feature": {
          "MAE": 0.132150218240383,
          "RMSE": 0.28278781980879913,
          "R2": 0.8970816491056874,
          "train_rows": 23268,
          "test_rows": 5842,
          "plants": 37,
          "features": 24
        },
        "historical_25_feature_reference": {
          "MAE": 0.11163797642553697,
          "leakage_affected": true,
          "comparable_to_current_24_feature_model": false,
          "usage": "provenance_only"
        }
      },
      "prediction_stats": {"negative_count": 0, "finite": true, "rows": 5842}
    },
    "solar_lstm": {
      "model_id": "solar_lstm_daily",
      "feature_count": 12,
      "sequence_length": 7,
      "metrics": {
        "committed_actual": {"MAE": 0.14415674553172728},
        "regenerated_pipeline_reference": {"...": "separate, not a reproduction"}
      }
    },
    "wind_lstm": {
      "model_id": "wind_lstm_daily",
      "feature_count": 12,
      "sequence_length": 7,
      "metrics": {
        "committed_actual": {"MAE": 0.6832080933787058},
        "regenerated_pipeline_reference": {"...": "separate, not a reproduction"}
      }
    }
  },
  "notes": ["..."]
}
```

Important:

- Historical 25-feature RF metrics are provenance only and **not comparable**
  to the current 24-feature artifact.
- LSTM `regenerated_pipeline_reference` values are a separate pipeline output,
  not a reproduction of `committed_actual`.
- No metric is synthesised.

---

## 9. `GET /api/feature-importance`

Random Forest **mean decrease in impurity** (Gini importance).

```json
{
  "model_id": "random_forest_daily",
  "frequency": "daily",
  "target": "DailyGeneration_MU",
  "method": "random_forest_impurity",
  "method_description": "Mean decrease in impurity (Gini importance) from the fitted scikit-learn RandomForestRegressor. This is not SHAP and not permutation importance.",
  "shap_used": false,
  "feature_count": 24,
  "importance_sum": 0.9999999999999987,
  "features": [
    {"rank": 1, "feature": "Generation_lag_1", "importance": 0.1996261071039647}
  ],
  "notes": ["..."],
  "historical_25_feature_reference": {
    "method": "random_forest_impurity",
    "leakage_affected": true,
    "comparable_to_current": false,
    "features": [
      {"rank": 1, "feature": "Generation_roll_3", "importance": 0.1807121184269389}
    ],
    "note": "Historical importances from the removed 25-feature model. They include Generation_per_MW and are not comparable to the current 24-feature model."
  }
}
```

- `shap_used` is always `false`; the API never claims SHAP.
- The current 24-feature list excludes `Generation_per_MW` and
  `DailyGeneration_MU`.
- The historical 25-feature block is separately labelled and includes the
  leaked feature for provenance only.
- Missing/invalid report files return 503 `REPORT_UNAVAILABLE` /
  `REPORT_INVALID`.

---

## 10. `GET /api/dashboard`

Fleet summary for the latest observed date.

```json
{
  "as_of_date": "2026-08-05",
  "frequency": "daily",
  "unit": "MU/day",
  "target": "DailyGeneration_MU",
  "total_plants": 37,
  "solar_plant_count": 30,
  "wind_plant_count": 7,
  "total_installed_capacity_mw": 4752.0,
  "capacity_by_type_mw": {"Solar": 3280.0, "Wind": 1472.0},
  "capacity_basis": "latest observed Capacity_MW per plant",
  "latest_generation": {
    "date": "2026-08-05",
    "total_generation_mu": 25.02,
    "solar_generation_mu": 12.1,
    "wind_generation_mu": 12.92,
    "reporting_plants": 26,
    "total_plants": 37,
    "coverage_note": "Only plants with an observed record on the latest fleet date are included."
  },
  "latest_weather_context": {
    "date": "2026-08-05",
    "scope": "fleet_mean_on_latest_fleet_date",
    "weather_type": "historical",
    "is_forecast": false,
    "reporting_plants": 26,
    "temperature": 24.516538461538463,
    "humidity": 85.06423076923078,
    "wind_speed": 3.972692307692308,
    "ghi": 4.081988461538462,
    "pressure": 94.36076923076924,
    "units": {"...": "..."},
    "note": "Arithmetic mean of the observed weather values for plants reporting on the latest fleet date."
  },
  "model_status": {"random_forest": "loaded", "solar_lstm": "loaded", "wind_lstm": "loaded"},
  "forecast_status": {
    "frequency": "daily",
    "unit": "MU/day",
    "future_weather": {"future_weather_available": false, "provider": "unavailable"},
    "random_forest_forecast_available": false,
    "one_day_lstm_forecast_available": true,
    "multi_day_lstm_forecast_available": false,
    "default_horizon_days": 3,
    "max_horizon_days": 7
  },
  "data_coverage": {
    "dataset_start": "2020-05-28",
    "dataset_end": "2026-08-05",
    "plants_reporting_on_latest_date": 26,
    "plants_with_stale_last_observation": 11,
    "oldest_last_observation": "2022-05-05",
    "plants_with_coordinates": 15,
    "rows_with_imputed_weather": 104,
    "stale_plant_examples": [
      {"plant_id": "adyah-block-1", "plant_name": "ADYAH BLOCK 1", "last_observed_date": "2022-05-05"}
    ]
  },
  "notes": ["..."]
}
```

Coverage is stated explicitly; stale plants are never back-filled.

---

## 11. `GET /api/analytics`

Descriptive daily analytics by plant, type or fleet.

**Query parameters**

| Name | Required | Notes |
| --- | --- | --- |
| `plant_id` | no | plant scope |
| `type` | no | `solar` / `wind` type scope |
| `start_date` | no | inclusive |
| `end_date` | no | inclusive |

No filters → fleet scope. `plant_id` + mismatched `type` → 400 `FILTER_MISMATCH`.

**Type-scope response:**

```json
{
  "scope": "type",
  "plant_id": null,
  "plant_name": null,
  "type": "Wind",
  "frequency": "daily",
  "unit": "MU/day",
  "target": "DailyGeneration_MU",
  "capacity_basis": "latest observed Capacity_MW per plant",
  "requested_range": {"start": "2026-08-01", "end": "2026-08-05"},
  "coverage": {
    "start": "2026-08-01",
    "end": "2026-08-05",
    "calendar_days": 5,
    "dates_observed": 5,
    "missing_calendar_days": 0,
    "plant_day_observations": 30
  },
  "summary": {
    "total_generation_mu": 72.21,
    "mean_daily_generation_mu": 14.442,
    "min_daily_generation_mu": 11.02,
    "max_daily_generation_mu": 17.52,
    "days": 5,
    "plant_day_observations": 30,
    "plants": 6,
    "capacity_mw": 1195.0,
    "unit": "MU/day"
  },
  "generation_by_date": [
    {
      "date": "2026-08-01",
      "total_generation_mu": 17.52,
      "solar_generation_mu": 0.0,
      "wind_generation_mu": 17.52,
      "reporting_plants": 6
    }
  ],
  "generation_by_type": [
    {
      "type": "Wind",
      "total_generation_mu": 72.21,
      "mean_daily_generation_mu": 14.442,
      "observations": 30,
      "days": 5,
      "plant_count": 6,
      "capacity_mw": 1195.0
    }
  ],
  "generation_by_plant": [
    {
      "plant_id": "gadag-vena-w",
      "plant_name": "GADAG_VENA_W",
      "type": "Wind",
      "capacity_mw": 133.0,
      "total_generation_mu": 10.78,
      "mean_daily_generation_mu": 2.156,
      "generation_per_mw_per_day": 0.01621052631578947,
      "observations": 5,
      "first_observed_date": "2026-08-01",
      "last_observed_date": "2026-08-05"
    }
  ],
  "derived_metrics": {
    "generation_per_mw_per_day": "Descriptive analytics ratio equal to mean daily generation divided by the plant's latest observed capacity. It is not a model feature, is not used by the Random Forest, and is not a capacity factor."
  },
  "notes": ["..."]
}
```

`generation_per_mw_per_day` is descriptive only. It is not the removed
`Generation_per_MW` model feature, is never used for inference, and is not a
capacity factor.

An empty period returns zeros and `null` means, with empty arrays; nothing is
invented.

---

## 12. Explicit non-capabilities

The following are **not** part of this contract and must not be inferred from
any response:

- hourly forecasts, hourly history, hourly weather, or sub-daily resolution;
- future weather availability (no provider is integrated);
- confidence intervals / prediction intervals / probabilities;
- SHAP or permutation importance;
- reproduction of the historical leaked 25-feature metrics;
- frontend integration;
- synthetic or mock fallback data.

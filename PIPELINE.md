# ENERVISION reproducible ML pipeline

This document describes the reproducible preprocessing pipeline for the
`member1-recovery` branch and the exact state of the committed model artifacts.
It is intentionally limited to **daily plant-wise generation forecasting**. There is
no hourly model in this repository.

## Current Forecasting Contract

ENERVISION currently performs **DAILY renewable-generation forecasting**.

- Target variable: `DailyGeneration_MU`.
- Frequency: **daily**.
- Unit: **MU/day**.
- Forecasts represent **energy generation over one day**, per plant.
- Forecast horizon is **future days**, not future hours.
- The current models do **not** produce hourly forecasts.
- The system must **not** convert daily forecasts into hourly forecasts by
  interpolation, division, synthetic timestamps, or relabelling.
- There are no `+3H` / `+6H` / `+12H` / `+24H` predictions.
- Any future hourly forecasting capability requires an **hourly dataset** and a
  **separately trained hourly forecasting model**. Neither exists in this repository.

This contract is enforced by `scripts/validate_pipeline.py`, which checks the manifest
target/frequency, rejects hourly model artifacts, and scans the pipeline scripts for
hourly forecasting code.

## Quick start

From the repository root, with Python 3.12:

```bash
python -m pip install -r requirements.txt
python scripts/run_preprocessing_pipeline.py
python scripts/train_random_forest.py
python scripts/validate_pipeline.py
```

`train_random_forest.py` writes the leakage-free 24-feature RF artifact and its own
metric/importance reports. `validate_pipeline.py` verifies the dataset contract, the
leakage proof, the artifact, all four scalers, the daily forecasting contract and
metric consistency.

The pipeline is deterministic and has no random split. Running it twice on the same
input produces byte-identical CSV ordering and values (pandas float formatting is
stable for the pinned version).

## Stage 1 - build the plant/weather modelling table

`scripts/build_plant_weather_training_dataset.py`

Input:

- `data/final/full_generation_weather_dataset.csv` (canonical committed dataset)

Output:

- `data/final/plant_weather_training_dataset.csv`
- `reports/data_quality_summary.json`

The historical builder from commit `760289efaa` read `generation_combined.csv`,
`weather_clean.csv` and `plant_weather_mapping.csv`. Those intermediate files are not
present in any branch or commit, so the historical acquisition/merge scripts were
**not** restored: restoring code without its source data would not make the pipeline
runnable. Instead, this stage derives the modelling table from the canonical merged
dataset and records every quality action.

### Data-quality policy (explicit, never silent)

| Issue | Policy |
|---|---|
| `-999` weather sentinels | Any weather value `<= -900` is treated as missing, flagged in `WeatherSentinelCount` / `WeatherImputed`, then filled per plant in date order with forward-fill followed by backward-fill. This matches the committed LSTM cleaning code. |
| Negative `DailyGeneration_MU` | Flagged in `GenerationWasNegative` and clipped to `0.0` for modelling, matching the committed LSTM target policy. The canonical dataset contains **0** negative rows today, so this is a no-op. |
| Missing Date / PlantName / Type / Capacity / target | Row dropped and counted. |
| `Capacity_MW <= 0` | Row dropped and counted. |
| Duplicate `(PlantName, Date, Capacity_MW)` | Dropped, first occurrence kept, counted. |
| Unrecoverable weather | Rows with NaN weather after per-plant filling are dropped and counted. |
| Mapping provenance | `MappingStatus` is joined from `data/metadata/plant_weather_mapping.csv` as metadata only. It is not a model feature. |

Canonical result: 29,369 rows in, 29,369 rows out, 37 plants, 312 weather values
imputed across 104 rows, 0 negatives.

## Stage 2 - engineer the 24 leakage-free Random Forest features

`scripts/engineer_plant_features.py`

Input:

- `data/final/plant_weather_training_dataset.csv`

Output:

- `data/final/plant_features_dataset.csv` (before the split column is added)

Leakage rules:

- Generation lags 1/2/3/7 are computed **per plant** with `shift(lag)`.
- `Generation_roll_3` and `Generation_roll_7` are computed **per plant** as
  `shift(1)` followed by a 3/7-row rolling mean. The shift happens **before** the
  roll, so the current day's target never enters its own feature.
- Weather lags are computed **per plant** with `shift(1)`.
- Rows without a complete feature vector or target are dropped.

`Generation_per_MW = DailyGeneration_MU / Capacity_MW` was **removed from the
dataset and the RF contract** because it was derived from the current-day target and
therefore leaked the value being predicted. It is not generated, renamed, or
reconstructed at inference time.

The exact 24-feature order is the order in `scripts/train_random_forest.py` and is
verified by `scripts/validate_pipeline.py` against an independent literal copy and
against `models/model_manifest.json`.

The validator also empirically reconstructs every generation lag/rolling feature and
every weather lag from historical targets/weather using the shift-before-roll rule and
compares them with the stored columns. The checked rows match to floating-point
tolerance, which proves the stored features contain only historical information.

Result: 29,110 rows, 37 plants (26,370 solar / 2,740 wind), date range
2020-06-04 to 2026-08-05.

## Stage 3 - chronological per-plant split

`scripts/split_plant_dataset.py`

Rule:

```
for each plant:
    sort rows by Date
    n_train = int(n * 0.80)
    earliest n_train rows -> train
    remaining rows        -> test
```

No shuffling and no random seed. The split is written as an explicit `_split` column
(`train` / `test`) into `data/final/plant_features_dataset.csv`, and the same rows are
also written to `data/final/plant_train.csv` and `data/final/plant_test.csv`.

Result: 23,268 train / 5,842 test rows, 37 plants with test rows, 0 temporal
violations.

## Feature contracts

### Random Forest - 24 leakage-free features

```
Capacity_MW, Temperature, Humidity, WindSpeed, GHI, Pressure,
Temperature_lag_1, Humidity_lag_1, WindSpeed_lag_1, GHI_lag_1,
Generation_lag_1, Generation_lag_2, Generation_lag_3, Generation_lag_7,
Generation_roll_3, Generation_roll_7,
Year, Month, DayOfYear, DayOfWeek,
Month_sin, Month_cos, DayOfYear_sin, DayOfYear_cos
```

Target: `DailyGeneration_MU` (daily, MU/day). Status: `production_candidate`.
No scaler is applied. The model does **not** require `DailyGeneration_MU` for the day
being predicted. It does require weather for the target day, which may be observed or
forecast weather.

`Generation_per_MW` is **absent** from this contract because it leaked the prediction
target.

### Solar / Wind LSTM - 12 features, sequence length 7

```
Capacity_MW, Temperature, Humidity, WindSpeed, GHI, Pressure,
Month_sin, Month_cos, DayOfYear_sin, DayOfYear_cos,
Lagged_Generation, Rolling_Generation_7
```

`Lagged_Generation` maps to dataset column `Generation_lag_1`.
`Rolling_Generation_7` maps to dataset column `Generation_roll_7`.

Input shape is exactly `(7, 12)` per sample. Each type has its own StandardScaler
feature scaler and target scaler.

## Model artifacts

`models/model_manifest.json` is the machine-readable contract. It contains only the
three usable production models:

1. Random Forest (`models/random_forest_model.pkl`)
2. Solar LSTM (`models/solar_lstm.keras`)
3. Wind LSTM (`models/wind_lstm.keras`)

It also records the four scalers, exact feature order, target, metrics, versions,
source scripts and hashes. The 11-feature `solar_lstm_best*.keras` files are excluded
because no matching 11-feature scaler exists. XGBoost, Gradient Boosting, CatBoost,
MLP and SVM are explicitly listed as not trained.

## Validation results

`scripts/validate_pipeline.py` writes `reports/validation_report.json`.

Structural checks: **37/37 pass**, including:

- dataset shape and `_split` counts;
- per-plant earliest-80 / latest-20 rule with 0 temporal violations;
- RF matrix exactly 24 columns in the frozen leakage-free order;
- `Generation_per_MW` absent from both the dataset and the RF contract;
- generation lag/rolling and weather-lag features empirically reconstructed from
  historical-only inputs (checked rows match to ~1e-15, 0 violations);
- RF artifact feature order proven index-by-index against
  `reports/generation_feature_importance.csv`, which must contain 24 features summing
  to 1;
- RF artifact SHA-256 and size match the manifest;
- both LSTMs load with input `(7, 12)`;
- all four scalers load with 12 feature slots / 1 target slot;
- scaler statistics match the code-defined LSTM training split to floating-point
  precision (max mean delta ~1e-17, max scale delta ~1e-16), proving the correct
  feature order and renewable type;
- inference is finite for RF, Solar LSTM and Wind LSTM;
- the saved leakage-free RF metrics match an independent recomputation;
- the manifest enforces a daily target/frequency and no hourly model artifact or
  hourly forecasting code exists.

### Metric reproducibility

The current RF metrics are reproduced by the validator. Historical committed metrics
are kept for provenance but are **not** claimed as reproduced.

| Model | Committed / historical metrics (MAE / RMSE / R²) | Current recomputation | Status |
|---|---|---|---|
| Random Forest (historical 25-feature, leaked) | 0.111638 / 0.300339 / 0.871158 | — | Historical only; feature contract changed, not comparable |
| Random Forest (current 24-feature, leakage-free) | — | 0.132150 / 0.282788 / 0.897082 | Saved report matches recomputation |
| Solar LSTM | 0.144157 / 0.234579 / 0.866819 | 0.147092 / 0.237815 / 0.862574 | Not reproduced |
| Wind LSTM | 0.683208 / 1.004004 / 0.436106 | 0.657784 / 0.956904 / 0.481457 | Not reproduced |

Random Forest: the historical 25-feature run used a 22,764-row / 25-plant feature
dataset and an original `_split` column that are absent from every branch and commit.
The new leakage-free model was trained on the regenerated 29,110-row / 37-plant
dataset with 23,268 train / 5,842 test rows. The historical and new metrics are
therefore different models and are not comparable. The historical metrics remain at
`reports/generation_metrics.csv`; the new metrics are at
`reports/generation_metrics_leakage_free.csv`.

LSTM: the committed run's exact per-plant cutoffs and data snapshot are not committed.
The recomputation uses the code-defined 2026 test window and the committed scalers, but
still differs. The committed values remain the authoritative recorded results; they
must not be described as reproduced. The LSTMs were **not** retrained or changed.

## Known blockers before API work

1. **Historical reproducibility:** the exact 25-plant dataset and original `_split`
   are missing, so the historical 25-feature RF metric cannot be independently
   regenerated. This is a provenance limitation, not a serving blocker.
2. **Dataset/README mismatch:** the canonical dataset has 37 plants / 29,369 rows, not
   the README's historical 25 plants / 22,764 rows.
3. **No hourly model:** every model predicts daily `DailyGeneration_MU`. Do not convert
   these predictions into fake hourly values. Hourly forecasting requires an hourly
   dataset and a separately trained model.
4. **Negative wind predictions:** the Wind LSTM produced a minimum test prediction of
   about `-0.1055` MU. It is finite but non-physical; the serving layer needs an
   explicit post-processing policy (for example, clip at 0) before exposing it. The RF
   test predictions are all non-negative (min `0.0`, 0 negatives).
5. **No backend:** no API exists yet, and none was created in this task.
6. **Plant identity:** the data uses free-text `PlantName`; there is no stable plant ID
   or frontend↔data plant mapping yet.
7. **Weather for the target day:** all models require weather features for the
   forecast date. A serving layer must obtain them from an observed or forecast weather
   source. This is legitimate input, not target leakage.

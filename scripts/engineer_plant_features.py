"""Engineer the 25 Random-Forest features from the plant/weather training dataset.

Pipeline position:
    data/final/plant_weather_training_dataset.csv
        -> scripts/engineer_plant_features.py
        -> data/final/plant_features_dataset.csv

The exact feature names and order are preserved from the committed training script
``scripts/train_random_forest.py``.  Lags and rolling statistics are computed strictly
per plant, and every generation rolling feature is shifted by one day *before* the
rolling window is applied so that the current day's target never enters its own
feature.

IMPORTANT (serving caveat, preserved from the original model contract)
----------------------------------------------------------------------
``Generation_per_MW`` is defined exactly as in the committed pipeline:

    Generation_per_MW = DailyGeneration_MU / Capacity_MW

This uses the current day's target and therefore cannot be computed before the day's
generation is known.  It is retained because the existing Random Forest artifact was
trained with it and changing the definition would invalidate the committed model.
This is recorded as a serving blocker in ``models/model_manifest.json``; it must be
resolved (for example by retraining without the feature) before the RF is exposed by
an API.  It is *not* silently changed here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent

INPUT = BASE / "data/final/plant_weather_training_dataset.csv"
OUTPUT = BASE / "data/final/plant_features_dataset.csv"

# Exact Random Forest feature order from scripts/train_random_forest.py.
FEATURES = [
    "Capacity_MW",
    "Temperature",
    "Humidity",
    "WindSpeed",
    "GHI",
    "Pressure",
    "Temperature_lag_1",
    "Humidity_lag_1",
    "WindSpeed_lag_1",
    "GHI_lag_1",
    "Generation_lag_1",
    "Generation_lag_2",
    "Generation_lag_3",
    "Generation_lag_7",
    "Generation_roll_3",
    "Generation_roll_7",
    "Generation_per_MW",
    "Year",
    "Month",
    "DayOfYear",
    "DayOfWeek",
    "Month_sin",
    "Month_cos",
    "DayOfYear_sin",
    "DayOfYear_cos",
]
TARGET = "DailyGeneration_MU"

# Identifier columns are kept for splitting, traceability and API joins.  They are
# not passed to the model (the training script selects FEATURES explicitly).
OUTPUT_COLS = (
    ["Date", "PlantName", "Type", "Capacity_MW", "District"]
    + [feature for feature in FEATURES if feature != "Capacity_MW"]
    + [TARGET]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args()


def shifted_rolling(series: pd.Series, window: int) -> pd.Series:
    """Shift first, then roll, so the current target is excluded from its feature."""
    return series.shift(1).rolling(window, min_periods=window).mean()


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(
            f"Input dataset not found: {args.input}\n"
            "Run scripts/build_plant_weather_training_dataset.py first."
        )

    df = pd.read_csv(args.input)
    required = [
        "Date",
        "PlantName",
        "Type",
        "Capacity_MW",
        "District",
        TARGET,
        "Temperature",
        "Humidity",
        "WindSpeed",
        "GHI",
        "Pressure",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Input dataset is missing required columns: {missing}")

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["PlantName", "Date", "Capacity_MW"]).reset_index(drop=True)

    duplicate_keys = df.duplicated(subset=["PlantName", "Date"], keep=False)
    if duplicate_keys.any():
        sample = df.loc[duplicate_keys, ["PlantName", "Date", "Capacity_MW"]].head(10)
        raise ValueError(
            "Found duplicate (PlantName, Date) rows; lag features would be ambiguous.\n"
            f"{sample.to_string(index=False)}"
        )

    # Calendar features.
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["DayOfYear"] = df["Date"].dt.dayofyear
    df["DayOfWeek"] = df["Date"].dt.dayofweek

    # Cyclic time features.
    df["Month_sin"] = np.sin(2 * np.pi * df["Month"] / 12)
    df["Month_cos"] = np.cos(2 * np.pi * df["Month"] / 12)
    df["DayOfYear_sin"] = np.sin(2 * np.pi * df["DayOfYear"] / 365.25)
    df["DayOfYear_cos"] = np.cos(2 * np.pi * df["DayOfYear"] / 365.25)

    # Plant-normalized generation (preserved contract; see module docstring).
    if (df["Capacity_MW"] <= 0).any():
        raise ValueError("Capacity_MW must be positive before computing Generation_per_MW")
    df["Generation_per_MW"] = df[TARGET] / df["Capacity_MW"]

    # Generation lags, strictly per plant.
    for lag in (1, 2, 3, 7):
        df[f"Generation_lag_{lag}"] = df.groupby("PlantName", group_keys=False)[TARGET].shift(lag)

    # Rolling generation statistics: shift(1) then roll, grouped per plant.
    for window in (3, 7):
        df[f"Generation_roll_{window}"] = df.groupby(
            "PlantName", group_keys=False
        )[TARGET].transform(lambda series, w=window: shifted_rolling(series, w))

    # Weather lags, strictly per plant.
    for col in ("Temperature", "Humidity", "WindSpeed", "GHI"):
        df[f"{col}_lag_1"] = df.groupby("PlantName", group_keys=False)[col].shift(1)

    # Only drop rows that lack a model feature or the target.  Do not drop rows for
    # unrelated metadata gaps.
    df = df.dropna(subset=FEATURES + [TARGET]).reset_index(drop=True)

    if df.empty:
        raise ValueError("Feature engineering produced an empty dataset")

    df = df[OUTPUT_COLS]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    print("=" * 72)
    print("PLANT-WISE FEATURE DATASET CREATED")
    print("=" * 72)
    print(f"Rows          : {len(df)}")
    print(f"Plants        : {df['PlantName'].nunique()}")
    print(f"Solar rows    : {(df['Type'] == 'Solar').sum()}")
    print(f"Wind rows     : {(df['Type'] == 'Wind').sum()}")
    print(f"Date range    : {df['Date'].min().date()} to {df['Date'].max().date()}")
    print(f"Model features: {len(FEATURES)}")
    print(f"Missing values in model features: {df[FEATURES].isna().sum().sum()}")
    print(f"\nSaved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

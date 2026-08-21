from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent

INPUT = BASE / "data/final/plant_weather_training_dataset.csv"
OUTPUT = BASE / "data/final/plant_features_dataset.csv"

df = pd.read_csv(INPUT)
df["Date"] = pd.to_datetime(df["Date"])

df = df.sort_values(["PlantName", "Date"]).reset_index(drop=True)

# Calendar features
df["Year"] = df["Date"].dt.year
df["Month"] = df["Date"].dt.month
df["DayOfYear"] = df["Date"].dt.dayofyear
df["DayOfWeek"] = df["Date"].dt.dayofweek

# Cyclic time features
import numpy as np

df["Month_sin"] = np.sin(2 * np.pi * df["Month"] / 12)
df["Month_cos"] = np.cos(2 * np.pi * df["Month"] / 12)

df["DayOfYear_sin"] = np.sin(2 * np.pi * df["DayOfYear"] / 365.25)
df["DayOfYear_cos"] = np.cos(2 * np.pi * df["DayOfYear"] / 365.25)

# Plant-normalized generation
df["Generation_per_MW"] = (
    df["DailyGeneration_MU"] / df["Capacity_MW"]
)

# Lag features — strictly plant-wise
for lag in [1, 2, 3, 7]:
    df[f"Generation_lag_{lag}"] = (
        df.groupby("PlantName")["DailyGeneration_MU"]
        .shift(lag)
    )

# Rolling generation statistics — shifted first to avoid leakage
grouped = df.groupby("PlantName")["DailyGeneration_MU"]

df["Generation_roll_3"] = (
    grouped.shift(1).rolling(3).mean()
    .reset_index(level=0, drop=True)
)

df["Generation_roll_7"] = (
    grouped.shift(1).rolling(7).mean()
    .reset_index(level=0, drop=True)
)

# Weather lags
for col in ["Temperature", "Humidity", "WindSpeed", "GHI"]:
    df[f"{col}_lag_1"] = (
        df.groupby("PlantName")[col].shift(1)
    )

# Remove rows created by lagging
df = df.dropna().reset_index(drop=True)

# Final columns
features = [
    "Date",
    "PlantName",
    "Type",
    "Capacity_MW",
    "District",

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

    "DailyGeneration_MU"
]

df = df[features]

df.to_csv(OUTPUT, index=False)

print("=" * 70)
print("PLANT-WISE FEATURE DATASET CREATED")
print("=" * 70)
print("Rows:", len(df))
print("Plants:", df.PlantName.nunique())
print("Solar:", (df.Type == "Solar").sum())
print("Wind:", (df.Type == "Wind").sum())
print("Date:", df.Date.min(), "to", df.Date.max())
print("\nMissing values:")
print(df.isna().sum())
print("\nSaved:")
print(OUTPUT)
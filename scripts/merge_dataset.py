import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------
# Load datasets
# -----------------------------
generation = pd.read_csv(
    BASE_DIR / "data/generation/generation_clean.csv"
)

mapping = pd.read_csv(
    BASE_DIR / "data/generation/isgs_plants.csv"
)

weather = pd.read_csv(
    BASE_DIR / "data/weather/weather_raw.csv"
)

# -----------------------------
# Clean mapping
# -----------------------------
mapping["District"] = (
    mapping["District"]
    .astype(str)
    .str.strip()
)

weather["District"] = (
    weather["District"]
    .astype(str)
    .str.strip()
)

# -----------------------------
# Merge generation with mapping
# -----------------------------
generation = generation.merge(
    mapping,
    on="PlantName",
    how="left"
)

# -----------------------------
# Convert dates
# -----------------------------
generation["Date"] = pd.to_datetime(generation["Date"])

weather["Date"] = pd.to_datetime(
    weather["Date"].astype(str),
    format="%Y%m%d"
)

# -----------------------------
# Merge weather
# -----------------------------
final = pd.merge(
    generation,
    weather,
    on=["District", "Date"],
    how="left"
)

# -----------------------------
# Keep required columns
# -----------------------------
final = final[
    [
        "Date",
        "PlantName",
        "District",
        "Type",
        "Capacity_MW",
        "Temperature",
        "Humidity",
        "WindSpeed",
        "GHI",
        "Pressure",
        "DailyGeneration_MU",
        "CumulativeGeneration_MU"
    ]
]

final = final.dropna(
    subset=[
        "Temperature",
        "Humidity",
        "WindSpeed",
        "GHI",
        "Pressure"
    ]
)

# -----------------------------
# Save
# -----------------------------
output = BASE_DIR / "data/final"
output.mkdir(parents=True, exist_ok=True)

final.to_csv(
    output / "final_training_dataset.csv",
    index=False
)

print("\nDataset Created Successfully!\n")

print(final.head())

print("\nRows :", len(final))

print("\nMissing Values\n")

print(final.isna().sum())
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent

GEN = BASE / "data/generation/generation_combined.csv"
WEATHER = BASE / "data/weather/weather_clean.csv"
MAPPING = BASE / "data/metadata/plant_weather_mapping.csv"

g = pd.read_csv(GEN)
w = pd.read_csv(WEATHER)
m = pd.read_csv(MAPPING)

g["Date"] = pd.to_datetime(g["Date"])
w["Date"] = pd.to_datetime(w["Date"])

# Only use plants for which we have a district/weather location.
m = m[m["MappingStatus"] == "Mapped"][
    ["PlantName", "Type", "Capacity_MW", "District"]
].drop_duplicates()

print("=" * 70)
print("BUILDING PLANT-WEATHER TRAINING DATASET")
print("=" * 70)

# Match generation to verified/probable weather district mappings
df = g.merge(
    m,
    on=["PlantName", "Type", "Capacity_MW"],
    how="inner"
)

print("Generation rows:", len(g))
print("Mapped generation rows:", len(df))
print("Plants:", df["PlantName"].nunique())

# Add weather
df = df.merge(
    w,
    on=["District", "Date"],
    how="left",
    suffixes=("", "_weather")
)

# Keep required ML columns
cols = [
    "Date",
    "PlantName",
    "Type",
    "Capacity_MW",
    "District",
    "DailyGeneration_MU",
    "Temperature",
    "Humidity",
    "WindSpeed",
    "GHI",
    "Pressure"
]

df = df[cols]

print("Final rows:", len(df))
print("Plants:", df.PlantName.nunique())
print("Weather missing:", df[["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]].isna().any(axis=1).sum())

out = BASE / "data/final/plant_weather_training_dataset.csv"
out.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(out, index=False)

print("\nSaved:")
print(out)
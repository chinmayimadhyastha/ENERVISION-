from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

GENERATION = BASE_DIR / "data" / "generation" / "generation_combined.csv"
MAPPING = BASE_DIR / "data" / "metadata" / "generation_plant_mapping.csv"
WEATHER = BASE_DIR / "data" / "weather" / "weather_clean.csv"
OUTPUT = BASE_DIR / "data" / "metadata" / "plant_weather_mapping.csv"


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

generation = pd.read_csv(GENERATION)
mapping = pd.read_csv(MAPPING)
weather = pd.read_csv(WEATHER)

generation["Date"] = pd.to_datetime(generation["Date"])
weather["Date"] = pd.to_datetime(weather["Date"])


# ---------------------------------------------------------
# Get unique generation plants
# ---------------------------------------------------------

plants = (
    generation[
        ["PlantName", "Type", "Capacity_MW"]
    ]
    .drop_duplicates()
    .sort_values(["PlantName", "Type", "Capacity_MW"])
    .reset_index(drop=True)
)


# ---------------------------------------------------------
# Keep only plant-level mapping information
# ---------------------------------------------------------

map_cols = [
    "PlantName",
    "Type",
    "Capacity_MW",
    "District",
    "Latitude",
    "Longitude",
    "MatchStatus",
]

mapping = mapping[map_cols].copy()

mapping["Capacity_MW"] = pd.to_numeric(
    mapping["Capacity_MW"],
    errors="coerce"
)


# ---------------------------------------------------------
# Merge plant information with mapping
# ---------------------------------------------------------

result = plants.merge(
    mapping,
    on=["PlantName", "Type", "Capacity_MW"],
    how="left"
)


# ---------------------------------------------------------
# Check which districts actually exist in weather data
# ---------------------------------------------------------

weather_districts = set(weather["District"].dropna().unique())

result["WeatherAvailable"] = result["District"].isin(
    weather_districts
)


# ---------------------------------------------------------
# Mapping status
# ---------------------------------------------------------

result["MappingStatus"] = "Unmapped"

result.loc[
    result["District"].notna() &
    result["WeatherAvailable"],
    "MappingStatus"
] = "Mapped"

result.loc[
    result["District"].notna() &
    ~result["WeatherAvailable"],
    "MappingStatus"
] = "DistrictUnavailable"


# ---------------------------------------------------------
# Select final columns
# ---------------------------------------------------------

result = result[
    [
        "PlantName",
        "Type",
        "Capacity_MW",
        "District",
        "Latitude",
        "Longitude",
        "MatchStatus",
        "WeatherAvailable",
        "MappingStatus",
    ]
]


# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

result.to_csv(OUTPUT, index=False)


# ---------------------------------------------------------
# Report
# ---------------------------------------------------------

print("=" * 70)
print("PLANT → WEATHER MAPPING CREATED")
print("=" * 70)

print("Generation plants:", len(plants))
print("Mapping rows:", len(result))

print("\nMapping status:")
print(result["MappingStatus"].value_counts().to_string())

print("\nMapped plants:")
print(
    result[
        result["MappingStatus"] == "Mapped"
    ][
        ["PlantName", "Type", "Capacity_MW", "District", "MappingStatus"]
    ].to_string(index=False)
)

print("\nUnmapped plants:")
print(
    result[
        result["MappingStatus"] != "Mapped"
    ][
        ["PlantName", "Type", "Capacity_MW", "District", "MappingStatus"]
    ].to_string(index=False)
)

print("\nSaved:")
print(OUTPUT)
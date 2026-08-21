from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

GEN_PATH = BASE_DIR / "data" / "generation" / "generation_combined.csv"
MAP_PATH = BASE_DIR / "data" / "metadata" / "generation_plant_mapping.csv"
OUT_PATH = BASE_DIR / "data" / "generation" / "generation_final.csv"

# Load
gen = pd.read_csv(GEN_PATH)
mapping = pd.read_csv(MAP_PATH)

# Remove aggregate rows if any
gen = gen[~gen["PlantName"].str.contains(
    r"^All |^Total|Karnataka|State",
    case=False,
    na=False,
    regex=True
)].copy()

# Mapping key
mapping_key = mapping[
    ["PlantName", "Type", "Capacity_MW",
     "District", "Latitude", "Longitude",
     "CommissionDate", "MatchStatus"]
].drop_duplicates()

# Merge plant metadata
final = gen.merge(
    mapping_key,
    on=["PlantName", "Type", "Capacity_MW"],
    how="left"
)

# Clean date
final["Date"] = pd.to_datetime(final["Date"])

# Remove accidental duplicate plant/date records
final = (
    final
    .drop_duplicates(subset=["Date", "PlantName", "Type", "Capacity_MW"])
    .sort_values(["Date", "Type", "PlantName"])
    .reset_index(drop=True)
)

# Save
final.to_csv(OUT_PATH, index=False)

print("=" * 70)
print("FINAL GENERATION DATASET CREATED")
print("=" * 70)

print("Rows:", len(final))
print("Plants:", final["PlantName"].nunique())

print("\nTypes:")
print(final["Type"].value_counts())

print("\nDate:")
print(final["Date"].min(), "to", final["Date"].max())

print("\nCoordinates:")
print("With coordinates:", final["Latitude"].notna().sum())
print("Without coordinates:", final["Latitude"].isna().sum())

print("\nMatch status:")
print(final["MatchStatus"].value_counts(dropna=False))

print("\nSaved:")
print(OUT_PATH)
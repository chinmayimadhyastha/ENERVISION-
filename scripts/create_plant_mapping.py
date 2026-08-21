import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

GEN_FILE = BASE_DIR / "data" / "generation" / "generation_combined.csv"
META_FILE = BASE_DIR / "data" / "metadata" / "plants_geocoded.csv"
OUT_FILE = BASE_DIR / "data" / "metadata" / "generation_plant_mapping.csv"

# Load data
generation = pd.read_csv(GEN_FILE)
metadata = pd.read_csv(META_FILE)

# Get unique CEA plant/capacity/type combinations
plants = (
    generation[
        ["PlantName", "Type", "Capacity_MW"]
    ]
    .drop_duplicates()
    .sort_values(["PlantName", "Type", "Capacity_MW"])
)

# Create empty mapping
mapping = plants.copy()

mapping["MetadataMatch"] = ""
mapping["District"] = ""
mapping["Latitude"] = ""
mapping["Longitude"] = ""
mapping["CommissionDate"] = ""
mapping["MatchStatus"] = "Unverified"

# Save
mapping.to_csv(OUT_FILE, index=False)

print("=" * 70)
print("PLANT MAPPING FILE CREATED")
print("=" * 70)

print("Generation plants:", generation["PlantName"].nunique())
print("Plant/capacity combinations:", len(plants))
print()
print("Saved:")
print(OUT_FILE)
print()
print(mapping.to_string(index=False))
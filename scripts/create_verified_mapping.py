import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

GEN = BASE / "data/generation/generation_combined.csv"
META = BASE / "data/metadata/plants_geocoded.csv"
OUT = BASE / "data/metadata/generation_plant_mapping.csv"

g = pd.read_csv(GEN)
m = pd.read_csv(META)

plants = (
    g[["PlantName", "Type", "Capacity_MW"]]
    .drop_duplicates()
    .reset_index(drop=True)
)

# Start with an empty, conservative mapping.
mapping = plants.copy()

mapping["MetadataMatch"] = ""
mapping["District"] = ""
mapping["Latitude"] = ""
mapping["Longitude"] = ""
mapping["CommissionDate"] = ""
mapping["MatchStatus"] = "Unverified"

# Known location clues from CEA plant names.
location_rules = {
    "KOPPAL": "Koppal",
    "GADAG": "Gadag",
    "PAVAGADA": "Tumakuru",
    "TUMKUR": "Tumakuru",
}

for i, row in mapping.iterrows():

    name = str(row["PlantName"]).upper()

    for keyword, district in location_rules.items():

        if keyword in name:

            mapping.loc[i, "District"] = district
            mapping.loc[i, "MatchStatus"] = "Probable"

            break

mapping.to_csv(OUT, index=False)

print("=" * 70)
print("CONSERVATIVE PLANT MAPPING CREATED")
print("=" * 70)

print("Rows:", len(mapping))
print("Verified:", (mapping.MatchStatus == "Verified").sum())
print("Probable:", (mapping.MatchStatus == "Probable").sum())
print("Unverified:", (mapping.MatchStatus == "Unverified").sum())

print("\nMapping:")
print(mapping.to_string(index=False))

print("\nSaved:")
print(OUT)
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

MAPPING = BASE_DIR / "data" / "metadata" / "plant_weather_mapping.csv"
METADATA = BASE_DIR / "data" / "metadata" / "plants_geocoded.csv"

mapping = pd.read_csv(MAPPING)
metadata = pd.read_csv(METADATA)

unmapped = (
    mapping[mapping["MappingStatus"] == "Unmapped"]
    [["PlantName", "Type", "Capacity_MW"]]
    .drop_duplicates()
)

print("=" * 80)
print("UNMAPPED PLANT INVESTIGATION")
print("=" * 80)

for _, plant in unmapped.iterrows():

    name = str(plant["PlantName"])
    ptype = str(plant["Type"]).lower()
    capacity = float(plant["Capacity_MW"])

    print("\n" + "-" * 80)
    print(f"CEA: {name} | {ptype} | {capacity} MW")

    m = metadata.copy()

    m["_type"] = (
        m["Type"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    m["_capacity_diff"] = (
        pd.to_numeric(m["Capacity_MW"], errors="coerce") - capacity
    ).abs()

    if "solar" in ptype:
        candidates = m[
            m["_type"].str.contains("solar", na=False)
            & (m["_capacity_diff"] <= 10)
        ].copy()

    elif "wind" in ptype:
        candidates = m[
            m["_type"].str.contains("wind", na=False)
            & (m["_capacity_diff"] <= 10)
        ].copy()

    else:
        candidates = pd.DataFrame()

    if len(candidates) == 0:
        print("  No same-type capacity candidates")
        continue

    cols = [
        "PlantName",
        "Capacity_MW",
        "Type",
        "District",
        "Latitude",
        "Longitude",
        "CommissionDate",
        "_capacity_diff",
    ]

    print(
        candidates[
            cols
        ]
        .sort_values("_capacity_diff")
        .head(10)
        .to_string(index=False)
    )

print("\n" + "=" * 80)
print("INVESTIGATION COMPLETE")
print("=" * 80)
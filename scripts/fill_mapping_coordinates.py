import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

MAP = BASE / "data/metadata/generation_plant_mapping.csv"
OUT = MAP

df = pd.read_csv(MAP)

coords = {
    "Koppal": (15.574824, 76.311849),
    "Gadag": (15.416692, 75.681580),
    "Tumakuru": (13.419251, 76.881000),
}

for i, row in df.iterrows():

    district = row["District"]

    if district in coords:
        lat, lon = coords[district]

        df.loc[i, "Latitude"] = lat
        df.loc[i, "Longitude"] = lon

df.to_csv(OUT, index=False)

print("=" * 70)
print("COORDINATES FILLED")
print("=" * 70)

print(
    df[
        df["MatchStatus"] == "Probable"
    ][
        [
            "PlantName",
            "Type",
            "Capacity_MW",
            "District",
            "Latitude",
            "Longitude",
            "MatchStatus",
        ]
    ].to_string(index=False)
)

print("\nSaved:", OUT)
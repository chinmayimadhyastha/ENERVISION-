from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

GEN = BASE_DIR / "data" / "generation" / "generation_combined.csv"
MAP = BASE_DIR / "data" / "metadata" / "plant_weather_mapping.csv"

g = pd.read_csv(GEN)
m = pd.read_csv(MAP)

unmapped = m[m["MappingStatus"] == "Unmapped"][
    ["PlantName", "Type", "Capacity_MW"]
].drop_duplicates()

print("=" * 80)
print("GENERATION LOCATION EVIDENCE")
print("=" * 80)

for _, r in unmapped.iterrows():

    name = r["PlantName"]

    x = g[
        (g["PlantName"] == name) &
        (g["Type"] == r["Type"]) &
        (g["Capacity_MW"] == r["Capacity_MW"])
    ].copy()

    print("\n" + "-" * 80)
    print(name, "|", r["Type"], "|", r["Capacity_MW"], "MW")
    print("Rows:", len(x))
    print("Date:", x["Date"].min(), "to", x["Date"].max())

    if "State" in x.columns:
        print("States:", x["State"].dropna().unique().tolist())

    if "Owner" in x.columns:
        print("Owners:", x["Owner"].dropna().unique().tolist())

print("\n" + "=" * 80)
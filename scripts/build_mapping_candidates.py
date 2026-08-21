import pandas as pd
from pathlib import Path
from difflib import SequenceMatcher

BASE = Path(__file__).resolve().parent.parent

GEN = BASE / "data/generation/generation_combined.csv"
META = BASE / "data/metadata/plants_geocoded.csv"
OUT = BASE / "data/metadata/mapping_candidates.csv"

g = pd.read_csv(GEN)
m = pd.read_csv(META)

plants = (
    g[["PlantName", "Type", "Capacity_MW"]]
    .drop_duplicates()
    .reset_index(drop=True)
)

# Normalize text
def norm(x):
    return (
        str(x)
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("\n", " ")
        .replace("  ", " ")
        .strip()
    )

gtype = g["Type"].astype(str).str.lower()
mtype = m["Type"].astype(str).str.lower()

results = []

for _, p in plants.iterrows():

    pname = norm(p["PlantName"])
    ptype = str(p["Type"]).lower()
    pcap = float(p["Capacity_MW"])

    candidates = []

    for _, x in m.iterrows():

        xtype = str(x["Type"]).lower()

        # Solar / solar variants
        if ptype == "solar" and "solar" not in xtype:
            continue

        # Wind
        if ptype == "wind" and "wind" not in xtype:
            continue

        cap = float(x["Capacity_MW"])

        # Capacity tolerance
        if abs(cap - pcap) > 10:
            continue

        name = norm(x["PlantName"])

        score = SequenceMatcher(None, pname, name).ratio()

        # Extra name-token similarity
        ptokens = set(pname.split())
        xtokens = set(name.split())

        common = len(ptokens & xtokens)

        score += min(common * 0.08, 0.24)

        candidates.append(
            (
                score,
                x["PlantName"],
                x["Capacity_MW"],
                x["Type"],
                x["District"],
                x["Latitude"],
                x["Longitude"],
                x["CommissionDate"],
            )
        )

    candidates.sort(reverse=True)

    for rank, c in enumerate(candidates[:3], start=1):

        results.append({
            "CEA_PlantName": p["PlantName"],
            "CEA_Type": p["Type"],
            "CEA_Capacity_MW": pcap,
            "Rank": rank,
            "MetadataMatch": c[1] if candidates else "",
            "MetadataCapacity_MW": c[2] if candidates else "",
            "MetadataType": c[3] if candidates else "",
            "District": c[4] if candidates else "",
            "Latitude": c[5] if candidates else "",
            "Longitude": c[6] if candidates else "",
            "CommissionDate": c[7] if candidates else "",
            "Score": round(c[0], 3) if candidates else 0,
        })

result = pd.DataFrame(results)

result.to_csv(OUT, index=False)

print("=" * 70)
print("MAPPING CANDIDATES CREATED")
print("=" * 70)
print("CEA plant/capacity combinations:", len(plants))
print("Candidate rows:", len(result))
print()
print("Saved:")
print(OUT)
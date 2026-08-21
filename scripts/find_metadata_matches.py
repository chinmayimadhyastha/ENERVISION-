import pandas as pd
from difflib import SequenceMatcher

GEN_FILE = "data/generation/generation_combined.csv"
META_FILE = "data/metadata/plants_geocoded.csv"

g = pd.read_csv(GEN_FILE)
m = pd.read_csv(META_FILE)

plants = (
    g[["PlantName", "Type", "Capacity_MW"]]
    .drop_duplicates()
    .sort_values("PlantName")
)

def normalize(text):
    return (
        str(text)
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )

print("=" * 80)
print("METADATA MATCH CANDIDATES")
print("=" * 80)

for _, row in plants.iterrows():

    cea_name = row["PlantName"]
    cea_type = str(row["Type"]).lower()
    cea_capacity = float(row["Capacity_MW"])

    candidates = []

    for _, meta in m.iterrows():

        meta_type = str(meta["Type"]).lower()

        # Type must match
        if meta_type != cea_type:
            continue

        meta_capacity = pd.to_numeric(
            meta["Capacity_MW"],
            errors="coerce"
        )

        if pd.isna(meta_capacity):
            continue

        # Capacity within 5 MW
        if abs(float(meta_capacity) - cea_capacity) > 5:
            continue

        score = SequenceMatcher(
            None,
            normalize(cea_name),
            normalize(meta["PlantName"])
        ).ratio()

        candidates.append({
            "PlantName": meta["PlantName"],
            "Capacity": meta_capacity,
            "District": meta["District"],
            "Latitude": meta["Latitude"],
            "Longitude": meta["Longitude"],
            "Score": score
        })

    candidates = sorted(
        candidates,
        key=lambda x: x["Score"],
        reverse=True
    )[:5]

    print()
    print(
        f"CEA: {cea_name} | "
        f"{cea_type} | "
        f"{cea_capacity} MW"
    )

    if not candidates:
        print("  NO CANDIDATES")
        continue

    for c in candidates:
        print(
            f"  → {c['PlantName']} | "
            f"{c['Capacity']} MW | "
            f"{c['District']} | "
            f"{c['Latitude']}, {c['Longitude']} | "
            f"score={c['Score']:.2f}"
        )
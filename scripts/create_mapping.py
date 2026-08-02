import pandas as pd
from rapidfuzz import process, fuzz
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

plants = pd.read_csv(BASE_DIR / "data" / "metadata" / "plants.csv")
gen = pd.read_csv(BASE_DIR / "data" / "generation" / "generation_clean.csv")

plant_names = plants["PlantName"].dropna().unique().tolist()
gen_names = gen["PlantName"].dropna().unique().tolist()

mapping = []

for g in gen_names:

    match = process.extractOne(
        g,
        plant_names,
        scorer=fuzz.token_sort_ratio
    )

    mapping.append({
        "GenerationName": g,
        "MatchedPlant": match[0],
        "Similarity": match[1]
    })

mapping = pd.DataFrame(mapping)

mapping.to_csv(
    BASE_DIR / "data" / "generation" / "plant_mapping.csv",
    index=False
)

print(mapping)
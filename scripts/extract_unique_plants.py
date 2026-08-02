import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

df = pd.read_csv(BASE_DIR / "data" / "generation" / "generation_clean.csv")

plants = (
    df[["PlantName"]]
    .drop_duplicates()
    .sort_values("PlantName")
)

plants["District"] = ""

plants.to_csv(
    BASE_DIR / "data" / "generation" / "isgs_plants.csv",
    index=False
)

print(plants)
import pandas as pd
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT = BASE_DIR / "data" / "generation" / "generation.csv"
OUTPUT = BASE_DIR / "data" / "generation" / "generation_clean.csv"

df = pd.read_csv(INPUT)

records = []

for _, row in df.iterrows():

    line = str(row["RawLine"]).strip()

    # Skip state summary rows
    if line.startswith("क") or line.startswith("Karnataka") or line.startswith("KARNATAKA"):
        continue

    # Split by whitespace
    tokens = line.split()

    if len(tokens) < 8:
        continue

    try:

        cumulative = float(tokens[-1])
        daily = float(tokens[-2])
        capacity = float(tokens[-3])

        energy_type = tokens[-4]

        # Find Karnataka index
        k_index = tokens.index("Karnataka")

        plant_name = " ".join(tokens[:k_index])

        owner = " ".join(tokens[k_index+1:-4])

        records.append({

            "Date": row["Date"],

            "PlantName": plant_name,

            "State": "Karnataka",

            "Owner": owner,

            "Type": energy_type,

            "Capacity_MW": capacity,

            "DailyGeneration_MU": daily,

            "CumulativeGeneration_MU": cumulative

        })

    except Exception:
        continue

clean = pd.DataFrame(records)

clean.to_csv(OUTPUT,index=False)

print(clean.head())

print()

print("Rows :",len(clean))

print("Plants :",clean["PlantName"].nunique())

print("Saved :",OUTPUT)
import pandas as pd
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data/generation/historical_generation.csv"
OUTPUT_FILE = BASE_DIR / "data/generation/historical_generation_clean.csv"

df = pd.read_csv(INPUT_FILE)

records = []

for _, row in df.iterrows():

    date = row["Date"]
    line = str(row["RawLine"]).strip()

    # Ignore Karnataka summary rows
    if line.startswith("Karnataka") or "Karnataka" in line and not re.search(
        r"Karnataka\s+Private\s+IPP\s+(Solar|Wind)",
        line
    ):
        continue

    # Plant-wise format:
    # PlantName Karnataka Owner Type Capacity DailyGeneration CumulativeGeneration

    match = re.match(
        r"^(.*?)\s+Karnataka\s+(.+?)\s+(Solar|Wind)\s+"
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$",
        line,
        re.IGNORECASE
    )

    if not match:
        continue

    plant = match.group(1).strip()
    owner = match.group(2).strip()
    energy_type = match.group(3).strip().title()

    capacity = float(match.group(4))
    daily_generation = float(match.group(5))
    cumulative_generation = float(match.group(6))

    records.append({
        "Date": date,
        "PlantName": plant,
        "State": "Karnataka",
        "Owner": owner,
        "Type": energy_type,
        "Capacity_MW": capacity,
        "DailyGeneration_MU": daily_generation,
        "CumulativeGeneration_MU": cumulative_generation
    })


clean = pd.DataFrame(records)

clean["Date"] = pd.to_datetime(clean["Date"])

clean = clean.sort_values(
    ["Date", "PlantName"]
).reset_index(drop=True)

clean.to_csv(
    OUTPUT_FILE,
    index=False
)

print(clean.head(20).to_string(index=False))

print("\nRows:", len(clean))

print("\nPlants:", clean["PlantName"].nunique())

print("\nTypes:")
print(clean["Type"].value_counts())

print("\nDate range:")
print(clean["Date"].min(), "to", clean["Date"].max())

print("\nSaved:")
print(OUTPUT_FILE)
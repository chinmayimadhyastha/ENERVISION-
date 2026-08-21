import pandas as pd
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "generation" / "generation.csv"

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "generation"
    / "generation_clean_parsed.csv"
)

df = pd.read_csv(INPUT_FILE)

records = []

for _, row in df.iterrows():

    date = row["Date"]
    line = str(row["RawLine"]).strip()

    # Only Karnataka plant rows
    if "Karnataka" not in line:
        continue

    # Ignore Karnataka state-summary rows
    if "Private IPP" not in line:
        continue

    # Expected structure:
    #
    # PlantName Karnataka Private IPP Solar/Wind
    # Capacity DailyGeneration CumulativeGeneration

    match = re.match(
        r"^(.*?)\s+"
        r"Karnataka\s+"
        r"Private\s+IPP\s+"
        r"(Solar|Wind)\s+"
        r"([\d.]+)\s+"
        r"([\d.]+)\s+"
        r"([\d.]+)\s*$",
        line,
        re.IGNORECASE
    )

    if not match:
        continue

    plant = match.group(1).strip()

    energy_type = match.group(2).strip().title()

    capacity = float(match.group(3))

    daily_generation = float(match.group(4))

    cumulative_generation = float(match.group(5))

    records.append({
        "Date": date,
        "PlantName": plant,
        "State": "Karnataka",
        "Owner": "Private IPP",
        "Type": energy_type,
        "Capacity_MW": capacity,
        "DailyGeneration_MU": daily_generation,
        "CumulativeGeneration_MU": cumulative_generation
    })


clean = pd.DataFrame(records)

clean["Date"] = pd.to_datetime(clean["Date"])

clean = (
    clean
    .sort_values(["Date", "PlantName"])
    .drop_duplicates(
        subset=["Date", "PlantName"],
        keep="last"
    )
    .reset_index(drop=True)
)

clean.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nFirst rows:")
print(clean.head(20).to_string(index=False))

print("\nRows:", len(clean))

print("\nPlants:", clean["PlantName"].nunique())

print("\nTypes:")
print(clean["Type"].value_counts())

print("\nDate range:")
print(clean["Date"].min(), "to", clean["Date"].max())

print("\nSaved:")
print(OUTPUT_FILE)
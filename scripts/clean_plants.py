import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load extracted data
df = pd.read_csv(BASE_DIR / "data" / "metadata" / "karnataka_raw.csv")

# Rename columns
df.columns = [
    "SerialNo",
    "PlantName",
    "Capacity_MW",
    "Type",
    "District",
    "State",
    "CommissionDate"
]

# Remove completely empty rows
df = df.dropna(how="all")

# Remove rows where PlantName is missing
df = df[df["PlantName"].notna()]

# Remove Total rows
df = df[
    ~df["PlantName"]
    .astype(str)
    .str.contains("Total", case=False, na=False)
]

# Clean spaces
for col in df.columns:
    df[col] = df[col].astype(str).str.strip()

# Convert Capacity
df["Capacity_MW"] = pd.to_numeric(
    df["Capacity_MW"],
    errors="coerce"
)

# Convert Date
df["CommissionDate"] = pd.to_datetime(
    df["CommissionDate"],
    errors="coerce"
)

# Create PlantID
df.insert(0, "PlantID", range(1, len(df) + 1))

# Save
output = BASE_DIR / "data" / "metadata" / "plants.csv"

df.to_csv(output, index=False)

print(df.head())

print("\n--------------------------------")

print("Plants :", len(df))

print("Saved :", output)
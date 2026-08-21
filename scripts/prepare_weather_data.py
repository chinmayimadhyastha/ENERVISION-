from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT = BASE_DIR / "data" / "weather" / "weather_raw.csv"
OUTPUT = BASE_DIR / "data" / "weather" / "weather_clean.csv"

df = pd.read_csv(INPUT)

df["Date"] = pd.to_datetime(
    df["Date"].astype(str),
    format="%Y%m%d",
    errors="coerce"
)

df = df.sort_values(["District", "Date"]).reset_index(drop=True)

df.to_csv(OUTPUT, index=False)

print("=" * 70)
print("WEATHER DATA PREPARED")
print("=" * 70)
print("Rows:", len(df))
print("Districts:", df["District"].nunique())
print("Date:", df["Date"].min(), "to", df["Date"].max())
print("Missing values:", df.isna().sum().sum())
print("Duplicates:", df.duplicated(["District", "Date"]).sum())
print("Saved:")
print(OUTPUT)
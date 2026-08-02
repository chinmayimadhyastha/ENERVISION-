import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

df = pd.read_csv(BASE_DIR / "data" / "metadata" / "plants.csv")

df["District"] = (
    df["District"]
    .astype(str)
    .str.replace("\n", "", regex=False)
    .str.strip()
)

replacements = {
    "Davanegere": "Davanagere",
    "Belgaum": "Belagavi",
    "Bagalkote": "Bagalkot",
    "Bijapur": "Vijayapura",
    "Gulbarga": "Kalaburagi",
    "Kalaburgi": "Kalaburagi",
    "Bellary": "Ballari",
    "Uttarakannada": "Uttara Kannada",
    "DakshinaKannada": "Dakshina Kannada",
    "Chamarajanagar": "Chamarajanagar",
    "Chikkamagalore": "Chikkamagaluru",
    "Vijaypura": "Vijayapura",
    "Vijayapra": "Vijayapura",
    "Tumkur": "Tumakuru",
    "Mysore": "Mysuru",
    "Location(District)": None
}

df["District"] = df["District"].replace(replacements)

# Remove accidental header rows
df = df[df["District"].notna()]

df.to_csv(BASE_DIR / "data" / "metadata" / "plants.csv", index=False)

print(df["District"].unique())
print("Saved!")
import pdfplumber
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import re

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "data" / "generation" / "historical_raw"

OUTPUT_FILE = BASE_DIR / "data" / "generation" / "historical_generation.csv"

files = sorted(INPUT_DIR.glob("DailyRE*.pdf"))

print(f"Found {len(files)} historical reports")

rows = []

for pdf_file in tqdm(files):

    # Get date from filename
    match = re.search(r"(\d{8})$", pdf_file.stem)

    if not match:
        continue

    date_raw = match.group(1)

    date = pd.to_datetime(
        date_raw,
        format="%d%m%Y",
        errors="coerce"
    )

    if pd.isna(date):
        continue

    try:

        with pdfplumber.open(pdf_file) as pdf:

            for page in pdf.pages:

                text = page.extract_text()

                if not text:
                    continue

                for line in text.split("\n"):

                    # Keep Karnataka lines
                    if "Karnataka" not in line:
                        continue

                    rows.append({
                        "Date": date.strftime("%Y-%m-%d"),
                        "RawLine": line.strip()
                    })

    except Exception as e:

        print(f"\nFailed: {pdf_file.name}")
        print(e)


df = pd.DataFrame(rows)

print("\n")
print(df.head())

print("\nRows:", len(df))

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nSaved:")
print(OUTPUT_FILE)
import pdfplumber
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import re

BASE_DIR = Path(__file__).resolve().parent.parent

PDF_FOLDER = BASE_DIR / "data" / "generation" / "raw"

OUTPUT = BASE_DIR / "data" / "generation" / "generation.csv"

rows = []

pdf_files = sorted(PDF_FOLDER.glob("*.pdf"))

print(f"Found {len(pdf_files)} reports")

for pdf_file in tqdm(pdf_files):

    report_date = pdf_file.stem.replace("Report-", "")

    try:

        with pdfplumber.open(pdf_file) as pdf:

            for page in pdf.pages:

                text = page.extract_text()

                if not text:
                    continue

                # Only Karnataka entries
                if "KARNATAKA" not in text.upper():
                    continue

                lines = text.split("\n")

                for line in lines:

                    if "KARNATAKA" not in line.upper():
                        continue

                    line = re.sub(r"\s+", " ", line)

                    rows.append({
                        "Date": report_date,
                        "RawLine": line
                    })

    except Exception as e:
        print(pdf_file.name, e)

df = pd.DataFrame(rows)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(OUTPUT, index=False)

print(df.head())

print()

print("Rows :", len(df))

print("Saved Successfully!")
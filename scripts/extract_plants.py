import pdfplumber
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
pdf_path = BASE_DIR / "Plant-wise details of RE Installed Capacity-merged.pdf"

rows = []

print("Opening PDF...")

with pdfplumber.open(pdf_path) as pdf:

    # Only Karnataka pages
    for page_no in range(220, 244):   # Python index (221–244)

        print(f"Reading page {page_no+1}")

        page = pdf.pages[page_no]

        tables = page.extract_tables()

        if not tables:
            continue

        for table in tables:

            if len(table) < 2:
                continue

            header = table[0]

            for row in table[1:]:

                if row:
                    rows.append(row)

print("\nTotal Rows:", len(rows))

df = pd.DataFrame(rows)

output = BASE_DIR / "data" / "metadata"
output.mkdir(parents=True, exist_ok=True)

df.to_csv(output / "karnataka_raw.csv", index=False)

print("Saved Successfully!")
import requests
from pathlib import Path
from datetime import datetime, timedelta
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent

SAVE_DIR = BASE_DIR / "data" / "generation" / "raw"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

START = datetime(2025,1,1)
END   = datetime(2025,7,31)

current = START

while current <= END:

    date_str = current.strftime("%Y-%m-%d")

    url = (
        f"https://gen-re.cea.gov.in/public/uploads/"
        f"dailyReport/pdf/Report-{date_str}.pdf"
    )

    file_path = SAVE_DIR / f"Report-{date_str}.pdf"

    if file_path.exists():

        current += timedelta(days=1)
        continue

    try:

        r = requests.get(url,timeout=30)

        if r.status_code == 200 and len(r.content) > 5000:

            with open(file_path,"wb") as f:

                f.write(r.content)

            print(f"Downloaded {date_str}")

        else:

            print(f"Missing {date_str}")

    except Exception as e:

        print(date_str,e)

    current += timedelta(days=1)

print("\nFinished!")
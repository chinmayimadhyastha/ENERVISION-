import requests
import pandas as pd
from pathlib import Path
from tqdm import tqdm

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "metadata" / "plants_geocoded.csv"

OUTPUT_DIR = BASE_DIR / "data" / "weather"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "20180101"
END_DATE = "20261231"

PARAMETERS = "T2M,RH2M,WS2M,ALLSKY_SFC_SW_DWN,PS"

# ---------------------------------------------------
# LOAD PLANTS
# ---------------------------------------------------

plants = pd.read_csv(INPUT_FILE)

# Only unique coordinates
coords = plants[
    ["District", "Latitude", "Longitude"]
].drop_duplicates()

print(f"\nUnique Locations : {len(coords)}\n")

# ---------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------

all_weather = []

for _, row in tqdm(coords.iterrows(), total=len(coords)):

    district = row["District"]
    lat = row["Latitude"]
    lon = row["Longitude"]

    url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?parameters={PARAMETERS}"
        f"&community=RE"
        f"&longitude={lon}"
        f"&latitude={lat}"
        f"&start={START_DATE}"
        f"&end={END_DATE}"
        "&format=JSON"
    )

    try:

        response = requests.get(url, timeout=60)

        data = response.json()["properties"]["parameter"]

        dates = list(data["T2M"].keys())

        for date in dates:

            all_weather.append({

                "District": district,

                "Latitude": lat,

                "Longitude": lon,

                "Date": date,

                "Temperature": data["T2M"].get(date),

                "Humidity": data["RH2M"].get(date),

                "WindSpeed": data["WS2M"].get(date),

                "GHI": data["ALLSKY_SFC_SW_DWN"].get(date),

                "Pressure": data["PS"].get(date)

            })

    except Exception as e:

        print(f"\nFailed : {district}")

        print(e)

weather = pd.DataFrame(all_weather)

weather.to_csv(

    OUTPUT_DIR / "weather_raw.csv",

    index=False

)

print("\n--------------------------------")

print(weather.head())

print("\nRows :", len(weather))

print("\nSaved Successfully!")
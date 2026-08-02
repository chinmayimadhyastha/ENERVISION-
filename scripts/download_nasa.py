import os
import requests
import pandas as pd
from tqdm import tqdm

BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

START = "20200101"
END = "20251231"

PARAMETERS = [
    "T2M",
    "RH2M",
    "WS2M",
    "ALLSKY_SFC_SW_DWN"
]

districts = pd.read_csv("../data/districts.csv")

all_data = []

os.makedirs("../data/raw", exist_ok=True)

for _, row in tqdm(districts.iterrows(), total=len(districts)):

    district = row["District"]
    lat = row["Latitude"]
    lon = row["Longitude"]

    params = {
        "parameters": ",".join(PARAMETERS),
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": START,
        "end": END,
        "format": "JSON"
    }

    response = requests.get(BASE_URL, params=params)

    if response.status_code != 200:
        print(f"Failed : {district}")
        continue

    data = response.json()["properties"]["parameter"]

    dates = list(data["T2M"].keys())

    district_rows = []

    for date in dates:

        district_rows.append({
            "Date": date,
            "District": district,
            "Latitude": lat,
            "Longitude": lon,
            "Temperature": data["T2M"].get(date),
            "Humidity": data["RH2M"].get(date),
            "WindSpeed": data["WS2M"].get(date),
            "GHI": data["ALLSKY_SFC_SW_DWN"].get(date)
        })

    df = pd.DataFrame(district_rows)

    df.to_csv(f"../data/raw/{district}.csv", index=False)

    all_data.append(df)

master = pd.concat(all_data)

master.to_csv("../data/raw/karnataka_weather.csv", index=False)

print(master.head())
print(master.shape)
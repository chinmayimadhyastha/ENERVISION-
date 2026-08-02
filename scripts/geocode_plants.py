import pandas as pd
import time
from pathlib import Path
from geopy.geocoders import Nominatim
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent

df = pd.read_csv(BASE_DIR / "data" / "metadata" / "plants.csv")

geolocator = Nominatim(user_agent="enervision")

district_cache = {}

latitudes = []
longitudes = []

for district in tqdm(df["District"]):

    district = str(district).strip()

    if district in district_cache:
        lat, lon = district_cache[district]

    else:
        query = f"{district}, Karnataka, India"

        try:
            location = geolocator.geocode(query, timeout=10)

            if location:
                lat = location.latitude
                lon = location.longitude
            else:
                lat = None
                lon = None

        except:
            lat = None
            lon = None

        district_cache[district] = (lat, lon)

        time.sleep(1)

    latitudes.append(lat)
    longitudes.append(lon)

df["Latitude"] = latitudes
df["Longitude"] = longitudes

output = BASE_DIR / "data" / "metadata" / "plants_geocoded.csv"

df.to_csv(output, index=False)

print(df.head())

print("\nUnique Districts :", df["District"].nunique())
print("Geocoded Districts :", len(district_cache))
print("Saved Successfully!")
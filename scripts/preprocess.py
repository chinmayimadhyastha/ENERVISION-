import pandas as pd

# Load dataset
df = pd.read_csv("../data/raw/karnataka_weather.csv")

print("Original Shape:", df.shape)

# Remove duplicates
df = df.drop_duplicates()

# Remove missing values
df = df.dropna()

# Convert Date
df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d")

# Feature Engineering
df["Year"] = df["Date"].dt.year
df["Month"] = df["Date"].dt.month
df["Day"] = df["Date"].dt.day
df["DayOfYear"] = df["Date"].dt.dayofyear
df["Week"] = df["Date"].dt.isocalendar().week.astype(int)

# Seasons
def get_season(month):
    if month in [12,1,2]:
        return "Winter"
    elif month in [3,4,5]:
        return "Summer"
    elif month in [6,7,8,9]:
        return "Monsoon"
    else:
        return "Post-Monsoon"

df["Season"] = df["Month"].apply(get_season)

# ---------- TARGET VARIABLE ----------
PANEL_EFFICIENCY = 0.20
PERFORMANCE_RATIO = 0.80

df["SolarPotential"] = (
    df["GHI"]
    * PANEL_EFFICIENCY
    * PERFORMANCE_RATIO
)

# Save
df.to_csv("../data/processed/clean_dataset.csv", index=False)

print(df.head())
print(df.shape)
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent

INPUT = BASE / "data/final/plant_features_dataset.csv"
TRAIN = BASE / "data/final/plant_train.csv"
TEST = BASE / "data/final/plant_test.csv"

df = pd.read_csv(INPUT)
df["Date"] = pd.to_datetime(df["Date"])

df = df.sort_values(["PlantName", "Date"]).reset_index(drop=True)

# Last 20% of each plant = test set
train_parts = []
test_parts = []

for plant, group in df.groupby("PlantName"):
    group = group.sort_values("Date")

    split = int(len(group) * 0.80)

    train_parts.append(group.iloc[:split])
    test_parts.append(group.iloc[split:])

train = pd.concat(train_parts).reset_index(drop=True)
test = pd.concat(test_parts).reset_index(drop=True)

train.to_csv(TRAIN, index=False)
test.to_csv(TEST, index=False)

print("=" * 70)
print("PLANT-WISE TRAIN / TEST SPLIT")
print("=" * 70)

print("Train rows:", len(train))
print("Test rows:", len(test))

print("\nTrain date:", train.Date.min(), "to", train.Date.max())
print("Test date:", test.Date.min(), "to", test.Date.max())

print("\nTrain plants:", train.PlantName.nunique())
print("Test plants:", test.PlantName.nunique())

print("\nTrain types:")
print(train.Type.value_counts())

print("\nTest types:")
print(test.Type.value_counts())

print("\nSaved:")
print(TRAIN)
print(TEST)
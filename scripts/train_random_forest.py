import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

DATA = "data/final/plant_features_dataset.csv"
MODEL = "models/random_forest_model.pkl"
RESULTS = "data/results"

df = pd.read_csv(DATA)
df["Date"] = pd.to_datetime(df["Date"])

features = [
    "Capacity_MW",
    "Temperature",
    "Humidity",
    "WindSpeed",
    "GHI",
    "Pressure",
    "Temperature_lag_1",
    "Humidity_lag_1",
    "WindSpeed_lag_1",
    "GHI_lag_1",
    "Generation_lag_1",
    "Generation_lag_2",
    "Generation_lag_3",
    "Generation_lag_7",
    "Generation_roll_3",
    "Generation_roll_7",
    "Generation_per_MW",
    "Year",
    "Month",
    "DayOfYear",
    "DayOfWeek",
    "Month_sin",
    "Month_cos",
    "DayOfYear_sin",
    "DayOfYear_cos",
]

train = df[df["_split"] == "train"].copy()
test = df[df["_split"] == "test"].copy()

X_train = train[features]
y_train = train["DailyGeneration_MU"]

X_test = test[features]
y_test = test["DailyGeneration_MU"]

print("=" * 70)
print("RANDOM FOREST TRAINING")
print("=" * 70)
print("Train rows:", len(train))
print("Test rows:", len(test))
print("Features:", len(features))

model = RandomForestRegressor(
    n_estimators=300,
    random_state=42,
    n_jobs=-1,
    max_features="sqrt"
)

model.fit(X_train, y_train)

pred = model.predict(X_test)

mae = mean_absolute_error(y_test, pred)
rmse = np.sqrt(mean_squared_error(y_test, pred))
r2 = r2_score(y_test, pred)

Path("reports").mkdir(exist_ok=True)
Path("plots").mkdir(exist_ok=True)

# Update metrics file
metrics = pd.DataFrame([{
    "Model": "Random Forest",
    "MAE": mae,
    "RMSE": rmse,
    "R2": r2
}])

metrics.to_csv("reports/generation_metrics.csv", index=False)

print("\nOverall Performance")
print("-------------------")
print(f"MAE : {mae:.6f}")
print(f"RMSE: {rmse:.6f}")
print(f"R²  : {r2:.6f}")

test = test.copy()
test["PredictedGeneration_MU"] = pred
test["AbsoluteError"] = abs(
    test["DailyGeneration_MU"] - test["PredictedGeneration_MU"]
)

plant_results = []

for plant, group in test.groupby("PlantName"):
    actual = group["DailyGeneration_MU"]
    predicted = group["PredictedGeneration_MU"]

    plant_results.append({
        "PlantName": plant,
        "Type": group["Type"].iloc[0],
        "MAE": mean_absolute_error(actual, predicted),
        "RMSE": np.sqrt(mean_squared_error(actual, predicted)),
        "R2": r2_score(actual, predicted) if len(group) > 1 else np.nan,
        "Rows": len(group)
    })

plant_results = pd.DataFrame(plant_results)

print("\nPlant-wise Performance")
print("----------------------")
print(plant_results.to_string(index=False))

importance = pd.DataFrame({
    "Feature": features,
    "Importance": model.feature_importances_
}).sort_values("Importance", ascending=False)

print("\nTop Features")
print("------------")
print(importance.head(10).to_string(index=False))

Path("models").mkdir(exist_ok=True)
Path(RESULTS).mkdir(exist_ok=True)
Path("reports").mkdir(exist_ok=True)

with open(MODEL, "wb") as f:
    pickle.dump(model, f)

test.to_csv(f"{RESULTS}/random_forest_predictions.csv", index=False)
plant_results.to_csv(f"{RESULTS}/random_forest_plant_performance.csv", index=False)
importance.to_csv(f"{RESULTS}/random_forest_feature_importance.csv", index=False)

# Update report files
importance.to_csv("reports/generation_feature_importance.csv", index=False)

print("\nSaved:")
print(MODEL)
print(f"{RESULTS}/random_forest_predictions.csv")
print(f"{RESULTS}/random_forest_plant_performance.csv")
print(f"{RESULTS}/random_forest_feature_importance.csv")

# ============================================================
# UPDATE PLOTS
# ============================================================

# 1. Actual vs Predicted
plt.figure(figsize=(8, 6))
plt.scatter(
    test["DailyGeneration_MU"],
    test["PredictedGeneration_MU"],
    alpha=0.5
)

min_val = min(
    test["DailyGeneration_MU"].min(),
    test["PredictedGeneration_MU"].min()
)
max_val = max(
    test["DailyGeneration_MU"].max(),
    test["PredictedGeneration_MU"].max()
)

plt.plot([min_val, max_val], [min_val, max_val], linestyle="--")

plt.xlabel("Actual Generation (MU)")
plt.ylabel("Predicted Generation (MU)")
plt.title("Random Forest: Actual vs Predicted Generation")
plt.tight_layout()
plt.savefig("plots/random_forest_actual_vs_predicted.png", dpi=300)
plt.close()


# 2. Feature Importance
top_features = importance.head(10).sort_values("Importance")

plt.figure(figsize=(9, 6))
plt.barh(
    top_features["Feature"],
    top_features["Importance"]
)

plt.xlabel("Importance")
plt.ylabel("Feature")
plt.title("Random Forest: Top 10 Feature Importance")
plt.tight_layout()
plt.savefig("plots/random_forest_feature_importance.png", dpi=300)
plt.close()

# 3. Prediction Error Distribution
test["PredictionError"] = (
    test["DailyGeneration_MU"] - test["PredictedGeneration_MU"]
)

plt.figure(figsize=(8, 6))
plt.hist(test["PredictionError"], bins=40)

plt.xlabel("Prediction Error (MU)")
plt.ylabel("Frequency")
plt.title("Random Forest: Prediction Error Distribution")
plt.tight_layout()
plt.savefig("plots/random_forest_prediction_error_distribution.png", dpi=300)
plt.close()

print("plots/random_forest_actual_vs_predicted.png")
print("plots/random_forest_feature_importance.png")
print("reports/generation_metrics.csv")
print("plots/random_forest_prediction_error_distribution.png")
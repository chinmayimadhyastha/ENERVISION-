import os
import joblib
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

# -------------------------------------------------------
# Create folders if they don't exist
# -------------------------------------------------------
os.makedirs("../plots", exist_ok=True)
os.makedirs("../models", exist_ok=True)
os.makedirs("../reports", exist_ok=True)

# -------------------------------------------------------
# Load Dataset
# -------------------------------------------------------
print("Loading dataset...")

df = pd.read_csv("../data/processed/clean_dataset.csv")

# One-Hot Encoding
df = pd.get_dummies(df, columns=["District", "Season"])

# Features and Target
X = df.drop(columns=["Date", "GHI", "SolarPotential"])
y = df["GHI"]

# -------------------------------------------------------
# Train-Test Split
# -------------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)

print(f"Training Samples : {len(X_train)}")
print(f"Testing Samples  : {len(X_test)}")

# -------------------------------------------------------
# Hyperparameter Tuning
# -------------------------------------------------------
print("\nStarting GridSearchCV...\n")

param_grid = {
    "n_estimators": [100, 200],
    "max_depth": [10, None],
    "min_samples_split": [2],
    "min_samples_leaf": [1]
}

grid = GridSearchCV(
    estimator=RandomForestRegressor(random_state=42),
    param_grid=param_grid,
    cv=5,
    scoring="r2",
    n_jobs=-1,
    verbose=2
)

grid.fit(X_train, y_train)

print("\n===================================")
print("Best Parameters")
print(grid.best_params_)
print("Best Cross Validation Score :", grid.best_score_)
print("===================================\n")

rf = grid.best_estimator_

# -------------------------------------------------------
# Prediction
# -------------------------------------------------------
pred = rf.predict(X_test)

# -------------------------------------------------------
# Evaluation
# -------------------------------------------------------
mae = mean_absolute_error(y_test, pred)
rmse = mean_squared_error(y_test, pred) ** 0.5
r2 = r2_score(y_test, pred)

print("----------- MODEL PERFORMANCE -----------")
print(f"MAE  : {mae:.4f}")
print(f"RMSE : {rmse:.4f}")
print(f"R²   : {r2:.4f}")
print("-----------------------------------------")

# -------------------------------------------------------
# Save Model
# -------------------------------------------------------
joblib.dump(rf, "../models/random_forest.pkl")
print("✅ Model saved")

# -------------------------------------------------------
# Feature Importance
# -------------------------------------------------------
importance = pd.Series(
    rf.feature_importances_,
    index=X.columns
).sort_values(ascending=False)

plt.figure(figsize=(12, 8))
importance.head(15).sort_values().plot(kind="barh")

plt.title("Top 15 Feature Importance")
plt.xlabel("Importance Score")
plt.tight_layout()

plt.savefig("../plots/feature_importance.png")
plt.close()

print("✅ Feature Importance saved")

# -------------------------------------------------------
# Actual vs Predicted
# -------------------------------------------------------
plt.figure(figsize=(8, 8))

plt.scatter(
    y_test,
    pred,
    alpha=0.5
)

plt.plot(
    [y_test.min(), y_test.max()],
    [y_test.min(), y_test.max()],
    color="red",
    linewidth=2
)

plt.xlabel("Actual GHI")
plt.ylabel("Predicted GHI")
plt.title("Actual vs Predicted")

plt.tight_layout()

plt.savefig("../plots/actual_vs_predicted.png")
plt.close()

print("✅ Actual vs Predicted saved")

# -------------------------------------------------------
# Residual Plot
# -------------------------------------------------------
residuals = y_test - pred

plt.figure(figsize=(8, 6))

plt.scatter(
    pred,
    residuals,
    alpha=0.5
)

plt.axhline(
    y=0,
    color="red",
    linestyle="--"
)

plt.xlabel("Predicted GHI")
plt.ylabel("Residual")

plt.title("Residual Plot")

plt.tight_layout()

plt.savefig("../plots/residual_plot.png")
plt.close()

print("✅ Residual Plot saved")

# -------------------------------------------------------
# Save Metrics
# -------------------------------------------------------
metrics = pd.DataFrame({
    "Metric": [
        "MAE",
        "RMSE",
        "R2"
    ],
    "Value": [
        mae,
        rmse,
        r2
    ]
})

metrics.to_csv(
    "../reports/random_forest_metrics.csv",
    index=False
)

print("✅ Metrics saved")

# -------------------------------------------------------
# Save Best Parameters
# -------------------------------------------------------
best_params = pd.DataFrame(
    [grid.best_params_]
)

best_params.to_csv(
    "../reports/random_forest_best_parameters.csv",
    index=False
)

print("✅ Best Parameters saved")

print("\n🎉 Member 1 Random Forest Pipeline Completed Successfully!")
import pandas as pd
from pathlib import Path
import joblib

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

import matplotlib.pyplot as plt

# ---------------------------------------------------
# Paths
# ---------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA = BASE_DIR / "data/final/final_training_dataset.csv"

MODEL_DIR = BASE_DIR / "models"
REPORT_DIR = BASE_DIR / "reports"
PLOT_DIR = BASE_DIR / "plots"

MODEL_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
PLOT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------
# Load dataset
# ---------------------------------------------------

df = pd.read_csv(DATA)

print(df.head())

# ---------------------------------------------------
# Feature Engineering
# ---------------------------------------------------

df["Date"] = pd.to_datetime(df["Date"])

df["Month"] = df["Date"].dt.month
df["Day"] = df["Date"].dt.day
df["DayOfYear"] = df["Date"].dt.dayofyear

# ---------------------------------------------------
# Features
# ---------------------------------------------------

X = df[
    [
        "Temperature",
        "Humidity",
        "WindSpeed",
        "GHI",
        "Pressure",
        "Capacity_MW",
        "District",
        "Type",
        "Month",
        "Day",
        "DayOfYear",
    ]
]

y = df["DailyGeneration_MU"]

categorical = ["District", "Type"]

numeric = [
    "Temperature",
    "Humidity",
    "WindSpeed",
    "GHI",
    "Pressure",
    "Capacity_MW",
    "Month",
    "Day",
    "DayOfYear",
]

# ---------------------------------------------------
# Preprocessing
# ---------------------------------------------------

preprocessor = ColumnTransformer(
    transformers=[
        (
            "cat",
            OneHotEncoder(handle_unknown="ignore"),
            categorical,
        ),
        (
            "num",
            "passthrough",
            numeric,
        ),
    ]
)

# ---------------------------------------------------
# Pipeline
# ---------------------------------------------------

pipeline = Pipeline(
    [
        ("prep", preprocessor),
        ("model", RandomForestRegressor(random_state=42)),
    ]
)

# ---------------------------------------------------
# Hyperparameter Search
# ---------------------------------------------------

params = {
    "model__n_estimators": [100, 200],
    "model__max_depth": [10, 20, None],
}

grid = GridSearchCV(
    pipeline,
    params,
    cv=5,
    scoring="r2",
    n_jobs=-1,
)

# ---------------------------------------------------
# Train Test Split
# ---------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
)

print("\nTraining Model...\n")

grid.fit(X_train, y_train)

best = grid.best_estimator_

pred = best.predict(X_test)

# ---------------------------------------------------
# Metrics
# ---------------------------------------------------

mae = mean_absolute_error(y_test, pred)
rmse = mean_squared_error(y_test, pred) ** 0.5
r2 = r2_score(y_test, pred)

metrics = pd.DataFrame(
    {
        "Metric": ["MAE", "RMSE", "R2"],
        "Value": [mae, rmse, r2],
    }
)

metrics.to_csv(
    REPORT_DIR / "generation_metrics.csv",
    index=False,
)

print(metrics)

# ---------------------------------------------------
# Save model
# ---------------------------------------------------

joblib.dump(
    best,
    MODEL_DIR / "generation_random_forest.pkl",
)

# ---------------------------------------------------
# Actual vs Predicted
# ---------------------------------------------------

plt.figure(figsize=(6, 6))

plt.scatter(y_test, pred)

plt.xlabel("Actual")

plt.ylabel("Predicted")

plt.title("Actual vs Predicted")

plt.tight_layout()

plt.savefig(PLOT_DIR / "generation_actual_vs_predicted.png")

plt.close()

# ---------------------------------------------------
# Residual Plot
# ---------------------------------------------------

residuals = y_test - pred

plt.figure(figsize=(6, 6))

plt.scatter(pred, residuals)

plt.axhline(0)

plt.xlabel("Predicted")

plt.ylabel("Residual")

plt.title("Residual Plot")

plt.tight_layout()

plt.savefig(PLOT_DIR / "generation_residual_plot.png")

plt.close()

# ---------------------------------------------------
# Feature Importance
# ---------------------------------------------------

feature_names = best.named_steps["prep"].get_feature_names_out()

importance = (
    pd.DataFrame(
        {
            "Feature": feature_names,
            "Importance": best.named_steps["model"].feature_importances_,
        }
    )
    .sort_values("Importance", ascending=False)
)

importance.to_csv(
    REPORT_DIR / "generation_feature_importance.csv",
    index=False,
)

plt.figure(figsize=(10, 6))

plt.barh(
    importance["Feature"][:15],
    importance["Importance"][:15],
)

plt.gca().invert_yaxis()

plt.tight_layout()

plt.savefig(PLOT_DIR / "generation_feature_importance.png")

plt.close()

print("\nModel Saved Successfully!")
print("Best Parameters:", grid.best_params_)
print("R² Score:", r2)
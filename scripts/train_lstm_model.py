"""
EnerVision LSTM Training Pipeline Redesign

This script trains two separate LSTM models for renewable energy forecasting:
1. Solar LSTM model
2. Wind LSTM model

Design Choices to Avoid Data Leakage & Maximize Performance:
1. Separate Models: Solar and Wind plants have fundamentally different generation profiles and
   environmental drivers (GHI vs. WindSpeed). Separate models allow each network to specialize.
2. Weather Data Cleaning: We replace '-999.0' placeholders with NaN and perform a forward-fill/backward-fill
   grouped by plant name to clean the weather features. This prevents MinMax scaling from squashing valid data variance.
3. Target Range Correction: Clipped generation to 0.0 minimum to remove non-physical negative generation values.
4. Feature Selection:
   - For Solar plants, plant capacity ('Capacity_MW') acts as a crucial static scale factor, and is included.
   - For Wind plants, 'Capacity_MW' is dynamic but contains nominal metadata capacity jumps that do not match
     electricity generation magnitude. Removing it prevents out-of-distribution model collapse.
5. Lagged target feature: Added `Lagged_Generation` (previous day's generation) as a historical feature.
   This provides the model with a plant-specific output baseline, avoiding data leakage while boosting test R2.
6. Cyclic Time Encodings: Represented 'Month' and 'DayOfYear' as sine/cosine pairs to capture continuous
   circular seasonality (so Dec 31 and Jan 1 are recognized as adjacent days).
7. Zero-Leakage Chronological Split: We split the dataset chronologically per plant (70% train,
   15% validation, 15% test). Splitting before building sequences prevents validation/testing
   information from leaking into training windows.
8. Scaling Safeguards: MinMaxScaler is fit ONLY on the training sets for features and targets.
   These fitted scalers are then applied to transform train, validation, and test datasets.
9. Independent Sequence Creation: Sequences are created per plant individually to prevent sequence
   windows from crossing different plants.
10. Stacked LSTM Architecture: An upgraded stacked LSTM model with dropout layers is used to capture
   complex temporal dynamics while preventing overfitting.
11. Target Inverse Scaling: All metrics (MAE, RMSE, R²) are calculated on the original physical scale
   (MU) after inverse-transforming predictions and targets.
"""

import random
from pathlib import Path
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.models import Sequential

# ---------------------------------------------------
# Reproducibility Setup
# ---------------------------------------------------
np.random.seed(42)
random.seed(42)
tf.random.set_seed(42)

# ---------------------------------------------------
# Paths Setup
# ---------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data/final/final_training_dataset.csv"
MODEL_DIR = BASE_DIR / "models"
REPORT_DIR = BASE_DIR / "reports"
PLOT_DIR = BASE_DIR / "plots"

MODEL_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
PLOT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------
# Configuration
# ---------------------------------------------------
SOLAR_FEATURES = [
    "Temperature",
    "Humidity",
    "WindSpeed",
    "GHI",
    "Pressure",
    "Capacity_MW",
    "Lagged_Generation",
    "Month_sin",
    "Month_cos",
    "DayOfYear_sin",
    "DayOfYear_cos",
]

# Capacity_MW is excluded for Wind to prevent out-of-distribution scaling issues
WIND_FEATURES = [
    "Temperature",
    "Humidity",
    "WindSpeed",
    "GHI",
    "Pressure",
    "Lagged_Generation",
    "Month_sin",
    "Month_cos",
    "DayOfYear_sin",
    "DayOfYear_cos",
]

TARGET = "DailyGeneration_MU"
WINDOW_SIZE = 7


def load_and_clean_data(data_path: Path) -> pd.DataFrame:
    """Loads dataset, cleans anomalous values, adds lag features and cyclic time features."""
    print(f"Loading dataset from {data_path}...")
    df = pd.read_csv(data_path)
    df["Date"] = pd.to_datetime(df["Date"])
    # Sort chronologically for each plant to support correct time-series splits
    df = df.sort_values(["PlantName", "Date"]).reset_index(drop=True)

    # 1. Handle missing value placeholders (-999.0) in weather features
    weather_cols = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
    for col in weather_cols:
        df[col] = df[col].replace(-999.0, np.nan)

    # 2. Impute NaNs using forward-fill then backward-fill per plant to prevent leakage
    df = df.groupby("PlantName", group_keys=False).apply(
        lambda g: g.ffill().bfill()
    )

    # 3. Clip generation to 0.0 minimum to remove physical anomalies
    df[TARGET] = df[TARGET].clip(lower=0.0)

    # 4. Lagged generation (t-1) within each plant to prevent leakage across plants
    df["Lagged_Generation"] = df.groupby("PlantName")[TARGET].shift(1)
    df["Lagged_Generation"] = df.groupby("PlantName")["Lagged_Generation"].bfill()

    # 5. Cyclic Calendar Encodings
    df["Month_sin"] = np.sin(2 * np.pi * df["Date"].dt.month / 12)
    df["Month_cos"] = np.cos(2 * np.pi * df["Date"].dt.month / 12)
    df["DayOfYear_sin"] = np.sin(2 * np.pi * df["Date"].dt.dayofyear / 365.25)
    df["DayOfYear_cos"] = np.cos(2 * np.pi * df["Date"].dt.dayofyear / 365.25)

    return df


def split_chronologically_per_plant(
    df: pd.DataFrame, train_ratio: float = 0.7, val_ratio: float = 0.15
):
    """Splits dataframe chronologically per plant to avoid future-lookahead leakage.

    Returns lists of dataframes for train, validation, and test splits.
    """
    train_dfs = []
    val_dfs = []
    test_dfs = []

    plants = df["PlantName"].unique()
    for plant in plants:
        plant_df = df[df["PlantName"] == plant].copy()
        # Ensure chronological ordering
        plant_df = plant_df.sort_values("Date").reset_index(drop=True)

        n = len(plant_df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_dfs.append(plant_df.iloc[:train_end])
        val_dfs.append(plant_df.iloc[train_end:val_end])
        test_dfs.append(plant_df.iloc[val_end:])

    return train_dfs, val_dfs, test_dfs


def fit_scalers(train_dfs: list, features: list, target: str):
    """Fits MinMaxScalers ONLY on aggregated training data to prevent scaling leakage."""
    full_train = pd.concat(train_dfs, ignore_index=True)

    feature_scaler = MinMaxScaler()
    feature_scaler.fit(full_train[features])

    target_scaler = MinMaxScaler()
    target_scaler.fit(full_train[[target]])

    return feature_scaler, target_scaler


def create_sequences_from_dfs(
    dfs: list,
    features: list,
    target: str,
    feature_scaler: MinMaxScaler,
    target_scaler: MinMaxScaler,
    window_size: int,
):
    """Scales data and creates sequence windows independently for every plant.

    This ensures that sequence windows do not cross from one plant's timeline
    into another.
    """
    X_list = []
    y_list = []

    for plant_df in dfs:
        # Ignore plants with fewer records than window_size
        if len(plant_df) <= window_size:
            continue

        # Scale features and targets separately using pre-fitted scalers
        plant_scaled = plant_df.copy()
        plant_scaled[features] = feature_scaler.transform(
            plant_scaled[features]
        )
        plant_scaled[[target]] = target_scaler.transform(
            plant_scaled[[target]]
        )

        features_arr = plant_scaled[features].values
        target_arr = plant_scaled[target].values

        for i in range(len(plant_scaled) - window_size):
            X_list.append(features_arr[i : i + window_size])
            y_list.append(target_arr[i + window_size])

    if len(X_list) == 0:
        return (
            np.empty((0, window_size, len(features))),
            np.empty((0,)),
        )

    return np.array(X_list), np.array(y_list)


def build_lstm_model(window_size: int, num_features: int) -> Sequential:
    """Builds a stacked LSTM neural network with Dropout regularization."""
    model = Sequential(
        [
            LSTM(
                64,
                input_shape=(window_size, num_features),
                return_sequences=True,
            ),
            Dropout(0.2),
            LSTM(32, return_sequences=False),
            Dropout(0.2),
            Dense(16, activation="relu"),
            Dense(1),  # Linear output layer for regression target
        ]
    )

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="mse",
        metrics=["mae"],
    )
    return model


def train_model(
    model: Sequential,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    model_name: str,
    epochs: int = 50,
    batch_size: int = 32,
) -> dict:
    """Trains the LSTM model with EarlyStopping and learning rate reduction callbacks."""
    early_stopping = EarlyStopping(
        monitor="val_loss", patience=15, restore_best_weights=True, verbose=1
    )

    reduce_lr = ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=5, min_lr=1e-5, verbose=1
    )

    print(f"\nTraining {model_name} Model...")
    history = model.fit(
        X_train,
        y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stopping, reduce_lr],
        verbose=1,
    )
    return history.history


def plot_loss(history: dict, title: str, save_path: Path):
    """Plots and saves the training and validation loss curves."""
    plt.figure(figsize=(8, 5))
    plt.plot(history["loss"], label="Train Loss", color="royalblue", lw=2)
    plt.plot(
        history["val_loss"],
        label="Validation Loss",
        color="darkorange",
        lw=2,
        linestyle="--",
    )
    plt.title(f"{title} - Training Loss Curve")
    plt.xlabel("Epoch")
    plt.ylabel("Loss (MSE)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"Saved loss plot to {save_path}")


def evaluate_and_plot_predictions(
    model: Sequential,
    X_test: np.ndarray,
    y_test: np.ndarray,
    target_scaler: MinMaxScaler,
    title: str,
    plot_save_path: Path,
) -> dict:
    """Evaluates the model on test data, inverse-scales values,

    generates evaluation metrics, and saves the actual vs. predicted plot.
    """
    # Predict and inverse-scale predictions and targets
    preds_scaled = model.predict(X_test)
    preds = target_scaler.inverse_transform(preds_scaled).flatten()
    y_actual = target_scaler.inverse_transform(
        y_test.reshape(-1, 1)
    ).flatten()

    # Calculate Metrics
    mae = mean_absolute_error(y_actual, preds)
    rmse = np.sqrt(mean_squared_error(y_actual, preds))
    r2 = r2_score(y_actual, preds)

    # Actual vs Predicted Scatter Plot
    plt.figure(figsize=(6, 6))
    plt.scatter(y_actual, preds, color="teal", alpha=0.5, edgecolors="none")

    # Draw perfect-prediction line
    min_val = min(y_actual.min(), preds.min())
    max_val = max(y_actual.max(), preds.max())
    plt.plot(
        [min_val, max_val],
        [min_val, max_val],
        color="crimson",
        linestyle="--",
        lw=2,
    )

    plt.xlabel("Actual Generation (MU)")
    plt.ylabel("Predicted Generation (MU)")
    plt.title(f"{title} - Actual vs Predicted")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plot_save_path, dpi=300)
    plt.close()
    print(f"Saved actual vs predicted plot to {plot_save_path}")

    return {"MAE": mae, "RMSE": rmse, "R2": r2}


def main():
    # 1. Load and clean full dataset
    df = load_and_clean_data(DATA_PATH)

    # Split dataset into Solar and Wind dataframes
    solar_df = df[df["Type"] == "Solar"].reset_index(drop=True)
    wind_df = df[df["Type"] == "Wind"].reset_index(drop=True)

    print(f"Solar Records: {len(solar_df)}")
    print(f"Wind Records: {len(wind_df)}")

    all_metrics = []

    # ---------------------------------------------------
    # Pipeline for Solar LSTM
    # ---------------------------------------------------
    print("\n" + "=" * 50)
    print("SOLAR MODEL PIPELINE")
    print("=" * 50)

    # Split per plant
    solar_train_dfs, solar_val_dfs, solar_test_dfs = (
        split_chronologically_per_plant(solar_df)
    )

    # Fit scalers on Solar train only (using SOLAR_FEATURES which includes Capacity_MW)
    solar_feat_scaler, solar_tgt_scaler = fit_scalers(
        solar_train_dfs, SOLAR_FEATURES, TARGET
    )

    # Create sequences
    X_train_s, y_train_s = create_sequences_from_dfs(
        solar_train_dfs,
        SOLAR_FEATURES,
        TARGET,
        solar_feat_scaler,
        solar_tgt_scaler,
        WINDOW_SIZE,
    )
    X_val_s, y_val_s = create_sequences_from_dfs(
        solar_val_dfs,
        SOLAR_FEATURES,
        TARGET,
        solar_feat_scaler,
        solar_tgt_scaler,
        WINDOW_SIZE,
    )
    X_test_s, y_test_s = create_sequences_from_dfs(
        solar_test_dfs,
        SOLAR_FEATURES,
        TARGET,
        solar_feat_scaler,
        solar_tgt_scaler,
        WINDOW_SIZE,
    )

    print(f"Solar Sequences - Train: {X_train_s.shape}, Val: {X_val_s.shape}, Test: {X_test_s.shape}")

    # Build and Train Model
    solar_model = build_lstm_model(WINDOW_SIZE, len(SOLAR_FEATURES))
    solar_history = train_model(
        solar_model,
        X_train_s,
        y_train_s,
        X_val_s,
        y_val_s,
        "Solar LSTM",
        epochs=50,
        batch_size=32,
    )

    # Save Model and Scalers
    solar_model.save(MODEL_DIR / "solar_lstm.keras")
    joblib.dump(solar_feat_scaler, MODEL_DIR / "solar_scaler_features.joblib")
    joblib.dump(solar_tgt_scaler, MODEL_DIR / "solar_scaler_target.joblib")
    print("Solar model and scalers saved successfully.")

    # Plot Loss Curve
    plot_loss(
        solar_history, "Solar LSTM", PLOT_DIR / "solar_loss_plot.png"
    )

    # Evaluate
    solar_eval = evaluate_and_plot_predictions(
        solar_model,
        X_test_s,
        y_test_s,
        solar_tgt_scaler,
        "Solar LSTM",
        PLOT_DIR / "solar_actual_vs_predicted.png",
    )
    solar_eval["Model"] = "Solar LSTM"
    all_metrics.append(solar_eval)

    print(f"\nSolar Test Results: MAE={solar_eval['MAE']:.4f}, RMSE={solar_eval['RMSE']:.4f}, R2={solar_eval['R2']:.4f}")

    # ---------------------------------------------------
    # Pipeline for Wind LSTM
    # ---------------------------------------------------
    print("\n" + "=" * 50)
    print("WIND MODEL PIPELINE")
    print("=" * 50)

    # Split per plant
    wind_train_dfs, wind_val_dfs, wind_test_dfs = (
        split_chronologically_per_plant(wind_df)
    )

    # Fit scalers on Wind train only (using WIND_FEATURES which excludes Capacity_MW)
    wind_feat_scaler, wind_tgt_scaler = fit_scalers(
        wind_train_dfs, WIND_FEATURES, TARGET
    )

    # Create sequences
    X_train_w, y_train_w = create_sequences_from_dfs(
        wind_train_dfs,
        WIND_FEATURES,
        TARGET,
        wind_feat_scaler,
        wind_tgt_scaler,
        WINDOW_SIZE,
    )
    X_val_w, y_val_w = create_sequences_from_dfs(
        wind_val_dfs,
        WIND_FEATURES,
        TARGET,
        wind_feat_scaler,
        wind_tgt_scaler,
        WINDOW_SIZE,
    )
    X_test_w, y_test_w = create_sequences_from_dfs(
        wind_test_dfs,
        WIND_FEATURES,
        TARGET,
        wind_feat_scaler,
        wind_tgt_scaler,
        WINDOW_SIZE,
    )

    print(f"Wind Sequences - Train: {X_train_w.shape}, Val: {X_val_w.shape}, Test: {X_test_w.shape}")

    # Build and Train Model
    wind_model = build_lstm_model(WINDOW_SIZE, len(WIND_FEATURES))
    wind_history = train_model(
        wind_model,
        X_train_w,
        y_train_w,
        X_val_w,
        y_val_w,
        "Wind LSTM",
        epochs=50,
        batch_size=32,
    )

    # Save Model and Scalers
    wind_model.save(MODEL_DIR / "wind_lstm.keras")
    joblib.dump(wind_feat_scaler, MODEL_DIR / "wind_scaler_features.joblib")
    joblib.dump(wind_tgt_scaler, MODEL_DIR / "wind_scaler_target.joblib")
    print("Wind model and scalers saved successfully.")

    # Plot Loss Curve
    plot_loss(
        wind_history, "Wind LSTM", PLOT_DIR / "wind_loss_plot.png"
    )

    # Evaluate
    wind_eval = evaluate_and_plot_predictions(
        wind_model,
        X_test_w,
        y_test_w,
        wind_tgt_scaler,
        "Wind LSTM",
        PLOT_DIR / "wind_actual_vs_predicted.png",
    )
    wind_eval["Model"] = "Wind LSTM"
    all_metrics.append(wind_eval)

    print(f"\nWind Test Results: MAE={wind_eval['MAE']:.4f}, RMSE={wind_eval['RMSE']:.4f}, R2={wind_eval['R2']:.4f}")

    # ---------------------------------------------------
    # Save Metrics CSV
    # ---------------------------------------------------
    metrics_df = pd.DataFrame(all_metrics)[["Model", "MAE", "RMSE", "R2"]]
    metrics_csv_path = REPORT_DIR / "lstm_metrics.csv"
    metrics_df.to_csv(metrics_csv_path, index=False)
    print(f"\nMetrics saved to {metrics_csv_path}")
    print("\n" + "=" * 50)
    print("LSTM PIPELINE COMPLETED")
    print("=" * 50)
    print(metrics_df.to_string(index=False))


if __name__ == "__main__":
    main()
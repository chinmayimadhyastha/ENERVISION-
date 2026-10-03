import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Set seed for reproducibility
np.random.seed(42)
tf.random.set_seed(42)

# File paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data/final/full_generation_weather_dataset.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
PLOTS_DIR = BASE_DIR / "plots"

# Input feature definition (12 features including rolling generation)
FEATURE_COLS = [
    "Capacity_MW",
    "Temperature",
    "Humidity",
    "WindSpeed",
    "GHI",
    "Pressure",
    "Month_sin",
    "Month_cos",
    "DayOfYear_sin",
    "DayOfYear_cos",
    "Lagged_Generation",
    "Rolling_Generation_7"
]
TARGET_COL = "DailyGeneration_MU"
SEQ_LEN = 7


def load_and_clean_data(file_path: Path):
    """
    Loads raw dataset, cleans invalid weather sentinel values (-999 or <= -900),
    imputes missing weather values per plant structure, clips target generation >= 0,
    engineers cyclical time features, plant-grouped lagged generation and 7-day rolling generation.
    """
    print("=" * 80)
    print("1. DATA LOADING AND CLEANING")
    print("=" * 80)
    df = pd.read_csv(file_path)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["PlantName", "Date"]).reset_index(drop=True)

    print(f"Raw dataset loaded: {len(df)} rows, {df['PlantName'].nunique()} plants.")
    print(f"Overall Date Range: {df['Date'].min().strftime('%Y-%m-%d')} to {df['Date'].max().strftime('%Y-%m-%d')}")
    print(f"Solar records: {(df['Type'] == 'Solar').sum()}, Wind records: {(df['Type'] == 'Wind').sum()}")

    # 1. Clean invalid weather sentinel values (-999 or <= -900)
    weather_cols = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
    for col in weather_cols:
        sentinels = (df[col] <= -900).sum()
        if sentinels > 0:
            print(f"Found {sentinels} sentinel values in '{col}'. Treating as NaN.")
            df[col] = df[col].mask(df[col] <= -900, np.nan)
        
        # Impute per plant: forward fill then backward fill
        df[col] = df.groupby("PlantName")[col].transform(lambda g: g.ffill().bfill())
        # Overall column mean fallback if an entire plant is missing
        if df[col].isna().sum() > 0:
            df[col] = df[col].fillna(df[col].mean())

    # 2. DailyGeneration_MU clipping for non-negative physical energy generation
    neg_count = (df[TARGET_COL] < 0).sum()
    if neg_count > 0:
        print(f"Found {neg_count} negative DailyGeneration_MU values. Clipping lower bound to 0.0 MU.")
        df[TARGET_COL] = df[TARGET_COL].clip(lower=0.0)

    # 3. Cyclical Temporal Features
    month = df["Date"].dt.month
    dayofyear = df["Date"].dt.dayofyear
    df["Month_sin"] = np.sin(2 * np.pi * month / 12)
    df["Month_cos"] = np.cos(2 * np.pi * month / 12)
    df["DayOfYear_sin"] = np.sin(2 * np.pi * dayofyear / 365.25)
    df["DayOfYear_cos"] = np.cos(2 * np.pi * dayofyear / 365.25)

    # 4. Lagged Generation and 7-Day Rolling Generation (shift 1 strictly per plant to prevent leakage)
    df["Lagged_Generation"] = df.groupby("PlantName")[TARGET_COL].shift(1)
    df["Rolling_Generation_7"] = df.groupby("PlantName")[TARGET_COL].transform(
        lambda g: g.shift(1).rolling(7).mean()
    )

    # Drop initial plant rows where lagged or rolling features are NaN
    init_rows = len(df)
    df = df.dropna(subset=["Lagged_Generation", "Rolling_Generation_7"]).reset_index(drop=True)
    print(f"Dropped {init_rows - len(df)} initial plant rows with missing lag/rolling features. Processed rows: {len(df)}.")

    # Duplicate check
    dups = df.duplicated(subset=["PlantName", "Date"]).sum()
    print(f"Duplicate PlantName + Date records: {dups}")

    return df


def split_time_based_per_plant(sub_df: pd.DataFrame, val_ratio: float = 0.20):
    """
    Splits each plant's data chronologically:
    - 2020-2025 data (Date <= 2025-12-31): Earlier portion -> Train, Later portion -> Val
    - Post-2025 data (Date >= 2026-01-01): Reserved strictly -> Test
    """
    plant_split_info = []
    train_rows = []

    for plant, group in sub_df.groupby("PlantName"):
        group = group.sort_values("Date").reset_index(drop=True)
        pre_2026 = group[group["Date"] <= "2025-12-31"]
        post_2025 = group[group["Date"] >= "2026-01-01"]

        if len(pre_2026) < SEQ_LEN + 1:
            continue

        n_pre = len(pre_2026)
        n_train = int(n_pre * (1.0 - val_ratio))

        train_part = pre_2026.iloc[:n_train]
        train_rows.append(train_part)

        # Record cutoffs for sequence assignment
        val_start_idx = len(train_part)
        test_start_idx = len(pre_2026)

        plant_split_info.append((group, val_start_idx, test_start_idx))

    if not train_rows:
        raise ValueError("No valid training rows found!")

    train_df = pd.concat(train_rows).reset_index(drop=True)
    return train_df, plant_split_info


def fit_scalers(train_df: pd.DataFrame, feature_cols: list = None):
    """
    Fits feature scaler and target scaler STRICTLY on the training portion (2020-2025 training data).
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLS

    feature_scaler = StandardScaler()
    target_scaler = StandardScaler()

    feature_scaler.fit(train_df[feature_cols])
    target_scaler.fit(train_df[[TARGET_COL]])

    return feature_scaler, target_scaler


def create_sequences(plant_split_info, feature_scaler, target_scaler, feature_cols: list = None, seq_len: int = SEQ_LEN):
    """
    Constructs 7-day sequences (samples, timesteps, features) strictly per plant.
    Transforms features and targets using pre-fitted scalers.
    Assigns sequence to Train, Val, or Test based on target index location:
    - target index t < val_start_idx -> Train
    - val_start_idx <= t < test_start_idx -> Validation
    - t >= test_start_idx -> Test
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLS

    X_tr, y_tr = [], []
    X_v, y_v = [], []
    X_te, y_te = [], []

    date_tr, date_v, date_te = [], [], []

    for group, val_start_idx, test_start_idx in plant_split_info:
        X_scaled = feature_scaler.transform(group[feature_cols])
        y_scaled = target_scaler.transform(group[[TARGET_COL]]).flatten()
        dates = group["Date"].values

        for t in range(seq_len, len(group)):
            seq = X_scaled[t - seq_len : t]
            target = y_scaled[t]
            target_date = dates[t]

            if t < val_start_idx:
                X_tr.append(seq)
                y_tr.append(target)
                date_tr.append(target_date)
            elif t < test_start_idx:
                X_v.append(seq)
                y_v.append(target)
                date_v.append(target_date)
            else:
                X_te.append(seq)
                y_te.append(target)
                date_te.append(target_date)

    X_train, y_train = np.array(X_tr), np.array(y_tr)
    X_val, y_val = np.array(X_v), np.array(y_v)
    X_test, y_test = np.array(X_te), np.array(y_te)

    dates_dict = {
        "train": (pd.to_datetime(date_tr).min(), pd.to_datetime(date_tr).max()) if len(date_tr) > 0 else (None, None),
        "val": (pd.to_datetime(date_v).min(), pd.to_datetime(date_v).max()) if len(date_v) > 0 else (None, None),
        "test": (pd.to_datetime(date_te).min(), pd.to_datetime(date_te).max()) if len(date_te) > 0 else (None, None)
    }

    return (X_train, y_train), (X_val, y_val), (X_test, y_test), dates_dict


def build_lstm_model(model_type: str, input_shape: tuple):
    """
    Builds the optimized LSTM architecture:
    Solar model: Input -> LSTM(64) -> Dropout(0.3) -> Dense(32, activation='relu') -> Dense(1)
                 Compiled with Nadam optimizer (lr=0.0001) for highest R^2 performance.
    Wind model:  Input -> LSTM(32) -> Dropout(0.2) -> Dense(16, activation='relu') -> Dense(1)
    """
    model = Sequential()
    if model_type.lower() == "solar":
        model.add(LSTM(64, input_shape=input_shape))
        model.add(Dropout(0.3))
        model.add(Dense(32, activation="relu"))
        model.add(Dense(1))
        model.compile(
            optimizer=tf.keras.optimizers.Nadam(learning_rate=0.0001),
            loss="mse"
        )
    elif model_type.lower() == "wind":
        model.add(LSTM(32, input_shape=input_shape))
        model.add(Dropout(0.2))
        model.add(Dense(16, activation="relu"))
        model.add(Dense(1))
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss="mse"
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    return model


def train_model(model, X_train, y_train, X_val, y_val, model_path: Path):
    """
    Trains the LSTM model with EarlyStopping, ReduceLROnPlateau, and ModelCheckpoint callbacks.
    """
    callbacks = [
        EarlyStopping(monitor="val_loss", patience=15, restore_best_weights=True),
        ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6),
        ModelCheckpoint(str(model_path), monitor="val_loss", save_best_only=True)
    ]

    history = model.fit(
        X_train,
        y_train,
        validation_data=(X_val, y_val),
        epochs=60,
        batch_size=32,
        shuffle=False,
        callbacks=callbacks,
        verbose=1
    )
    return history


def evaluate_model(model, X_test, y_test, target_scaler):
    """
    Predicts on test data, inverse transforms predictions and actuals to original MU scale,
    and computes MAE, RMSE, and R2 regression metrics.
    """
    preds_scaled = model.predict(X_test).flatten()
    y_test_scaled = y_test.flatten()

    y_pred = target_scaler.inverse_transform(preds_scaled.reshape(-1, 1)).flatten()
    y_true = target_scaler.inverse_transform(y_test_scaled.reshape(-1, 1)).flatten()

    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)

    return mae, rmse, r2, y_true, y_pred


def plot_results(history, y_true, y_pred, model_type: str, plots_dir: Path):
    """
    Generates and saves high-resolution loss and actual vs predicted plots.
    """
    plots_dir.mkdir(parents=True, exist_ok=True)
    title_prefix = model_type.capitalize()

    # 1. Loss Plot
    plt.figure(figsize=(8, 5))
    plt.plot(history.history["loss"], label="Training Loss (MSE)", linewidth=2)
    plt.plot(history.history["val_loss"], label="Validation Loss (MSE)", linewidth=2)
    plt.title(f"{title_prefix} LSTM: Training vs Validation Loss", fontsize=14, fontweight="bold")
    plt.xlabel("Epoch", fontsize=12)
    plt.ylabel("Loss (Scaled MSE)", fontsize=12)
    plt.legend(fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    loss_plot_path = plots_dir / f"{model_type.lower()}_lstm_loss.png"
    plt.savefig(loss_plot_path, dpi=300)
    plt.close()

    # 2. Actual vs Predicted Scatter Plot
    plt.figure(figsize=(8, 6))
    plt.scatter(y_true, y_pred, alpha=0.5, color="tab:orange" if model_type.lower() == "wind" else "tab:blue")
    min_val = min(y_true.min(), y_pred.min())
    max_val = max(y_true.max(), y_pred.max())
    plt.plot([min_val, max_val], [min_val, max_val], "k--", label="Ideal Prediction (y = x)", linewidth=1.5)
    plt.title(f"{title_prefix} LSTM: Actual vs Predicted Generation (MU)", fontsize=14, fontweight="bold")
    plt.xlabel("Actual Generation (MU)", fontsize=12)
    plt.ylabel("Predicted Generation (MU)", fontsize=12)
    plt.legend(fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    scatter_plot_path = plots_dir / f"{model_type.lower()}_lstm_actual_vs_predicted.png"
    plt.savefig(scatter_plot_path, dpi=300)
    plt.close()

    return loss_plot_path, scatter_plot_path


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Load and clean dataset
    df = load_and_clean_data(DATA_PATH)

    # Split dataset by Type
    solar_df = df[df["Type"] == "Solar"].copy()
    wind_df = df[df["Type"] == "Wind"].copy()

    results_summary = []

    for model_type, sub_df in [("solar", solar_df), ("wind", wind_df)]:
        print("\n" + "=" * 80)
        print(f"PROCESSING {model_type.upper()} DATASET AND MODEL")
        print("=" * 80)

        # Step 2: Time-based per-plant split
        train_df, plant_split_info = split_time_based_per_plant(sub_df, val_ratio=0.20)

        # Step 3: Fit scalers ONLY on 2020-2025 Training portion
        f_scaler, t_scaler = fit_scalers(train_df)

        # Save scalers
        f_scaler_path = MODELS_DIR / f"{model_type}_scaler_features.joblib"
        t_scaler_path = MODELS_DIR / f"{model_type}_scaler_target.joblib"
        joblib.dump(f_scaler, f_scaler_path)
        joblib.dump(t_scaler, t_scaler_path)
        print(f"Saved feature scaler -> {f_scaler_path}")
        print(f"Saved target scaler  -> {t_scaler_path}")

        # Step 4: Create plant-wise 7-day sequences
        (X_train, y_train), (X_val, y_val), (X_test, y_test), dates_dict = create_sequences(
            plant_split_info, f_scaler, t_scaler, seq_len=SEQ_LEN
        )

        print(f"\n{model_type.upper()} Sequence Shapes:")
        print(f"  Train: X = {X_train.shape}, y = {y_train.shape}")
        print(f"  Val  : X = {X_val.shape}, y = {y_val.shape}")
        print(f"  Test : X = {X_test.shape}, y = {y_test.shape}")

        print(f"\n{model_type.upper()} Date Ranges:")
        print(f"  Training   : {dates_dict['train'][0].strftime('%Y-%m-%d')} to {dates_dict['train'][1].strftime('%Y-%m-%d')}")
        print(f"  Validation : {dates_dict['val'][0].strftime('%Y-%m-%d')} to {dates_dict['val'][1].strftime('%Y-%m-%d')}")
        print(f"  Testing    : {dates_dict['test'][0].strftime('%Y-%m-%d')} to {dates_dict['test'][1].strftime('%Y-%m-%d')}")

        # Step 5: Build and train model
        model_path = MODELS_DIR / f"{model_type}_lstm.keras"
        model = build_lstm_model(model_type, input_shape=(SEQ_LEN, len(FEATURE_COLS)))
        print(f"\nTraining {model_type.upper()} LSTM Model...")
        history = train_model(model, X_train, y_train, X_val, y_val, model_path)

        # Step 6: Evaluate on post-2025 test period
        mae, rmse, r2, y_true, y_pred = evaluate_model(model, X_test, y_test, t_scaler)

        print(f"\n{model_type.upper()} LSTM TEST EVALUATION (POST-2025 TEST PERIOD):")
        print(f"  MAE  : {mae:.6f} MU")
        print(f"  RMSE : {rmse:.6f} MU")
        print(f"  R²   : {r2:.6f}")

        # Step 7: Plot loss and actual vs predicted
        l_plot, s_plot = plot_results(history, y_true, y_pred, model_type, PLOTS_DIR)

        results_summary.append({
            "Model": f"{model_type.capitalize()} LSTM",
            "MAE": mae,
            "RMSE": rmse,
            "R2": r2
        })

    # Step 8: Save evaluation metrics CSV report
    metrics_df = pd.DataFrame(results_summary)
    metrics_path = REPORTS_DIR / "lstm_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)

    print("\n" + "=" * 80)
    print("FINAL SUMMARY REPORT")
    print("=" * 80)
    print(metrics_df.to_string(index=False))
    print(f"\nSaved metrics report -> {metrics_path}")


if __name__ == "__main__":
    main()

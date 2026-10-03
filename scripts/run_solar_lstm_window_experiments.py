import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Set seed for reproducibility
def set_seeds(seed=42):
    np.random.seed(seed)
    tf.random.set_seed(seed)

set_seeds(42)

# File paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data/final/full_generation_weather_dataset.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
PLOTS_DIR = BASE_DIR / "plots"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

# Feature definitions
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
    "Lagged_Generation"
]
TARGET_COL = "DailyGeneration_MU"


def load_and_clean_solar_data(file_path: Path):
    df = pd.read_csv(file_path)
    df["Date"] = pd.to_datetime(df["Date"])
    
    # Solar only
    solar_df = df[df["Type"] == "Solar"].copy()
    solar_df = solar_df.sort_values(["PlantName", "Date"]).reset_index(drop=True)

    # Handle sentinel weather values (-900 or lower)
    weather_cols = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
    for col in weather_cols:
        solar_df[col] = solar_df[col].mask(solar_df[col] <= -900, np.nan)
        solar_df[col] = solar_df.groupby("PlantName")[col].transform(lambda g: g.ffill().bfill())
        if solar_df[col].isna().sum() > 0:
            solar_df[col] = solar_df[col].fillna(solar_df[col].mean())

    # Clip generation to non-negative
    solar_df[TARGET_COL] = solar_df[TARGET_COL].clip(lower=0.0)

    # Cyclical temporal features
    month = solar_df["Date"].dt.month
    dayofyear = solar_df["Date"].dt.dayofyear
    solar_df["Month_sin"] = np.sin(2 * np.pi * month / 12)
    solar_df["Month_cos"] = np.cos(2 * np.pi * month / 12)
    solar_df["DayOfYear_sin"] = np.sin(2 * np.pi * dayofyear / 365.25)
    solar_df["DayOfYear_cos"] = np.sin(2 * np.pi * dayofyear / 365.25)

    # Plant-wise Lagged Generation (shift 1)
    solar_df["Lagged_Generation"] = solar_df.groupby("PlantName")[TARGET_COL].shift(1)

    # Drop missing lag rows
    solar_df = solar_df.dropna(subset=["Lagged_Generation"]).reset_index(drop=True)
    return solar_df


def split_time_based_per_plant(solar_df: pd.DataFrame, max_seq_len: int, val_ratio: float = 0.20):
    plant_split_info = []
    train_rows = []

    for plant, group in solar_df.groupby("PlantName"):
        group = group.sort_values("Date").reset_index(drop=True)
        pre_2026 = group[group["Date"] <= "2025-12-31"]
        post_2025 = group[group["Date"] >= "2026-01-01"]

        if len(pre_2026) < max_seq_len + 1:
            continue

        n_pre = len(pre_2026)
        n_train = int(n_pre * (1.0 - val_ratio))

        train_part = pre_2026.iloc[:n_train]
        train_rows.append(train_part)

        val_start_idx = len(train_part)
        test_start_idx = len(pre_2026)

        plant_split_info.append((group, val_start_idx, test_start_idx))

    train_df = pd.concat(train_rows).reset_index(drop=True)
    return train_df, plant_split_info


def fit_scalers(train_df: pd.DataFrame):
    feature_scaler = StandardScaler()
    target_scaler = StandardScaler()

    feature_scaler.fit(train_df[FEATURE_COLS])
    target_scaler.fit(train_df[[TARGET_COL]])

    return feature_scaler, target_scaler


def create_sequences_for_window(plant_split_info, feature_scaler, target_scaler, seq_len: int):
    X_tr, y_tr = [], []
    X_v, y_v = [], []
    X_te, y_te = [], []
    date_tr, date_v, date_te = [], [], []

    for group, val_start_idx, test_start_idx in plant_split_info:
        X_scaled = feature_scaler.transform(group[FEATURE_COLS])
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

    return (np.array(X_tr), np.array(y_tr)), (np.array(X_v), np.array(y_v)), (np.array(X_te), np.array(y_te))


def build_best_solar_lstm(input_shape):
    """
    Current Best Architecture:
    Input -> LSTM(64, return_sequences=True) -> Dropout(0.3) -> LSTM(32) -> Dropout(0.3) -> Dense(16, relu) -> Dense(1)
    Optimizer: Nadam(learning_rate=0.0001)
    Loss: MSE
    """
    model = Sequential([
        Input(shape=input_shape),
        LSTM(64, return_sequences=True),
        Dropout(0.3),
        LSTM(32),
        Dropout(0.3),
        Dense(16, activation="relu"),
        Dense(1)
    ])
    model.compile(optimizer=tf.keras.optimizers.Nadam(learning_rate=0.0001), loss="mse")
    return model


def calculate_metrics(model, X, y, target_scaler, epsilon=1e-4):
    preds_scaled = model.predict(X, verbose=0).flatten()
    y_scaled = y.flatten()

    y_pred = target_scaler.inverse_transform(preds_scaled.reshape(-1, 1)).flatten()
    y_true = target_scaler.inverse_transform(y_scaled.reshape(-1, 1)).flatten()

    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)

    # Safe MAPE calculation on original MU scale
    mask = np.abs(y_true) > epsilon
    excluded_count = int(np.sum(~mask))
    if np.sum(mask) > 0:
        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0
    else:
        mape = np.nan

    return mae, rmse, r2, mape, excluded_count, y_true, y_pred


def run_window_experiment(X_train, y_train, X_val, y_val, X_test, y_test, target_scaler, window_size, seed=42):
    set_seeds(seed)
    
    input_shape = (X_train.shape[1], X_train.shape[2])
    model = build_best_solar_lstm(input_shape)

    callbacks = [
        EarlyStopping(monitor="val_loss", patience=15, restore_best_weights=True),
        ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6)
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=60,
        batch_size=32,
        shuffle=False,
        callbacks=callbacks,
        verbose=0
    )

    best_epoch = int(np.argmin(history.history["val_loss"]) + 1)
    val_loss = float(np.min(history.history["val_loss"]))

    val_mae, val_rmse, val_r2, val_mape, val_excl, _, _ = calculate_metrics(model, X_val, y_val, target_scaler)
    test_mae, test_rmse, test_r2, test_mape, test_excl, y_true_test, y_pred_test = calculate_metrics(model, X_test, y_test, target_scaler)

    return {
        "model": model,
        "history": history,
        "best_epoch": best_epoch,
        "val_loss": val_loss,
        "val_mae": val_mae,
        "val_rmse": val_rmse,
        "val_r2": val_r2,
        "val_mape": val_mape,
        "val_excl": val_excl,
        "test_mae": test_mae,
        "test_rmse": test_rmse,
        "test_r2": test_r2,
        "test_mape": test_mape,
        "test_excl": test_excl,
        "y_true_test": y_true_test,
        "y_pred_test": y_pred_test
    }


def main():
    print("=" * 80)
    print("EXPERIMENT: SEQUENCE WINDOW SIZE ONLY FOR SOLAR LSTM")
    print("=" * 80)

    # Load and clean solar data
    solar_df = load_and_clean_solar_data(DATA_PATH)
    
    # Split plants time-based
    max_window = 30
    train_df, plant_split_info = split_time_based_per_plant(solar_df, max_seq_len=max_window, val_ratio=0.20)

    # Fit scalers strictly on train_df
    feature_scaler, target_scaler = fit_scalers(train_df)

    window_sizes = [7, 14, 21, 30]
    records = []
    results_dict = {}

    print(f"\nEvaluating Window Sizes: {window_sizes}")
    for w in window_sizes:
        print("\n" + "-" * 60)
        print(f"Testing Window Size = {w} days")
        print("-" * 60)

        (X_tr, y_tr), (X_v, y_v), (X_te, y_te) = create_sequences_for_window(
            plant_split_info, feature_scaler, target_scaler, seq_len=w
        )

        print(f"  Sequence shapes for Window = {w}:")
        print(f"    Train: X = {X_tr.shape}, y = {y_tr.shape}")
        print(f"    Val  : X = {X_v.shape}, y = {y_v.shape}")
        print(f"    Test : X = {X_te.shape}, y = {y_te.shape}")

        res = run_window_experiment(X_tr, y_tr, X_v, y_v, X_te, y_te, target_scaler, window_size=w)
        results_dict[w] = res

        records.append({
            "Window_Size": int(w),
            "Validation_Loss": float(res["val_loss"]),
            "MAE": float(res["val_mae"]),
            "RMSE": float(res["val_rmse"]),
            "R2": float(res["val_r2"]),
            "MAPE": float(res["val_mape"]),
            "Best_Epoch": int(res["best_epoch"]),
            "Train_Samples": X_tr.shape[0],
            "Val_Samples": X_v.shape[0],
            "Test_Samples": X_te.shape[0],
            "Test_MAE": float(res["test_mae"]),
            "Test_RMSE": float(res["test_rmse"]),
            "Test_R2": float(res["test_r2"]),
            "Test_MAPE": float(res["test_mape"]),
            "Val_Excluded_MAPE_Count": res["val_excl"],
            "Test_Excluded_MAPE_Count": res["test_excl"]
        })

        print(f"  -> Val Loss: {res['val_loss']:.6f}, Val R²: {res['val_r2']:.6f}, Val MAE: {res['val_mae']:.6f}")
        print(f"  -> Test MAE: {res['test_mae']:.6f}, Test RMSE: {res['test_rmse']:.6f}, Test R²: {res['test_r2']:.6f}, Test MAPE: {res['test_mape']:.4f}%")

    df_res = pd.DataFrame(records)

    # Save to reports/solar_lstm_window_experiments.csv
    csv_path = REPORTS_DIR / "solar_lstm_window_experiments.csv"
    df_res[["Window_Size", "Validation_Loss", "MAE", "RMSE", "R2", "MAPE", "Best_Epoch"]].to_csv(csv_path, index=False)
    print(f"\nSaved results to -> {csv_path}")

    # Select best window size based on lowest Validation Loss / highest Validation R2
    best_idx = df_res["Validation_Loss"].idxmin()
    best_row = df_res.loc[best_idx]
    best_w = int(best_row["Window_Size"])

    best_res = results_dict[best_w]

    # Save best model
    best_model_path = MODELS_DIR / "solar_lstm_best_window.keras"
    best_res["model"].save(best_model_path)
    print(f"Saved best window model -> {best_model_path}")

    prev_baseline_r2 = 0.866015
    improvement = best_res["test_r2"] - prev_baseline_r2

    print("\n" + "=" * 80)
    print("FINAL SUMMARY REPORT FOR SEQUENCE WINDOW EXPERIMENTS")
    print("=" * 80)
    print(df_res[["Window_Size", "Train_Samples", "Validation_Loss", "MAE", "RMSE", "R2", "MAPE", "Best_Epoch", "Test_R2"]].to_string(index=False))

    print(f"\nSelected Best Window Size (based on Validation Loss): {best_w} days")
    print(f"  Validation Loss: {best_row['Validation_Loss']:.6f}")
    print(f"  Validation R²  : {best_row['R2']:.6f}")
    print(f"  Validation MAE : {best_row['MAE']:.6f} MU")
    print(f"  Validation RMSE: {best_row['RMSE']:.6f} MU")
    print(f"  Validation MAPE: {best_row['MAPE']:.4f}%")
    print(f"\nFinal Untouched Test Set Evaluation (Window = {best_w}):")
    print(f"  Final Test MAE  : {best_res['test_mae']:.6f} MU")
    print(f"  Final Test RMSE : {best_res['test_rmse']:.6f} MU")
    print(f"  Final Test R²   : {best_res['test_r2']:.6f}")
    print(f"  Final Test MAPE : {best_res['test_mape']:.4f}%")
    print(f"  Previous Baseline Test R²: {prev_baseline_r2:.6f}")
    print(f"  Improvement in Test R²   : {improvement:+.6f}")

if __name__ == "__main__":
    main()

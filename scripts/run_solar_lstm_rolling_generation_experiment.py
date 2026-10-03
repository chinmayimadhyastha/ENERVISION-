import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
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

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data/final/full_generation_weather_dataset.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

BASE_FEATURE_COLS = [
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
NEW_FEATURE_COLS = BASE_FEATURE_COLS + ["Rolling_Generation_7"]
TARGET_COL = "DailyGeneration_MU"
SEQ_LEN = 7


def load_and_clean_solar_data(file_path: Path, include_rolling: bool = False):
    df = pd.read_csv(file_path)
    df["Date"] = pd.to_datetime(df["Date"])
    
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
    solar_df["DayOfYear_cos"] = np.cos(2 * np.pi * dayofyear / 365.25)

    # Plant-wise Lagged Generation (shift 1 strictly per plant)
    solar_df["Lagged_Generation"] = solar_df.groupby("PlantName")[TARGET_COL].shift(1)

    if include_rolling:
        # Plant-wise 7-day rolling mean of previous days (shift(1).rolling(7))
        solar_df["Rolling_Generation_7"] = (
            solar_df.groupby("PlantName")[TARGET_COL]
                    .transform(lambda g: g.shift(1).rolling(7).mean())
        )
        drop_cols = ["Lagged_Generation", "Rolling_Generation_7"]
    else:
        drop_cols = ["Lagged_Generation"]

    # Drop NaN rows resulting from lags/rolling
    solar_df = solar_df.dropna(subset=drop_cols).reset_index(drop=True)
    return solar_df


def split_time_based_per_plant(solar_df: pd.DataFrame, val_ratio: float = 0.20):
    plant_split_info = []
    train_rows = []

    for plant, group in solar_df.groupby("PlantName"):
        group = group.sort_values("Date").reset_index(drop=True)
        pre_2026 = group[group["Date"] <= "2025-12-31"]
        post_2025 = group[group["Date"] >= "2026-01-01"]

        if len(pre_2026) < SEQ_LEN + 1:
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


def fit_scalers(train_df: pd.DataFrame, feature_cols: list):
    feature_scaler = StandardScaler()
    target_scaler = StandardScaler()

    feature_scaler.fit(train_df[feature_cols])
    target_scaler.fit(train_df[[TARGET_COL]])

    return feature_scaler, target_scaler


def create_sequences(plant_split_info, feature_scaler, target_scaler, feature_cols: list, seq_len: int = SEQ_LEN):
    X_tr, y_tr = [], []
    X_v, y_v = [], []
    X_te, y_te = [], []

    for group, val_start_idx, test_start_idx in plant_split_info:
        X_scaled = feature_scaler.transform(group[feature_cols])
        y_scaled = target_scaler.transform(group[[TARGET_COL]]).flatten()

        for t in range(seq_len, len(group)):
            seq = X_scaled[t - seq_len : t]
            target = y_scaled[t]

            if t < val_start_idx:
                X_tr.append(seq)
                y_tr.append(target)
            elif t < test_start_idx:
                X_v.append(seq)
                y_v.append(target)
            else:
                X_te.append(seq)
                y_te.append(target)

    return (np.array(X_tr), np.array(y_tr)), (np.array(X_v), np.array(y_v)), (np.array(X_te), np.array(y_te))


def build_solar_lstm(input_shape):
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

    mask = np.abs(y_true) > epsilon
    excluded_count = int(np.sum(~mask))
    if np.sum(mask) > 0:
        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0
    else:
        mape = np.nan

    return mae, rmse, r2, mape, excluded_count, y_true, y_pred


def run_single_experiment(feature_cols: list, include_rolling: bool, seed=42):
    set_seeds(seed)
    
    solar_df = load_and_clean_solar_data(DATA_PATH, include_rolling=include_rolling)
    train_df, plant_split_info = split_time_based_per_plant(solar_df, val_ratio=0.20)

    f_scaler, t_scaler = fit_scalers(train_df, feature_cols)
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = create_sequences(
        plant_split_info, f_scaler, t_scaler, feature_cols, seq_len=SEQ_LEN
    )

    input_shape = (X_train.shape[1], X_train.shape[2])
    model = build_solar_lstm(input_shape)

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

    val_mae, val_rmse, val_r2, val_mape, val_excl, _, _ = calculate_metrics(model, X_val, y_val, t_scaler)
    test_mae, test_rmse, test_r2, test_mape, test_excl, y_true_test, y_pred_test = calculate_metrics(model, X_test, y_test, t_scaler)

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
        "train_samples": X_train.shape[0],
        "val_samples": X_val.shape[0],
        "test_samples": X_test.shape[0],
        "feature_count": len(feature_cols)
    }


def main():
    print("=" * 80)
    print("EXPERIMENT: ADDING 7-DAY ROLLING GENERATION FEATURE (Rolling_Generation_7)")
    print("=" * 80)

    # 1. Baseline Model (11 Features)
    print("\n1. Running BASELINE Model (11 Features)...")
    base_res = run_single_experiment(BASE_FEATURE_COLS, include_rolling=False)
    print(f"  Baseline Train samples: {base_res['train_samples']}, Val: {base_res['val_samples']}, Test: {base_res['test_samples']}")
    print(f"  Baseline Val Loss : {base_res['val_loss']:.6f}")
    print(f"  Baseline Val MAE  : {base_res['val_mae']:.6f} MU, RMSE: {base_res['val_rmse']:.6f} MU, R²: {base_res['val_r2']:.6f}, MAPE: {base_res['val_mape']:.4f}%")
    print(f"  Baseline Test MAE : {base_res['test_mae']:.6f} MU, RMSE: {base_res['test_rmse']:.6f} MU, R²: {base_res['test_r2']:.6f}, MAPE: {base_res['test_mape']:.4f}%")

    # 2. Experiment Model (12 Features including Rolling_Generation_7)
    print("\n2. Running EXPERIMENT Model (12 Features: Base + Rolling_Generation_7)...")
    exp_res = run_single_experiment(NEW_FEATURE_COLS, include_rolling=True)
    print(f"  Experiment Train samples: {exp_res['train_samples']}, Val: {exp_res['val_samples']}, Test: {exp_res['test_samples']}")
    print(f"  Experiment Val Loss : {exp_res['val_loss']:.6f}")
    print(f"  Experiment Val MAE  : {exp_res['val_mae']:.6f} MU, RMSE: {exp_res['val_rmse']:.6f} MU, R²: {exp_res['val_r2']:.6f}, MAPE: {exp_res['val_mape']:.4f}%")
    print(f"  Experiment Test MAE : {exp_res['test_mae']:.6f} MU, RMSE: {exp_res['test_rmse']:.6f} MU, R²: {exp_res['test_r2']:.6f}, MAPE: {exp_res['test_mape']:.4f}%")

    # Compare validation performance
    val_loss_diff = exp_res['val_loss'] - base_res['val_loss']
    val_r2_diff = exp_res['val_r2'] - base_res['val_r2']
    test_r2_diff = exp_res['test_r2'] - base_res['test_r2']

    is_improved = (exp_res['val_loss'] < base_res['val_loss']) or (exp_res['val_r2'] > base_res['val_r2'])
    decision = "KEEP (Improved Validation Performance)" if is_improved else "REVERT (No Validation Improvement)"

    # Save results to CSV
    csv_rows = [
        {
            "Model": "Solar LSTM",
            "Feature_Set": "Baseline (11 features)",
            "Validation_Loss": base_res["val_loss"],
            "Validation_MAE": base_res["val_mae"],
            "Validation_RMSE": base_res["val_rmse"],
            "Validation_R2": base_res["val_r2"],
            "Validation_MAPE": base_res["val_mape"],
            "Test_MAE": base_res["test_mae"],
            "Test_RMSE": base_res["test_rmse"],
            "Test_R2": base_res["test_r2"],
            "Test_MAPE": base_res["test_mape"],
            "Best_Epoch": base_res["best_epoch"]
        },
        {
            "Model": "Solar LSTM",
            "Feature_Set": "With Rolling_Generation_7 (12 features)",
            "Validation_Loss": exp_res["val_loss"],
            "Validation_MAE": exp_res["val_mae"],
            "Validation_RMSE": exp_res["val_rmse"],
            "Validation_R2": exp_res["val_r2"],
            "Validation_MAPE": exp_res["val_mape"],
            "Test_MAE": exp_res["test_mae"],
            "Test_RMSE": exp_res["test_rmse"],
            "Test_R2": exp_res["test_r2"],
            "Test_MAPE": exp_res["test_mape"],
            "Best_Epoch": exp_res["best_epoch"]
        }
    ]

    csv_df = pd.DataFrame(csv_rows)
    csv_path = REPORTS_DIR / "solar_lstm_rolling_generation_experiment.csv"
    csv_df.to_csv(csv_path, index=False)
    print(f"\nSaved experiment CSV -> {csv_path}")

    # Save model if improved
    if is_improved:
        model_save_path = MODELS_DIR / "solar_lstm_rolling_7.keras"
        exp_res["model"].save(model_save_path)
        print(f"Saved improved model -> {model_save_path}")

    print("\n" + "=" * 80)
    print("COMPARISON & DECISION SUMMARY")
    print("=" * 80)
    print(f"Baseline Validation R² : {base_res['val_r2']:.6f}")
    print(f"New Validation R²      : {exp_res['val_r2']:.6f}")
    print(f"Validation R² Change   : {val_r2_diff:+.6f}")
    print(f"Baseline Test R²       : {base_res['test_r2']:.6f}")
    print(f"New Test R²            : {exp_res['test_r2']:.6f}")
    print(f"Test R² Change         : {test_r2_diff:+.6f}")
    print(f"Decision               : {decision}")

if __name__ == "__main__":
    main()

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
SEQ_LEN = 7


def load_and_clean_solar_data(file_path: Path):
    df = pd.read_csv(file_path)
    df["Date"] = pd.to_datetime(df["Date"])
    
    # Filter solar only
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

    # Plant-wise Lagged Generation (shift 1)
    solar_df["Lagged_Generation"] = solar_df.groupby("PlantName")[TARGET_COL].shift(1)

    # Drop missing lag rows
    solar_df = solar_df.dropna(subset=["Lagged_Generation"]).reset_index(drop=True)
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


def fit_scalers(train_df: pd.DataFrame):
    feature_scaler = StandardScaler()
    target_scaler = StandardScaler()

    feature_scaler.fit(train_df[FEATURE_COLS])
    target_scaler.fit(train_df[[TARGET_COL]])

    return feature_scaler, target_scaler


def create_sequences(plant_split_info, feature_scaler, target_scaler, seq_len: int = SEQ_LEN):
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


def get_optimizer(optimizer_name: str, learning_rate: float):
    opt_name = optimizer_name.lower()
    if opt_name == "adam":
        return tf.keras.optimizers.Adam(learning_rate=learning_rate)
    elif opt_name == "rmsprop":
        return tf.keras.optimizers.RMSprop(learning_rate=learning_rate)
    elif opt_name == "nadam":
        return tf.keras.optimizers.Nadam(learning_rate=learning_rate)
    else:
        raise ValueError(f"Unsupported optimizer: {optimizer_name}")


def build_lstm(input_shape, lstm1_units=64, lstm2_units=32, dropout1=0.2, dropout2=0.2, dense_units=16):
    model = Sequential([
        Input(shape=input_shape),
        LSTM(lstm1_units, return_sequences=True),
        Dropout(dropout1),
        LSTM(lstm2_units),
        Dropout(dropout2),
        Dense(dense_units, activation="relu"),
        Dense(1)
    ])
    return model


def calculate_metrics(model, X, y, target_scaler, epsilon=1e-4):
    preds_scaled = model.predict(X, verbose=0).flatten()
    y_scaled = y.flatten()

    y_pred = target_scaler.inverse_transform(preds_scaled.reshape(-1, 1)).flatten()
    y_true = target_scaler.inverse_transform(y_scaled.reshape(-1, 1)).flatten()

    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)

    # Safe MAPE on original MU scale
    mask = np.abs(y_true) > epsilon
    if np.sum(mask) > 0:
        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0
    else:
        mape = np.nan

    return mae, rmse, r2, mape, y_true, y_pred


def run_experiment_run(X_train, y_train, X_val, y_val, X_test, y_test, target_scaler,
                       learning_rate=0.001, optimizer_name="Adam",
                       lstm1_units=64, lstm2_units=32, dropout1=0.2, dropout2=0.2,
                       seed=42):
    set_seeds(seed)
    
    input_shape = (X_train.shape[1], X_train.shape[2])
    model = build_lstm(input_shape, lstm1_units=lstm1_units, lstm2_units=lstm2_units,
                       dropout1=dropout1, dropout2=dropout2)

    optimizer = get_optimizer(optimizer_name, learning_rate)
    model.compile(optimizer=optimizer, loss="mse")

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

    # Validation metrics
    val_mae, val_rmse, val_r2, val_mape, _, _ = calculate_metrics(model, X_val, y_val, target_scaler)

    # Test metrics
    test_mae, test_rmse, test_r2, test_mape, y_true_test, y_pred_test = calculate_metrics(model, X_test, y_test, target_scaler)

    return {
        "model": model,
        "history": history,
        "best_epoch": best_epoch,
        "val_loss": val_loss,
        "val_mae": val_mae,
        "val_rmse": val_rmse,
        "val_r2": val_r2,
        "val_mape": val_mape,
        "test_mae": test_mae,
        "test_rmse": test_rmse,
        "test_r2": test_r2,
        "test_mape": test_mape,
        "y_true_test": y_true_test,
        "y_pred_test": y_pred_test
    }


def main():
    print("=" * 80)
    print("STARTING SOLAR LSTM HYPERPARAMETER TUNING EXPERIMENTS")
    print("=" * 80)

    # Step 1: Load and clean data
    solar_df = load_and_clean_solar_data(DATA_PATH)
    train_df, plant_split_info = split_time_based_per_plant(solar_df, val_ratio=0.20)

    # Fit scalers strictly on train_df
    feature_scaler, target_scaler = fit_scalers(train_df)

    # Save scalers
    joblib.dump(feature_scaler, MODELS_DIR / "solar_scaler_features.joblib")
    joblib.dump(target_scaler, MODELS_DIR / "solar_scaler_target.joblib")

    # Create plant-wise sequences
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = create_sequences(
        plant_split_info, feature_scaler, target_scaler, seq_len=SEQ_LEN
    )

    print(f"Dataset split completed:")
    print(f"  Train: X = {X_train.shape}, y = {y_train.shape}")
    print(f"  Val  : X = {X_val.shape}, y = {y_val.shape}")
    print(f"  Test : X = {X_test.shape}, y = {y_test.shape}")

    # =========================================================================
    # EXPERIMENT 0: Baseline Model Evaluation
    # =========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENT 0: BASELINE MODEL")
    print("=" * 80)
    baseline_res = run_experiment_run(
        X_train, y_train, X_val, y_val, X_test, y_test, target_scaler,
        learning_rate=0.001, optimizer_name="Adam",
        lstm1_units=64, lstm2_units=32, dropout1=0.2, dropout2=0.2
    )
    print(f"Baseline Validation Loss: {baseline_res['val_loss']:.6f}, Val R²: {baseline_res['val_r2']:.6f}")
    print(f"Baseline Test MAE: {baseline_res['test_mae']:.6f}, RMSE: {baseline_res['test_rmse']:.6f}, R²: {baseline_res['test_r2']:.6f}, MAPE: {baseline_res['test_mape']:.4f}%")

    # =========================================================================
    # EXPERIMENT 1: LEARNING RATE ONLY
    # =========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENT 1: LEARNING RATE ONLY")
    print("=" * 80)
    learning_rates = [0.0001, 0.0003, 0.0005, 0.001, 0.002, 0.003]
    exp1_records = []
    exp1_results_dict = {}

    for lr in learning_rates:
        print(f"Testing Learning Rate = {lr} (Optimizer = Adam)...")
        res = run_experiment_run(
            X_train, y_train, X_val, y_val, X_test, y_test, target_scaler,
            learning_rate=lr, optimizer_name="Adam",
            lstm1_units=64, lstm2_units=32, dropout1=0.2, dropout2=0.2
        )
        exp1_results_dict[lr] = res
        exp1_records.append({
            "Learning Rate": lr,
            "Optimizer": "Adam",
            "MAE": res["val_mae"],
            "RMSE": res["val_rmse"],
            "R2": res["val_r2"],
            "MAPE": res["val_mape"],
            "Best Epoch": res["best_epoch"],
            "Validation Loss": res["val_loss"],
            "Test_MAE": res["test_mae"],
            "Test_RMSE": res["test_rmse"],
            "Test_R2": res["test_r2"],
            "Test_MAPE": res["test_mape"]
        })
        print(f"  -> Val Loss: {res['val_loss']:.6f}, Val R²: {res['val_r2']:.6f}, Test R²: {res['test_r2']:.6f}")

    exp1_df = pd.DataFrame(exp1_records)
    # Save CSV strictly with specified format
    exp1_csv = REPORTS_DIR / "solar_lstm_learning_rate_experiments.csv"
    exp1_df[["Learning Rate", "Optimizer", "MAE", "RMSE", "R2", "MAPE", "Best Epoch", "Validation Loss"]].to_csv(exp1_csv, index=False)
    print(f"\nSaved Experiment 1 results -> {exp1_csv}")

    # Pick best learning rate based strictly on VALIDATION Loss
    best_lr_idx = exp1_df["Validation Loss"].idxmin()
    best_lr = float(exp1_df.loc[best_lr_idx, "Learning Rate"])
    print(f"\nBest Learning Rate selected based on Validation Performance: {best_lr} (Val Loss: {exp1_df.loc[best_lr_idx, 'Validation Loss']:.6f}, Val R²: {exp1_df.loc[best_lr_idx, 'R2']:.6f})")

    # =========================================================================
    # EXPERIMENT 2: OPTIMIZER ONLY
    # =========================================================================
    print("\n" + "=" * 80)
    print(f"EXPERIMENT 2: OPTIMIZER ONLY (Fixed LR = {best_lr})")
    print("=" * 80)
    optimizers = ["Adam", "RMSprop", "Nadam"]
    exp2_records = []
    exp2_results_dict = {}

    for opt in optimizers:
        print(f"Testing Optimizer = {opt} (Learning Rate = {best_lr})...")
        res = run_experiment_run(
            X_train, y_train, X_val, y_val, X_test, y_test, target_scaler,
            learning_rate=best_lr, optimizer_name=opt,
            lstm1_units=64, lstm2_units=32, dropout1=0.2, dropout2=0.2
        )
        exp2_results_dict[opt] = res
        exp2_records.append({
            "Optimizer": opt,
            "Learning Rate": best_lr,
            "MAE": res["val_mae"],
            "RMSE": res["val_rmse"],
            "R2": res["val_r2"],
            "MAPE": res["val_mape"],
            "Best Epoch": res["best_epoch"],
            "Validation Loss": res["val_loss"],
            "Test_MAE": res["test_mae"],
            "Test_RMSE": res["test_rmse"],
            "Test_R2": res["test_r2"],
            "Test_MAPE": res["test_mape"]
        })
        print(f"  -> Val Loss: {res['val_loss']:.6f}, Val R²: {res['val_r2']:.6f}, Test R²: {res['test_r2']:.6f}")

    exp2_df = pd.DataFrame(exp2_records)
    exp2_csv = REPORTS_DIR / "solar_lstm_optimizer_experiments.csv"
    exp2_df[["Optimizer", "Learning Rate", "MAE", "RMSE", "R2", "MAPE", "Best Epoch", "Validation Loss"]].to_csv(exp2_csv, index=False)
    print(f"\nSaved Experiment 2 results -> {exp2_csv}")

    best_opt_idx = exp2_df["Validation Loss"].idxmin()
    best_optimizer = str(exp2_df.loc[best_opt_idx, "Optimizer"])
    print(f"\nBest Optimizer selected based on Validation Performance: {best_optimizer} (Val Loss: {exp2_df.loc[best_opt_idx, 'Validation Loss']:.6f}, Val R²: {exp2_df.loc[best_opt_idx, 'R2']:.6f})")

    # =========================================================================
    # EXPERIMENT 3: ARCHITECTURE ONE PARAMETER AT A TIME
    # =========================================================================
    print("\n" + "=" * 80)
    print(f"EXPERIMENT 3: ARCHITECTURE ONE PARAMETER AT A TIME (Fixed LR={best_lr}, Optimizer={best_optimizer})")
    print("=" * 80)

    arch_configs = [
        {
            "Experiment": "Baseline Architecture",
            "Parameter Changed": "None (Baseline)",
            "Value": "LSTM(64)->Drop(0.2)->LSTM(32)->Drop(0.2)->Dense(16)",
            "lstm1": 64, "lstm2": 32, "d1": 0.2, "d2": 0.2
        },
        {
            "Experiment": "Experiment A",
            "Parameter Changed": "1st LSTM Units",
            "Value": "128 (vs baseline 64)",
            "lstm1": 128, "lstm2": 32, "d1": 0.2, "d2": 0.2
        },
        {
            "Experiment": "Experiment B",
            "Parameter Changed": "2nd LSTM Units",
            "Value": "64 (vs baseline 32)",
            "lstm1": 64, "lstm2": 64, "d1": 0.2, "d2": 0.2
        },
        {
            "Experiment": "Experiment C",
            "Parameter Changed": "Dropout Rate",
            "Value": "0.1 (vs baseline 0.2)",
            "lstm1": 64, "lstm2": 32, "d1": 0.1, "d2": 0.1
        },
        {
            "Experiment": "Experiment D",
            "Parameter Changed": "Dropout Rate",
            "Value": "0.3 (vs baseline 0.2)",
            "lstm1": 64, "lstm2": 32, "d1": 0.3, "d2": 0.3
        }
    ]

    exp3_records = []
    exp3_results_dict = {}

    for cfg in arch_configs:
        print(f"Testing {cfg['Experiment']}: {cfg['Parameter Changed']} = {cfg['Value']}...")
        res = run_experiment_run(
            X_train, y_train, X_val, y_val, X_test, y_test, target_scaler,
            learning_rate=best_lr, optimizer_name=best_optimizer,
            lstm1_units=cfg["lstm1"], lstm2_units=cfg["lstm2"],
            dropout1=cfg["d1"], dropout2=cfg["d2"]
        )
        exp3_results_dict[cfg["Experiment"]] = res
        exp3_records.append({
            "Experiment": cfg["Experiment"],
            "Parameter Changed": cfg["Parameter Changed"],
            "Value": cfg["Value"],
            "MAE": res["val_mae"],
            "RMSE": res["val_rmse"],
            "R2": res["val_r2"],
            "MAPE": res["val_mape"],
            "Best Epoch": res["best_epoch"],
            "Validation Loss": res["val_loss"],
            "Test_MAE": res["test_mae"],
            "Test_RMSE": res["test_rmse"],
            "Test_R2": res["test_r2"],
            "Test_MAPE": res["test_mape"],
            "lstm1": cfg["lstm1"],
            "lstm2": cfg["lstm2"],
            "d1": cfg["d1"],
            "d2": cfg["d2"]
        })
        print(f"  -> Val Loss: {res['val_loss']:.6f}, Val R²: {res['val_r2']:.6f}, Test R²: {res['test_r2']:.6f}")

    exp3_df = pd.DataFrame(exp3_records)
    exp3_csv = REPORTS_DIR / "solar_lstm_architecture_experiments.csv"
    exp3_df[["Experiment", "Parameter Changed", "Value", "MAE", "RMSE", "R2", "MAPE", "Best Epoch", "Validation Loss"]].to_csv(exp3_csv, index=False)
    print(f"\nSaved Experiment 3 results -> {exp3_csv}")

    best_arch_idx = exp3_df["Validation Loss"].idxmin()
    best_arch_row = exp3_df.loc[best_arch_idx]
    print(f"\nBest Architecture selected based on Validation Performance: {best_arch_row['Experiment']} - {best_arch_row['Parameter Changed']} = {best_arch_row['Value']}")

    # =========================================================================
    # MODEL SELECTION & FINAL HELD-OUT TEST EVALUATION
    # =========================================================================
    print("\n" + "=" * 80)
    print("FINAL MODEL SELECTION & UNTOUCHED TEST EVALUATION")
    print("=" * 80)

    # Train final best model architecture with best hyperparameters
    final_res = run_experiment_run(
        X_train, y_train, X_val, y_val, X_test, y_test, target_scaler,
        learning_rate=best_lr, optimizer_name=best_optimizer,
        lstm1_units=int(best_arch_row["lstm1"]), lstm2_units=int(best_arch_row["lstm2"]),
        dropout1=float(best_arch_row["d1"]), dropout2=float(best_arch_row["d2"])
    )

    # Save best model
    final_model_path = MODELS_DIR / "solar_lstm_best.keras"
    final_res["model"].save(final_model_path)
    print(f"Saved final best model -> {final_model_path}")

    # Calculate metrics for baseline test vs final test
    base_test_r2 = baseline_res["test_r2"]
    final_test_r2 = final_res["test_r2"]
    r2_improvement = final_test_r2 - base_test_r2

    print(f"\nFINAL UNTOUCHED TEST EVALUATION (POST-2025 TEST SET):")
    print(f"  Final Test MAE  : {final_res['test_mae']:.6f} MU")
    print(f"  Final Test RMSE : {final_res['test_rmse']:.6f} MU")
    print(f"  Final Test R²   : {final_res['test_r2']:.6f}")
    print(f"  Final Test MAPE : {final_res['test_mape']:.4f}%")
    print(f"  Baseline Test R²: {base_test_r2:.6f}")
    print(f"  R² Improvement  : {r2_improvement:+.6f}")
    print(f"  Target R² >= 0.90 Achieved? : {'YES' if final_test_r2 >= 0.90 else 'NO'}")

    # Plot actual vs predicted for final model
    plt.figure(figsize=(8, 6))
    plt.scatter(final_res["y_true_test"], final_res["y_pred_test"], alpha=0.5, color="tab:blue")
    min_val = min(final_res["y_true_test"].min(), final_res["y_pred_test"].min())
    max_val = max(final_res["y_true_test"].max(), final_res["y_pred_test"].max())
    plt.plot([min_val, max_val], [min_val, max_val], "k--", label="Ideal Prediction (y = x)", linewidth=1.5)
    plt.title("Solar LSTM (Optimized): Actual vs Predicted Generation (MU)", fontsize=14, fontweight="bold")
    plt.xlabel("Actual Generation (MU)", fontsize=12)
    plt.ylabel("Predicted Generation (MU)", fontsize=12)
    plt.legend(fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "solar_lstm_best_actual_vs_predicted.png", dpi=300)
    plt.close()

    # Save summary report dataframe
    summary_rows = []
    # Add Baseline
    summary_rows.append({
        "Experiment": "Baseline",
        "Parameter Changed": "None",
        "Value": "LR=0.001, Adam, 64/32",
        "MAE": baseline_res["val_mae"],
        "RMSE": baseline_res["val_rmse"],
        "R2": baseline_res["val_r2"],
        "MAPE": baseline_res["val_mape"],
        "Best Epoch": baseline_res["best_epoch"]
    })

    # Add Exp 1 best
    summary_rows.append({
        "Experiment": "Exp 1 Best",
        "Parameter Changed": "Learning Rate",
        "Value": str(best_lr),
        "MAE": exp1_df.loc[best_lr_idx, "MAE"],
        "RMSE": exp1_df.loc[best_lr_idx, "RMSE"],
        "R2": exp1_df.loc[best_lr_idx, "R2"],
        "MAPE": exp1_df.loc[best_lr_idx, "MAPE"],
        "Best Epoch": exp1_df.loc[best_lr_idx, "Best Epoch"]
    })

    # Add Exp 2 best
    summary_rows.append({
        "Experiment": "Exp 2 Best",
        "Parameter Changed": "Optimizer",
        "Value": best_optimizer,
        "MAE": exp2_df.loc[best_opt_idx, "MAE"],
        "RMSE": exp2_df.loc[best_opt_idx, "RMSE"],
        "R2": exp2_df.loc[best_opt_idx, "R2"],
        "MAPE": exp2_df.loc[best_opt_idx, "MAPE"],
        "Best Epoch": exp2_df.loc[best_opt_idx, "Best Epoch"]
    })

    # Add Exp 3 best
    summary_rows.append({
        "Experiment": "Exp 3 Best",
        "Parameter Changed": best_arch_row["Parameter Changed"],
        "Value": best_arch_row["Value"],
        "MAE": best_arch_row["MAE"],
        "RMSE": best_arch_row["RMSE"],
        "R2": best_arch_row["R2"],
        "MAPE": best_arch_row["MAPE"],
        "Best Epoch": best_arch_row["Best Epoch"]
    })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(REPORTS_DIR / "solar_lstm_experiments_summary.csv", index=False)
    print("\nSUMMARY COMPARISON TABLE (VALIDATION PERFORMANCE):")
    print(summary_df.to_string(index=False))

if __name__ == "__main__":
    main()

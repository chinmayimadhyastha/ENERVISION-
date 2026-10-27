from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.models import Sequential


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "final" / "full_generation_weather_dataset.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"

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
    "Lagged_Generation",
]
ROLLING_FEATURE = "Rolling_Generation_7"
ROLLING_FEATURE_COLS = [*BASE_FEATURE_COLS, ROLLING_FEATURE]
TARGET_COL = "DailyGeneration_MU"
SEQ_LEN = 7
SEED = 42


def set_seeds(seed: int = SEED) -> None:
    np.random.seed(seed)
    tf.random.set_seed(seed)


def load_and_clean_solar_data(
    file_path: Path, include_rolling: bool = False
) -> pd.DataFrame:
    df = pd.read_csv(file_path)
    required_columns = {
        "Date",
        "Type",
        "PlantName",
        TARGET_COL,
        "Capacity_MW",
        "Temperature",
        "Humidity",
        "WindSpeed",
        "GHI",
        "Pressure",
    }
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"Dataset is missing required columns: {', '.join(sorted(missing_columns))}"
        )

    df["Date"] = pd.to_datetime(df["Date"], errors="raise")
    solar_df = (
        df.loc[df["Type"] == "Solar"]
        .sort_values(["PlantName", "Date"])
        .reset_index(drop=True)
        .copy()
    )
    if solar_df.empty:
        raise ValueError("The dataset contains no Solar records.")

    weather_cols = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
    for col in weather_cols:
        solar_df[col] = solar_df[col].mask(solar_df[col] <= -900, np.nan)
        solar_df[col] = solar_df.groupby("PlantName")[col].transform(
            lambda values: values.ffill().bfill()
        )
        if solar_df[col].isna().any():
            solar_df[col] = solar_df[col].fillna(solar_df[col].mean())

    solar_df[TARGET_COL] = solar_df[TARGET_COL].clip(lower=0.0)
    month = solar_df["Date"].dt.month
    day_of_year = solar_df["Date"].dt.dayofyear
    solar_df["Month_sin"] = np.sin(2 * np.pi * month / 12)
    solar_df["Month_cos"] = np.cos(2 * np.pi * month / 12)
    solar_df["DayOfYear_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    solar_df["DayOfYear_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)

    generation_by_plant = solar_df.groupby("PlantName")[TARGET_COL]
    solar_df["Lagged_Generation"] = generation_by_plant.shift(1)
    required_lags = ["Lagged_Generation"]
    if include_rolling:
        solar_df[ROLLING_FEATURE] = generation_by_plant.transform(
            lambda values: values.shift(1).rolling(7, min_periods=7).mean()
        )
        required_lags.append(ROLLING_FEATURE)

    return solar_df.dropna(subset=required_lags).reset_index(drop=True)


def split_time_based_per_plant(
    solar_df: pd.DataFrame, val_ratio: float = 0.20
) -> tuple[pd.DataFrame, list[tuple[pd.DataFrame, int, int]]]:
    if not 0 < val_ratio < 1:
        raise ValueError("val_ratio must be between 0 and 1.")

    plant_split_info = []
    train_rows = []
    for _, plant_df in solar_df.groupby("PlantName"):
        group = plant_df.sort_values("Date").reset_index(drop=True)
        pre_2026 = group[group["Date"] < pd.Timestamp("2026-01-01")]
        if pre_2026.empty:
            continue

        train_count = int(len(pre_2026) * (1.0 - val_ratio))
        if train_count <= SEQ_LEN or train_count >= len(pre_2026):
            continue

        train_rows.append(pre_2026.iloc[:train_count])
        plant_split_info.append((group, train_count, len(pre_2026)))

    if not train_rows:
        raise ValueError(
            "No plants have enough pre-2026 records for both training and validation."
        )
    return pd.concat(train_rows, ignore_index=True), plant_split_info


def fit_scalers(
    train_df: pd.DataFrame, feature_cols: list[str]
) -> tuple[StandardScaler, StandardScaler]:
    feature_scaler = StandardScaler()
    target_scaler = StandardScaler()
    feature_scaler.fit(train_df[feature_cols])
    target_scaler.fit(train_df[[TARGET_COL]])
    return feature_scaler, target_scaler


def create_sequences(
    plant_split_info: list[tuple[pd.DataFrame, int, int]],
    feature_scaler: StandardScaler,
    target_scaler: StandardScaler,
    feature_cols: list[str],
    seq_len: int = SEQ_LEN,
) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    sequences: list[list[np.ndarray]] = [[], [], []]
    targets: list[list[float]] = [[], [], []]

    for group, val_start_idx, test_start_idx in plant_split_info:
        scaled_features = feature_scaler.transform(group[feature_cols])
        scaled_targets = target_scaler.transform(group[[TARGET_COL]]).ravel()
        for target_idx in range(seq_len, len(group)):
            if target_idx < val_start_idx:
                split_idx = 0
            elif target_idx < test_start_idx:
                split_idx = 1
            else:
                split_idx = 2
            sequences[split_idx].append(
                scaled_features[target_idx - seq_len : target_idx]
            )
            targets[split_idx].append(float(scaled_targets[target_idx]))

    result = tuple(
        (np.asarray(x, dtype=np.float32), np.asarray(y, dtype=np.float32))
        for x, y in zip(sequences, targets)
    )
    for split_name, (x_values, _) in zip(("training", "validation", "test"), result):
        if x_values.size == 0:
            raise ValueError(
                f"The {split_name} split contains no sequences; check the data dates "
                "and per-plant record counts."
            )
    return result


def build_solar_lstm(input_shape: tuple[int, int]) -> Sequential:
    model = Sequential(
        [
            Input(shape=input_shape),
            LSTM(64, return_sequences=True),
            Dropout(0.3),
            LSTM(32),
            Dropout(0.3),
            Dense(16, activation="relu"),
            Dense(1),
        ]
    )
    model.compile(
        optimizer=tf.keras.optimizers.Nadam(learning_rate=0.0001), loss="mse"
    )
    return model


def calculate_metrics(
    model: Sequential,
    x_values: np.ndarray,
    y_values: np.ndarray,
    target_scaler: StandardScaler,
    epsilon: float = 1e-4,
) -> tuple[float, float, float, float, int, np.ndarray, np.ndarray]:
    predictions_scaled = model.predict(x_values, verbose=0).reshape(-1, 1)
    actual_scaled = y_values.reshape(-1, 1)
    predictions = target_scaler.inverse_transform(predictions_scaled).ravel()
    actual = target_scaler.inverse_transform(actual_scaled).ravel()

    mae = float(mean_absolute_error(actual, predictions))
    rmse = float(np.sqrt(mean_squared_error(actual, predictions)))
    r2 = float(r2_score(actual, predictions))
    nonzero_mask = np.abs(actual) > epsilon
    excluded_count = int(np.count_nonzero(~nonzero_mask))
    mape = (
        float(
            np.mean(
                np.abs(
                    (actual[nonzero_mask] - predictions[nonzero_mask])
                    / actual[nonzero_mask]
                )
            )
            * 100.0
        )
        if np.any(nonzero_mask)
        else float("nan")
    )
    return mae, rmse, r2, mape, excluded_count, actual, predictions


def run_single_experiment(
    feature_cols: list[str], include_rolling: bool, seed: int = SEED
) -> dict[str, object]:
    set_seeds(seed)
    solar_df = load_and_clean_solar_data(DATA_PATH, include_rolling=include_rolling)
    train_df, plant_split_info = split_time_based_per_plant(solar_df)
    feature_scaler, target_scaler = fit_scalers(train_df, feature_cols)
    (x_train, y_train), (x_val, y_val), (x_test, y_test) = create_sequences(
        plant_split_info, feature_scaler, target_scaler, feature_cols
    )

    model = build_solar_lstm((x_train.shape[1], x_train.shape[2]))
    callbacks = [
        EarlyStopping(monitor="val_loss", patience=15, restore_best_weights=True),
        ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6
        ),
    ]
    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=60,
        batch_size=32,
        shuffle=False,
        callbacks=callbacks,
        verbose=0,
    )

    val_metrics = calculate_metrics(model, x_val, y_val, target_scaler)
    test_metrics = calculate_metrics(model, x_test, y_test, target_scaler)
    return {
        "model": model,
        "best_epoch": int(np.argmin(history.history["val_loss"]) + 1),
        "val_loss": float(np.min(history.history["val_loss"])),
        "val_mae": val_metrics[0],
        "val_rmse": val_metrics[1],
        "val_r2": val_metrics[2],
        "val_mape": val_metrics[3],
        "val_excluded": val_metrics[4],
        "test_mae": test_metrics[0],
        "test_rmse": test_metrics[1],
        "test_r2": test_metrics[2],
        "test_mape": test_metrics[3],
        "test_excluded": test_metrics[4],
        "train_samples": len(x_train),
        "val_samples": len(x_val),
        "test_samples": len(x_test),
    }


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    print("=" * 80)
    print("EXPERIMENT: ADDING 7-DAY ROLLING GENERATION FEATURE")
    print("=" * 80)

    experiments = [
        ("Baseline (11 features)", BASE_FEATURE_COLS, False),
        (
            "With Rolling_Generation_7 (12 features)",
            ROLLING_FEATURE_COLS,
            True,
        ),
    ]
    results = []
    for label, feature_cols, include_rolling in experiments:
        print(f"\nRunning {label}...")
        result = run_single_experiment(feature_cols, include_rolling)
        result["feature_set"] = label
        results.append(result)
        print(
            f"  Samples - train: {result['train_samples']}, "
            f"validation: {result['val_samples']}, test: {result['test_samples']}"
        )
        print(
            f"  Validation loss: {result['val_loss']:.6f}; "
            f"MAE: {result['val_mae']:.6f}; RMSE: {result['val_rmse']:.6f}; "
            f"R2: {result['val_r2']:.6f}"
        )
        print(
            f"  Test MAE: {result['test_mae']:.6f}; "
            f"RMSE: {result['test_rmse']:.6f}; R2: {result['test_r2']:.6f}"
        )

    baseline, rolling = results
    improved = rolling["val_loss"] < baseline["val_loss"]
    if improved:
        model_path = MODELS_DIR / "solar_lstm_rolling_7.keras"
        rolling["model"].save(model_path)
        print(f"\nSaved improved model to {model_path}")

    csv_rows = [
        {
            "Model": "Solar LSTM",
            "Feature_Set": result["feature_set"],
            "Validation_Loss": result["val_loss"],
            "Validation_MAE": result["val_mae"],
            "Validation_RMSE": result["val_rmse"],
            "Validation_R2": result["val_r2"],
            "Validation_MAPE": result["val_mape"],
            "Test_MAE": result["test_mae"],
            "Test_RMSE": result["test_rmse"],
            "Test_R2": result["test_r2"],
            "Test_MAPE": result["test_mape"],
            "Best_Epoch": result["best_epoch"],
        }
        for result in results
    ]
    report_path = REPORTS_DIR / "solar_lstm_rolling_generation_experiment.csv"
    pd.DataFrame(csv_rows).to_csv(report_path, index=False)

    print(f"\nSaved experiment report to {report_path}")
    print(f"Validation loss improved: {'YES' if improved else 'NO'}")


if __name__ == "__main__":
    main()

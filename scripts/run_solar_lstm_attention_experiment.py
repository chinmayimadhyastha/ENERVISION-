from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import (
    Attention,
    Dense,
    Dropout,
    GlobalAveragePooling1D,
    Input,
    LSTM,
)
from tensorflow.keras.models import Model


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "final" / "full_generation_weather_dataset.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
TARGET_COL = "DailyGeneration_MU"
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
    "Rolling_Generation_7",
]
WEATHER_COLS = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
SEQ_LEN = 7
SEED = 42
VALIDATION_FRACTION = 0.20
TRAINING_CUTOFF = pd.Timestamp("2026-01-01")
OPTIMIZER = "Nadam"
LEARNING_RATE = 0.0001
BATCH_SIZE = 32
MAX_EPOCHS = 60
EARLY_STOPPING_PATIENCE = 15
REDUCE_LR_FACTOR = 0.5
REDUCE_LR_PATIENCE = 5
MIN_LEARNING_RATE = 1e-6
DROPOUT_RATE = 0.3
DENSE_UNITS = 16

MODEL_PATH = MODELS_DIR / "solar_lstm_attention.keras"
FEATURE_SCALER_PATH = MODELS_DIR / "solar_lstm_attention_feature_scaler.joblib"
TARGET_SCALER_PATH = MODELS_DIR / "solar_lstm_attention_target_scaler.joblib"
CONFIG_PATH = MODELS_DIR / "solar_lstm_attention_config.json"
REPORT_PATH = REPORTS_DIR / "solar_lstm_attention_experiment.csv"

CURRENT_BASELINE = {
    "Validation_MAE": 0.14669904112815857,
    "Validation_RMSE": 0.24318671982698142,
    "Validation_R2": 0.8526325225830078,
    "Test_MAE": 0.14029693603515625,
    "Test_RMSE": 0.23404275073627287,
    "Test_R2": 0.8674271106719971,
}
HISTORICAL_BENCHMARK = {
    "Validation_R2": 0.854995,
    "Test_R2": 0.866096,
}


def set_seeds(seed: int = SEED) -> None:
    np.random.seed(seed)
    tf.random.set_seed(seed)


def load_and_clean_solar_data(file_path: Path) -> pd.DataFrame:
    df = pd.read_csv(file_path)
    required_columns = {
        "Date",
        "Type",
        "PlantName",
        TARGET_COL,
        "Capacity_MW",
        *WEATHER_COLS,
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

    for col in WEATHER_COLS:
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
    solar_df["Rolling_Generation_7"] = generation_by_plant.transform(
        lambda values: values.shift(1).rolling(7, min_periods=7).mean()
    )
    return solar_df.dropna(
        subset=["Lagged_Generation", "Rolling_Generation_7"]
    ).reset_index(drop=True)


def split_time_based_per_plant(
    solar_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[tuple[str, pd.DataFrame, int, int]], list[dict[str, str | None]]]:
    train_rows = []
    plant_split_info = []
    split_dates = []

    for plant, plant_df in solar_df.groupby("PlantName"):
        group = plant_df.sort_values("Date").reset_index(drop=True)
        pre_test = group[group["Date"] < TRAINING_CUTOFF]
        if pre_test.empty:
            continue

        train_count = int(len(pre_test) * (1.0 - VALIDATION_FRACTION))
        if train_count <= SEQ_LEN or train_count >= len(pre_test):
            continue

        test_start_idx = len(pre_test)
        train_rows.append(pre_test.iloc[:train_count])
        plant_split_info.append((str(plant), group, train_count, test_start_idx))
        split_dates.append(
            {
                "plant": str(plant),
                "train_start": group.iloc[0]["Date"].date().isoformat(),
                "train_end": group.iloc[train_count - 1]["Date"].date().isoformat(),
                "validation_start": group.iloc[train_count]["Date"].date().isoformat(),
                "validation_end": group.iloc[test_start_idx - 1]["Date"].date().isoformat(),
                "test_start": (
                    group.iloc[test_start_idx]["Date"].date().isoformat()
                    if test_start_idx < len(group)
                    else None
                ),
                "test_end": (
                    group.iloc[-1]["Date"].date().isoformat()
                    if test_start_idx < len(group)
                    else None
                ),
            }
        )

    if not train_rows:
        raise ValueError(
            "No plants have enough pre-2026 records for both training and validation."
        )
    return pd.concat(train_rows, ignore_index=True), plant_split_info, split_dates


def fit_scalers(
    train_df: pd.DataFrame,
) -> tuple[StandardScaler, StandardScaler]:
    feature_scaler = StandardScaler()
    target_scaler = StandardScaler()
    feature_scaler.fit(train_df[FEATURE_COLS])
    target_scaler.fit(train_df[[TARGET_COL]])
    return feature_scaler, target_scaler


def create_sequences(
    plant_split_info: list[tuple[str, pd.DataFrame, int, int]],
    feature_scaler: StandardScaler,
    target_scaler: StandardScaler,
) -> tuple[
    tuple[tuple[np.ndarray, np.ndarray], ...],
    list[list[pd.Timestamp]],
]:
    sequences: list[list[np.ndarray]] = [[], [], []]
    targets: list[list[float]] = [[], [], []]
    target_dates: list[list[pd.Timestamp]] = [[], [], []]

    for _, group, val_start_idx, test_start_idx in plant_split_info:
        scaled_features = feature_scaler.transform(group[FEATURE_COLS])
        scaled_targets = target_scaler.transform(group[[TARGET_COL]]).ravel()
        for target_idx in range(SEQ_LEN, len(group)):
            if target_idx < val_start_idx:
                split_idx = 0
            elif target_idx < test_start_idx:
                split_idx = 1
            else:
                split_idx = 2
            sequences[split_idx].append(
                scaled_features[target_idx - SEQ_LEN : target_idx]
            )
            targets[split_idx].append(float(scaled_targets[target_idx]))
            target_dates[split_idx].append(group["Date"].iloc[target_idx])

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
    return result, target_dates


def build_solar_lstm_attention(input_shape: tuple[int, int]) -> Model:
    inputs = Input(shape=input_shape, name="historical_solar_features")
    lstm_sequence = LSTM(64, return_sequences=True, name="lstm_64")(inputs)
    attended_sequence = Attention(name="temporal_self_attention")(
        [lstm_sequence, lstm_sequence]
    )
    context = GlobalAveragePooling1D(name="attention_context_pooling")(
        attended_sequence
    )
    x = Dropout(DROPOUT_RATE, name="dropout")(context)
    x = Dense(DENSE_UNITS, activation="relu", name="dense_16_relu")(x)
    outputs = Dense(1, name="generation_prediction")(x)

    model = Model(inputs=inputs, outputs=outputs, name="solar_lstm_self_attention")
    model.compile(
        optimizer=tf.keras.optimizers.Nadam(learning_rate=LEARNING_RATE), loss="mse"
    )
    return model


def calculate_metrics(
    model: Model,
    x_values: np.ndarray,
    y_values: np.ndarray,
    target_scaler: StandardScaler,
) -> dict[str, float]:
    predictions_scaled = model.predict(x_values, verbose=0).reshape(-1, 1)
    actual_scaled = y_values.reshape(-1, 1)
    predictions = target_scaler.inverse_transform(predictions_scaled).ravel()
    actual = target_scaler.inverse_transform(actual_scaled).ravel()
    return {
        "MAE": float(mean_absolute_error(actual, predictions)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predictions))),
        "R2": float(r2_score(actual, predictions)),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def protected_artifact_hashes() -> dict[str, str]:
    protected_paths = [MODELS_DIR / "solar_lstm_rolling_7.keras"]
    protected_paths.extend(
        path
        for directory in (MODELS_DIR, REPORTS_DIR)
        for path in directory.iterdir()
        if path.is_file() and path.name.lower().startswith("wind")
    )
    return {
        str(path.relative_to(BASE_DIR)): sha256(path)
        for path in sorted(set(protected_paths))
        if path.is_file()
    }


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")
    output_paths = [
        MODEL_PATH,
        FEATURE_SCALER_PATH,
        TARGET_SCALER_PATH,
        CONFIG_PATH,
        REPORT_PATH,
    ]
    collisions = [str(path) for path in output_paths if path.exists()]
    if collisions:
        raise FileExistsError(
            "Refusing to overwrite existing experiment artifacts: "
            + ", ".join(collisions)
        )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    hashes_before = protected_artifact_hashes()
    set_seeds(SEED)

    solar_df = load_and_clean_solar_data(DATA_PATH)
    train_df, plant_split_info, split_dates = split_time_based_per_plant(solar_df)
    feature_scaler, target_scaler = fit_scalers(train_df)
    sequence_splits, target_dates = create_sequences(
        plant_split_info, feature_scaler, target_scaler
    )
    (x_train, y_train), (x_val, y_val), (x_test, y_test) = sequence_splits

    model = build_solar_lstm_attention((x_train.shape[1], x_train.shape[2]))
    callbacks = [
        EarlyStopping(
            monitor="val_loss",
            patience=EARLY_STOPPING_PATIENCE,
            restore_best_weights=True,
        ),
        ReduceLROnPlateau(
            monitor="val_loss",
            factor=REDUCE_LR_FACTOR,
            patience=REDUCE_LR_PATIENCE,
            min_lr=MIN_LEARNING_RATE,
        ),
    ]
    print("Temporal self-attention shape: (batch, 7 query steps, 7 key steps)")
    model.summary()

    started_at = time.perf_counter()
    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=MAX_EPOCHS,
        batch_size=BATCH_SIZE,
        shuffle=False,
        callbacks=callbacks,
        verbose=2,
    )
    training_duration_seconds = time.perf_counter() - started_at

    best_epoch = int(np.argmin(history.history["val_loss"]) + 1)
    val_metrics = calculate_metrics(model, x_val, y_val, target_scaler)
    selected_model = (
        "Solar LSTM + Self-Attention"
        if val_metrics["R2"] > CURRENT_BASELINE["Validation_R2"]
        else "Current Solar LSTM"
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    joblib.dump(feature_scaler, FEATURE_SCALER_PATH)
    joblib.dump(target_scaler, TARGET_SCALER_PATH)

    # Test data is evaluated only after validation-based model selection.
    test_metrics = calculate_metrics(model, x_test, y_test, target_scaler)
    date_ranges = {
        split_name: {
            "start": min(dates).date().isoformat(),
            "end": max(dates).date().isoformat(),
        }
        for split_name, dates in zip(("train", "validation", "test"), target_dates)
    }
    split_metadata = {
        "cutoff_exclusive": TRAINING_CUTOFF.date().isoformat(),
        "validation_fraction_per_plant": VALIDATION_FRACTION,
        "target_date_ranges": date_ranges,
        "per_plant_boundaries": split_dates,
        "sample_counts": {
            "train": len(x_train),
            "validation": len(x_val),
            "test": len(x_test),
        },
    }

    metric_differences = {
        f"{split}_{metric}_difference_vs_current": round(
            attention_value - CURRENT_BASELINE[f"{split}_{metric}"], 9
        )
        for split, metrics in (("Validation", val_metrics), ("Test", test_metrics))
        for metric, attention_value in metrics.items()
    }
    architecture = (
        "Input(7,12) -> LSTM(64, return_sequences=True) -> "
        "temporal self-attention(query=value=LSTM sequence; per-sample 7x7 scores) "
        "-> GlobalAveragePooling1D(context) -> Dropout(0.3) -> "
        "Dense(16, relu) -> Dense(1)"
    )
    artifact_paths = {
        "model": str(MODEL_PATH.resolve()),
        "feature_scaler": str(FEATURE_SCALER_PATH.resolve()),
        "target_scaler": str(TARGET_SCALER_PATH.resolve()),
        "configuration": str(CONFIG_PATH.resolve()),
        "report": str(REPORT_PATH.resolve()),
    }
    config = {
        "experiment": "Solar LSTM + Self-Attention",
        "data_path": str(DATA_PATH.resolve()),
        "target": TARGET_COL,
        "features_in_order": FEATURE_COLS,
        "sequence_length": SEQ_LEN,
        "architecture": architecture,
        "training_settings": {
            "seed": SEED,
            "optimizer": OPTIMIZER,
            "learning_rate": LEARNING_RATE,
            "loss": "mse",
            "batch_size": BATCH_SIZE,
            "maximum_epochs": MAX_EPOCHS,
            "best_epoch": best_epoch,
            "training_duration_seconds": training_duration_seconds,
            "shuffle": False,
            "dropout": DROPOUT_RATE,
            "dense_units": DENSE_UNITS,
            "early_stopping": {
                "monitor": "val_loss",
                "patience": EARLY_STOPPING_PATIENCE,
                "restore_best_weights": True,
            },
            "reduce_lr_on_plateau": {
                "monitor": "val_loss",
                "factor": REDUCE_LR_FACTOR,
                "patience": REDUCE_LR_PATIENCE,
                "minimum_learning_rate": MIN_LEARNING_RATE,
            },
        },
        "split": split_metadata,
        "scaler_fit_rows": len(train_df),
        "scaler_fit_rule": "StandardScaler fit on training rows only",
        "generation_feature_construction": {
            "lag": "per-plant DailyGeneration_MU shifted by one row",
            "rolling": "per-plant shift(1).rolling(7, min_periods=7).mean()",
            "generation_clipping": "DailyGeneration_MU clipped at lower bound 0.0",
        },
        "validation_metrics": val_metrics,
        "test_metrics_after_selection": test_metrics,
        "current_baseline": {
            "source": "Recorded metrics in reports/solar_lstm_rolling_generation_experiment.csv",
            "measurement_status": "Existing reported results; not remeasured in this run",
            "metrics": CURRENT_BASELINE,
        },
        "historical_benchmark": {
            "checkpoint_available": False,
            "measurement_status": "Recorded historical metrics only; not newly measured",
            "validation_r2": HISTORICAL_BENCHMARK["Validation_R2"],
            "test_r2": HISTORICAL_BENCHMARK["Test_R2"],
        },
        "metric_differences_vs_current": metric_differences,
        "validation_r2_improved": val_metrics["R2"]
        > CURRENT_BASELINE["Validation_R2"],
        "selected_model": selected_model,
        "selection_rule": (
            "Select the attention model only when its validation R2 exceeds the "
            "recorded current Solar LSTM validation R2; test metrics are excluded "
            "from model selection."
        ),
        "artifact_paths": artifact_paths,
        "protected_artifact_sha256_before": hashes_before,
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")

    report_rows = [
        {
            "Model": "Solar LSTM + Self-Attention",
            "Metric_Source": "Newly measured in this experiment",
            "Validation_MAE": val_metrics["MAE"],
            "Validation_RMSE": val_metrics["RMSE"],
            "Validation_R2": val_metrics["R2"],
            "Test_MAE": test_metrics["MAE"],
            "Test_RMSE": test_metrics["RMSE"],
            "Test_R2": test_metrics["R2"],
            **metric_differences,
            "Validation_R2_Improved": config["validation_r2_improved"],
            "Selected_Model": selected_model,
            "Architecture": architecture,
            "Feature_List": json.dumps(FEATURE_COLS),
            "Split_Dates": json.dumps(split_metadata),
            "Seed": SEED,
            "Optimizer": OPTIMIZER,
            "Learning_Rate": LEARNING_RATE,
            "Loss": "mse",
            "Batch_Size": BATCH_SIZE,
            "Maximum_Epochs": MAX_EPOCHS,
            "Best_Epoch": best_epoch,
            "Dropout": DROPOUT_RATE,
            "Dense_Units": DENSE_UNITS,
            "Model_Path": artifact_paths["model"],
            "Feature_Scaler_Path": artifact_paths["feature_scaler"],
            "Target_Scaler_Path": artifact_paths["target_scaler"],
            "Config_Path": artifact_paths["configuration"],
        },
        {
            "Model": "Current Solar LSTM",
            "Metric_Source": (
                "Recorded existing report; checkpoint not re-evaluated"
            ),
            **{f"Validation_{key.removeprefix('Validation_')}": value for key, value in CURRENT_BASELINE.items() if key.startswith("Validation_")},
            **{f"Test_{key.removeprefix('Test_')}": value for key, value in CURRENT_BASELINE.items() if key.startswith("Test_")},
            "Selected_Model": selected_model,
        },
        {
            "Model": "Historical Solar benchmark",
            "Metric_Source": "Recorded historical metrics; checkpoint unavailable",
            "Validation_R2": HISTORICAL_BENCHMARK["Validation_R2"],
            "Test_R2": HISTORICAL_BENCHMARK["Test_R2"],
            "Selected_Model": selected_model,
        },
    ]
    pd.DataFrame(report_rows).to_csv(REPORT_PATH, index=False)
    hashes_after = protected_artifact_hashes()
    if hashes_after != hashes_before:
        raise RuntimeError("A protected Solar or Wind artifact changed during the run.")

    print("\nComparison (newly measured vs recorded metrics)")
    print(
        f"{'Model':32} {'Val MAE':>10} {'Val RMSE':>10} {'Val R2':>10} "
        f"{'Test MAE':>10} {'Test RMSE':>10} {'Test R2':>10}"
    )
    rows = [
        ("Solar LSTM + Self-Attention", val_metrics, test_metrics),
        (
            "Current Solar LSTM (recorded)",
            {
                "MAE": CURRENT_BASELINE["Validation_MAE"],
                "RMSE": CURRENT_BASELINE["Validation_RMSE"],
                "R2": CURRENT_BASELINE["Validation_R2"],
            },
            {
                "MAE": CURRENT_BASELINE["Test_MAE"],
                "RMSE": CURRENT_BASELINE["Test_RMSE"],
                "R2": CURRENT_BASELINE["Test_R2"],
            },
        ),
    ]
    for name, validation, test in rows:
        print(
            f"{name:32} {validation['MAE']:10.6f} {validation['RMSE']:10.6f} "
            f"{validation['R2']:10.6f} {test['MAE']:10.6f} "
            f"{test['RMSE']:10.6f} {test['R2']:10.6f}"
        )
    print(
        "\nHistorical Solar benchmark (recorded; checkpoint unavailable): "
        f"Validation R2={HISTORICAL_BENCHMARK['Validation_R2']:.6f}, "
        f"Test R2={HISTORICAL_BENCHMARK['Test_R2']:.6f}"
    )
    print(
        "Attention minus current baseline: "
        + ", ".join(f"{key}={value:+.6f}" for key, value in metric_differences.items())
    )
    print(
        f"Validation R2 improved: {'YES' if config['validation_r2_improved'] else 'NO'}"
    )
    print(f"Selected Solar model: {selected_model}")
    print(f"Best epoch: {best_epoch}; training time: {training_duration_seconds:.1f}s")
    print(f"Report: {REPORT_PATH}")
    print(f"Configuration: {CONFIG_PATH}")
    print("Protected baseline and Wind artifact hashes unchanged.")


if __name__ == "__main__":
    main()

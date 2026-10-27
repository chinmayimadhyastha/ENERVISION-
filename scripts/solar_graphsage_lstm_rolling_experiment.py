"""Fair Solar LSTM and GraphSAGE + LSTM comparison on rolling-feature samples."""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from tensorflow.keras import Model
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import (
    Concatenate,
    Dense,
    Dropout,
    Input,
    LSTM,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "final" / "full_generation_weather_dataset.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
SEQ_LEN = 7
K_NEIGHBORS = 10
HIDDEN_DIM = 32
LSTM_UNITS = (64, 32)
DROP_OUT = 0.3
LEARNING_RATE = 0.0001
BATCH_SIZE = 32
MAX_EPOCHS = 60
PATIENCE = 15
VALIDATION_FRACTION = 0.20
SEEDS = (42, 43, 44)
CUTOFF_DATE = pd.Timestamp("2025-12-31")
TEST_START_DATE = pd.Timestamp("2026-01-01")
TARGET_COL = "DailyGeneration_MU"
WEATHER_COLS = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
BASE_FEATURE_COLS = [
    "Capacity_MW",
    *WEATHER_COLS,
    "Month_sin",
    "Month_cos",
    "DayOfYear_sin",
    "DayOfYear_cos",
    "Lagged_Generation",
]
ROLLING_FEATURE_COLS = [*BASE_FEATURE_COLS, "Rolling_Generation_7"]


def set_seeds(seed: int) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    tf.keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()


def prepare_solar_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    required = {
        "Date",
        "PlantName",
        "Type",
        TARGET_COL,
        *BASE_FEATURE_COLS[:6],
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    solar = df.loc[df["Type"].eq("Solar")].copy()
    solar["Date"] = pd.to_datetime(solar["Date"], errors="raise")
    solar = solar.sort_values(["PlantName", "Date"]).reset_index(drop=True)
    if solar.duplicated(["PlantName", "Date"]).any():
        raise ValueError("Solar dataset contains duplicate PlantName/Date rows.")

    solar[TARGET_COL] = solar[TARGET_COL].clip(lower=0.0)
    for col in WEATHER_COLS:
        solar[col] = solar[col].mask(solar[col] <= -900)
        solar[col] = solar.groupby("PlantName", sort=False)[col].ffill()

    month = solar["Date"].dt.month
    day_of_year = solar["Date"].dt.dayofyear
    solar["Month_sin"] = np.sin(2 * np.pi * month / 12)
    solar["Month_cos"] = np.cos(2 * np.pi * month / 12)
    solar["DayOfYear_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    solar["DayOfYear_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    grouped_generation = solar.groupby("PlantName", sort=False)[TARGET_COL]
    solar["Lagged_Generation"] = grouped_generation.shift(1)
    solar["Rolling_Generation_7"] = grouped_generation.transform(
        lambda values: values.shift(1).rolling(7, min_periods=7).mean()
    )
    return solar.dropna(subset=["Lagged_Generation", "Rolling_Generation_7"]).reset_index(drop=True)


def create_plant_splits(
    solar: pd.DataFrame,
) -> tuple[
    dict[str, pd.DataFrame],
    dict[str, dict[tuple[int, pd.Timestamp], float]],
    list[str],
]:
    plants = sorted(solar["PlantName"].unique().tolist())
    plant_rows: dict[str, pd.DataFrame] = {}
    target_splits: dict[str, dict[tuple[int, pd.Timestamp], float]] = {
        "train": {},
        "validation": {},
        "test": {},
    }

    for plant_index, plant in enumerate(plants):
        rows = solar.loc[solar["PlantName"].eq(plant)].sort_values("Date").reset_index(drop=True)
        plant_rows[plant] = rows
        pre = rows.index[rows["Date"].le(CUTOFF_DATE)].to_numpy()
        split_index = int(len(pre) * (1.0 - VALIDATION_FRACTION))
        for row_index in range(SEQ_LEN, len(rows)):
            date = rows.at[row_index, "Date"]
            if date <= CUTOFF_DATE:
                split = "train" if row_index < split_index else "validation"
            elif date >= TEST_START_DATE:
                split = "test"
            else:
                continue
            if row_index < SEQ_LEN:
                continue
            target_splits[split][(plant_index, date)] = float(rows.at[row_index, TARGET_COL])

    return plant_rows, target_splits, plants


def fit_training_transformers(
    plant_rows: dict[str, pd.DataFrame],
    target_splits: dict[str, dict[tuple[int, pd.Timestamp], float]],
    plants: list[str],
) -> tuple[StandardScaler, StandardScaler, np.ndarray, dict[str, float]]:
    train_keys = target_splits["train"]
    if not train_keys:
        raise ValueError("No training targets remain after sequence construction.")

    feature_training_rows: list[pd.DataFrame] = []
    target_training_values: list[float] = []
    for plant_index, plant in enumerate(plants):
        rows = plant_rows[plant]
        train_row_indices = [
            row_index
            for row_index in range(SEQ_LEN, len(rows))
            if (plant_index, rows.at[row_index, "Date"]) in train_keys
        ]
        if train_row_indices:
            feature_training_rows.append(rows.iloc[train_row_indices][ROLLING_FEATURE_COLS])
            target_training_values.extend(
                float(rows.at[row_index, TARGET_COL]) for row_index in train_row_indices
            )

    training_features = pd.concat(feature_training_rows, ignore_index=True)
    medians = training_features.median(numeric_only=True)
    if medians.isna().any():
        missing_medians = medians.index[medians.isna()].tolist()
        raise ValueError(f"Training data cannot provide medians for: {missing_medians}")

    feature_scaler = StandardScaler()
    feature_scaler.fit(training_features.fillna(medians))
    target_scaler = StandardScaler()
    target_scaler.fit(np.asarray(target_training_values, dtype=np.float64).reshape(-1, 1))
    return (
        feature_scaler,
        target_scaler,
        medians.reindex(ROLLING_FEATURE_COLS).to_numpy(dtype=np.float64),
        {str(name): float(value) for name, value in medians.items()},
    )


def build_profile_graph(
    plant_rows: dict[str, pd.DataFrame],
    target_splits: dict[str, dict[tuple[int, pd.Timestamp], float]],
    plants: list[str],
    feature_scaler: StandardScaler,
    feature_medians: np.ndarray,
) -> tuple[np.ndarray, dict[str, object]]:
    train_keys = target_splits["train"]
    profiles: list[np.ndarray] = []
    active_nodes: list[int] = []
    for plant_index, plant in enumerate(plants):
        rows = plant_rows[plant]
        selected = [
            row_index
            for row_index in range(SEQ_LEN, len(rows))
            if (plant_index, rows.at[row_index, "Date"]) in train_keys
        ]
        if selected:
            profile_rows = rows.iloc[selected][ROLLING_FEATURE_COLS].fillna(
                pd.Series(feature_medians, index=ROLLING_FEATURE_COLS)
            )
            scaled = feature_scaler.transform(profile_rows).astype(np.float64)
            profiles.append(scaled.mean(axis=0))
            active_nodes.append(plant_index)
    if not active_nodes:
        raise ValueError("No plant has eligible training data for fitting the plant graph.")
    profile_matrix = np.stack(profiles)
    profile_scaler = StandardScaler()
    profile_matrix = profile_scaler.fit_transform(profile_matrix)
    norms = np.linalg.norm(profile_matrix, axis=1, keepdims=True)
    normalized = np.divide(profile_matrix, norms, out=np.zeros_like(profile_matrix), where=norms > 0)
    similarities = normalized @ normalized.T
    np.fill_diagonal(similarities, -np.inf)

    node_count = len(plants)
    adjacency = np.zeros((node_count, node_count), dtype=np.float32)
    selected_neighbors: dict[str, list[str]] = {}
    k = min(K_NEIGHBORS, len(active_nodes) - 1)
    for plant in plants:
        selected_neighbors[plant] = []
    if k:
        for local_index, node_index in enumerate(active_nodes):
            neighbor_indices = np.argsort(similarities[local_index])[-k:]
            for local_neighbor in neighbor_indices:
                neighbor = active_nodes[local_neighbor]
                selected_neighbors[plants[node_index]].append(plants[neighbor])
                adjacency[node_index, neighbor] = 1.0
                adjacency[neighbor, node_index] = 1.0

    graph_configuration = {
        "method": "symmetric union of cosine-similarity KNN edges",
        "k_neighbors": k,
        "profile_features": ROLLING_FEATURE_COLS,
        "profile_fit_scope": "training target rows only",
        "plant_order": plants,
        "training_profile_plants": [plants[index] for index in active_nodes],
        "plants_without_training_profiles_are_isolated": [
            plants[index] for index in range(len(plants)) if index not in active_nodes
        ],
        "neighbors": selected_neighbors,
        "adjacency": adjacency.tolist(),
    }
    return adjacency, graph_configuration


def make_snapshots(
    plant_rows: dict[str, pd.DataFrame],
    target_splits: dict[str, dict[tuple[int, pd.Timestamp], float]],
    plants: list[str],
    feature_scaler: StandardScaler,
    target_scaler: StandardScaler,
    feature_medians: np.ndarray,
) -> dict[str, tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, list[pd.Timestamp]]]:
    all_dates = sorted({date for split in target_splits.values() for _, date in split})
    n_dates = len(all_dates)
    n_plants = len(plants)
    n_features = len(ROLLING_FEATURE_COLS)
    histories = np.zeros((n_dates, n_plants, SEQ_LEN, n_features), dtype=np.float32)
    node_mask = np.zeros((n_dates, n_plants), dtype=np.float32)
    labels = {
        split: np.zeros((n_dates, n_plants, 1), dtype=np.float32)
        for split in target_splits
    }
    weights = {
        split: np.zeros((n_dates, n_plants, 1), dtype=np.float32)
        for split in target_splits
    }
    date_index = {date: index for index, date in enumerate(all_dates)}

    scaled_plant_features: list[np.ndarray] = []
    for plant in plants:
        rows = plant_rows[plant]
        values = rows[ROLLING_FEATURE_COLS].fillna(
            pd.Series(feature_medians, index=ROLLING_FEATURE_COLS)
        )
        scaled_plant_features.append(feature_scaler.transform(values).astype(np.float32))

    for date, snapshot_index in date_index.items():
        for plant_index, plant in enumerate(plants):
            rows = plant_rows[plant]
            prior_end = int(rows["Date"].searchsorted(date, side="left"))
            if prior_end < SEQ_LEN:
                continue
            histories[snapshot_index, plant_index] = scaled_plant_features[plant_index][
                prior_end - SEQ_LEN : prior_end
            ]
            node_mask[snapshot_index, plant_index] = 1.0

    for split_name, split_targets in target_splits.items():
        for (plant_index, date), target in split_targets.items():
            snapshot_index = date_index[date]
            scaled_target = target_scaler.transform([[target]])[0, 0]
            labels[split_name][snapshot_index, plant_index, 0] = scaled_target
            weights[split_name][snapshot_index, plant_index, 0] = 1.0

    result = {}
    for split_name in target_splits:
        active_dates = np.flatnonzero(weights[split_name].sum(axis=(1, 2)) > 0)
        result[split_name] = (
            {
                "history": histories[active_dates],
                "node_mask": node_mask[active_dates],
            },
            labels[split_name][active_dates],
            weights[split_name][active_dates],
            [all_dates[index] for index in active_dates],
        )
    return result


@tf.keras.utils.register_keras_serializable(package="EnerVision")
class MeanGraphSAGE(tf.keras.layers.Layer):
    def __init__(self, adjacency: list[list[float]], units: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.adjacency_values = adjacency
        self.units = units
        self.projection = Dense(units, activation="relu")

    def build(self, input_shape: tuple[tf.TensorShape, tf.TensorShape]) -> None:
        feature_count = int(input_shape[0][-1])
        projection_shape = tuple(input_shape[0][:-1]) + (feature_count * 2,)
        self.projection.build(projection_shape)
        super().build(input_shape)

    def call(self, inputs: tuple[tf.Tensor, tf.Tensor]) -> tf.Tensor:
        node_features, node_mask = inputs
        adjacency = tf.cast(tf.convert_to_tensor(self.adjacency_values), node_features.dtype)
        mask = tf.cast(node_mask[..., tf.newaxis], node_features.dtype)
        available_neighbors = tf.matmul(adjacency, mask)
        neighbor_sum = tf.matmul(adjacency, node_features * mask)
        neighbor_mean = tf.math.divide_no_nan(neighbor_sum, available_neighbors)
        return self.projection(tf.concat([node_features, neighbor_mean], axis=-1))

    def get_config(self) -> dict[str, object]:
        config = super().get_config()
        config.update({"adjacency": self.adjacency_values, "units": self.units})
        return config


@tf.keras.utils.register_keras_serializable(package="EnerVision")
class LastTimeStep(tf.keras.layers.Layer):
    def call(self, inputs: tf.Tensor) -> tf.Tensor:
        return inputs[:, :, -1, :]


@tf.keras.utils.register_keras_serializable(package="EnerVision")
class FlattenPlantSequences(tf.keras.layers.Layer):
    def __init__(self, node_count: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.node_count = node_count

    def call(self, inputs: tf.Tensor) -> tf.Tensor:
        shape = tf.shape(inputs)
        return tf.reshape(inputs, (shape[0] * self.node_count, shape[2], shape[3]))

    def get_config(self) -> dict[str, object]:
        config = super().get_config()
        config.update({"node_count": self.node_count})
        return config


@tf.keras.utils.register_keras_serializable(package="EnerVision")
class RestorePlantDimension(tf.keras.layers.Layer):
    def __init__(self, node_count: int, units: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.node_count = node_count
        self.units = units

    def call(self, inputs: tuple[tf.Tensor, tf.Tensor]) -> tf.Tensor:
        values, node_mask = inputs
        return tf.reshape(values, (tf.shape(node_mask)[0], self.node_count, self.units))

    def get_config(self) -> dict[str, object]:
        config = super().get_config()
        config.update({"node_count": self.node_count, "units": self.units})
        return config


def build_lstm_model(node_count: int, feature_count: int) -> Model:
    history = Input(shape=(node_count, SEQ_LEN, feature_count), name="history")
    node_mask = Input(shape=(node_count,), name="node_mask")
    x = FlattenPlantSequences(node_count)(history)
    x = LSTM(LSTM_UNITS[0], return_sequences=True)(x)
    x = Dropout(DROP_OUT)(x)
    x = LSTM(LSTM_UNITS[1])(x)
    x = Dropout(DROP_OUT)(x)
    x = RestorePlantDimension(node_count, LSTM_UNITS[1])([x, node_mask])
    x = Dense(16, activation="relu")(x)
    output = Dense(1, name="generation")(x)
    output = tf.keras.layers.Multiply()([output, tf.keras.layers.Reshape((node_count, 1))(node_mask)])
    model = Model({"history": history, "node_mask": node_mask}, output)
    model.compile(optimizer=tf.keras.optimizers.Nadam(learning_rate=LEARNING_RATE), loss="mse")
    return model


def build_graphsage_lstm_model(
    node_count: int,
    feature_count: int,
    adjacency: np.ndarray,
) -> Model:
    history = Input(shape=(node_count, SEQ_LEN, feature_count), name="history")
    node_mask = Input(shape=(node_count,), name="node_mask")
    current_features = LastTimeStep(name="latest_node_features")(history)
    graph = MeanGraphSAGE(adjacency.tolist(), HIDDEN_DIM, name="graphsage_mean_1")(
        [current_features, node_mask]
    )
    graph = Dropout(DROP_OUT)(graph)
    graph = MeanGraphSAGE(adjacency.tolist(), HIDDEN_DIM, name="graphsage_mean_2")(
        [graph, node_mask]
    )

    temporal = FlattenPlantSequences(node_count)(history)
    temporal = LSTM(LSTM_UNITS[0], return_sequences=True)(temporal)
    temporal = Dropout(DROP_OUT)(temporal)
    temporal = LSTM(LSTM_UNITS[1])(temporal)
    temporal = Dropout(DROP_OUT)(temporal)
    temporal = RestorePlantDimension(node_count, LSTM_UNITS[1])([temporal, node_mask])
    combined = Concatenate(name="spatial_temporal_fusion")([temporal, graph])
    combined = Dropout(DROP_OUT)(combined)
    combined = Dense(16, activation="relu")(combined)
    output = Dense(1, name="generation")(combined)
    model = Model({"history": history, "node_mask": node_mask}, output)
    model.compile(optimizer=tf.keras.optimizers.Nadam(learning_rate=LEARNING_RATE), loss="mse")
    return model


def evaluate(
    model: Model,
    inputs: dict[str, np.ndarray],
    scaled_targets: np.ndarray,
    sample_weights: np.ndarray,
    target_scaler: StandardScaler,
) -> dict[str, float | int]:
    predictions_scaled = model.predict(inputs, verbose=0)
    mask = sample_weights.reshape(-1) > 0
    y_true = target_scaler.inverse_transform(scaled_targets.reshape(-1, 1)).reshape(-1)[mask]
    y_pred = target_scaler.inverse_transform(predictions_scaled.reshape(-1, 1)).reshape(-1)[mask]
    nonzero = np.abs(y_true) > 1e-4
    return {
        "sample_count": int(mask.sum()),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "mape": float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])) * 100)
        if nonzero.any()
        else float("nan"),
        "mape_excluded_zero_targets": int((~nonzero).sum()),
    }


def train_model(
    model_name: str,
    seed: int,
    snapshots: dict[str, tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, list[pd.Timestamp]]],
    target_scaler: StandardScaler,
    node_count: int,
    feature_count: int,
    adjacency: np.ndarray,
) -> tuple[dict[str, object], Model]:
    set_seeds(seed)
    tf.keras.backend.clear_session()
    model = (
        build_lstm_model(node_count, feature_count)
        if model_name != "Solar GraphSAGE + LSTM"
        else build_graphsage_lstm_model(node_count, feature_count, adjacency)
    )
    train_inputs, train_targets, train_weights, _ = snapshots["train"]
    validation_inputs, validation_targets, validation_weights, _ = snapshots["validation"]
    callbacks = [
        EarlyStopping(monitor="val_loss", patience=PATIENCE, restore_best_weights=True),
        ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6),
    ]
    started = time.perf_counter()
    history = model.fit(
        train_inputs,
        train_targets,
        sample_weight=train_weights,
        validation_data=(validation_inputs, validation_targets, validation_weights),
        epochs=MAX_EPOCHS,
        batch_size=BATCH_SIZE,
        shuffle=False,
        callbacks=callbacks,
        verbose=0,
    )
    duration_seconds = time.perf_counter() - started
    best_epoch = int(np.argmin(history.history["val_loss"]) + 1)
    validation_metrics = evaluate(
        model, validation_inputs, validation_targets, validation_weights, target_scaler
    )
    test_inputs, test_targets, test_weights, _ = snapshots["test"]
    test_metrics = evaluate(model, test_inputs, test_targets, test_weights, target_scaler)

    record: dict[str, object] = {
        "model": model_name,
        "seed": seed,
        "best_epoch": best_epoch,
        "training_duration_seconds": duration_seconds,
        "train_sample_count": int(train_weights.sum()),
        "validation_sample_count": validation_metrics["sample_count"],
        "test_sample_count": test_metrics["sample_count"],
        "feature_count": len(BASE_FEATURE_COLS) if model_name == "Solar LSTM (11 features)" else len(ROLLING_FEATURE_COLS),
        "sequence_length": SEQ_LEN,
        "k_neighbors": K_NEIGHBORS if model_name == "Solar GraphSAGE + LSTM" else None,
        "graphsage_hidden_dimension": HIDDEN_DIM if model_name == "Solar GraphSAGE + LSTM" else None,
        "aggregation": "mean" if model_name == "Solar GraphSAGE + LSTM" else None,
        "lstm_units": "64,32",
        "dropout": DROP_OUT,
        "optimizer": "Nadam",
        "learning_rate": LEARNING_RATE,
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAX_EPOCHS,
        "early_stopping_patience": PATIENCE,
    }
    for split, metrics in (("validation", validation_metrics), ("test", test_metrics)):
        for metric, value in metrics.items():
            record[f"{split}_{metric}"] = value
    return record, model


def print_final_summary(report: pd.DataFrame) -> str:
    grouped = report.groupby("model").agg(
        validation_r2=("validation_r2", "mean"),
        validation_mae=("validation_mae", "mean"),
        validation_rmse=("validation_rmse", "mean"),
        validation_mape=("validation_mape", "mean"),
        test_r2=("test_r2", "mean"),
        test_mae=("test_mae", "mean"),
        test_rmse=("test_rmse", "mean"),
        test_mape=("test_mape", "mean"),
    )
    baseline_name = "Solar LSTM (12 features)"
    graph_name = "Solar GraphSAGE + LSTM"
    baseline = grouped.loc[baseline_name]
    graph = grouped.loc[graph_name]
    val_r2_delta = float(graph.validation_r2 - baseline.validation_r2)
    test_r2_delta = float(graph.test_r2 - baseline.test_r2)
    val_mae_delta = float(graph.validation_mae - baseline.validation_mae)
    test_mae_delta = float(graph.test_mae - baseline.test_mae)
    graph_by_seed = report.loc[report["model"].eq(graph_name)].set_index("seed")
    rolling_by_seed = report.loc[report["model"].eq(baseline_name)].set_index("seed")
    all_seeds_improved = bool(
        (graph_by_seed["validation_r2"] > rolling_by_seed["validation_r2"]).all()
    )
    keep = (
        val_r2_delta >= 0.01
        and val_mae_delta < 0
        and all_seeds_improved
        and test_r2_delta >= -0.01
        and test_mae_delta <= 0.01
    )
    decision = "KEEP graph model as preferred candidate" if keep else "REVERT to rolling-feature Solar LSTM"
    print("\n" + "=" * 88)
    print("FINAL COMPARISON (mean across fixed seeds; test is final evaluation only)")
    print("=" * 88)
    print("Metric                Rolling LSTM    GraphSAGE + LSTM      Difference (graph - LSTM)")
    for metric in ("validation_r2", "validation_mae", "validation_rmse", "validation_mape",
                   "test_r2", "test_mae", "test_rmse", "test_mape"):
        print(
            f"{metric:21s} {grouped.loc[baseline_name, metric]:12.6f} "
            f"{grouped.loc[graph_name, metric]:18.6f} "
            f"{grouped.loc[graph_name, metric] - grouped.loc[baseline_name, metric]:+22.6f}"
        )
    print(f"Validation R² difference: {val_r2_delta:+.6f}")
    print(f"Validation MAE difference: {val_mae_delta:+.6f} MU")
    print(f"Test R² difference       : {test_r2_delta:+.6f}")
    print(f"Test MAE difference      : {test_mae_delta:+.6f} MU")
    print(f"Recommendation           : {decision}")
    print("Meaningful-improvement rule: validation R² gain >= 0.01 and validation MAE improves")
    print(f"across all seeds={all_seeds_improved};")
    print("test R² must not fall by more than 0.01 and test MAE must not worsen by > 0.01 MU.")
    return decision


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    solar = prepare_solar_data()
    plant_rows, target_splits, plants = create_plant_splits(solar)
    feature_scaler, target_scaler, feature_medians, median_config = fit_training_transformers(
        plant_rows, target_splits, plants
    )
    adjacency, graph_config = build_profile_graph(
        plant_rows, target_splits, plants, feature_scaler, feature_medians
    )
    snapshots = make_snapshots(
        plant_rows, target_splits, plants, feature_scaler, target_scaler, feature_medians
    )
    sample_counts = {
        name: int(values[2].sum()) for name, values in snapshots.items()
    }
    if sample_counts["train"] == 0 or sample_counts["validation"] == 0 or sample_counts["test"] == 0:
        raise ValueError(f"Insufficient common samples for comparison: {sample_counts}")

    # Feature A uses the first 11 channels of the exact same 12-feature histories.
    original_feature_count = len(BASE_FEATURE_COLS)
    snapshots_11 = {
        split: (
            {**inputs, "history": inputs["history"][..., :original_feature_count]},
            targets,
            weights,
            dates,
        )
        for split, (inputs, targets, weights, dates) in snapshots.items()
    }

    records: list[dict[str, object]] = []
    best_graph_model: Model | None = None
    best_graph_validation_r2 = -np.inf
    for seed in SEEDS:
        print(f"\nSeed {seed}: training three models on shared date/plant samples...", flush=True)
        for model_name, model_snapshots in (
            ("Solar LSTM (11 features)", snapshots_11),
            ("Solar LSTM (12 features)", snapshots),
            ("Solar GraphSAGE + LSTM", snapshots),
        ):
            run_record, model = train_model(
                model_name,
                seed,
                model_snapshots,
                target_scaler,
                len(plants),
                len(model_snapshots["train"][0]["history"][0, 0, 0]),
                adjacency,
            )
            records.append(run_record)
            print(
                f"  {model_name}: val R²={run_record['validation_r2']:.6f}, "
                f"test R²={run_record['test_r2']:.6f}, "
                f"best epoch={run_record['best_epoch']}, "
                f"time={run_record['training_duration_seconds']:.1f}s",
                flush=True,
            )
            if model_name == "Solar GraphSAGE + LSTM":
                if float(run_record["validation_r2"]) > best_graph_validation_r2:
                    best_graph_validation_r2 = float(run_record["validation_r2"])
                    best_graph_model = model

    report = pd.DataFrame(records)
    for column in ("train_sample_count", "validation_sample_count", "test_sample_count"):
        if report.groupby("model")[column].nunique().gt(1).any():
            raise RuntimeError(f"Models were not evaluated on identical {column} counts.")
    report_path = REPORTS_DIR / "solar_graphsage_lstm_rolling_experiment.csv"
    report.to_csv(report_path, index=False)
    if best_graph_model is None:
        raise RuntimeError("GraphSAGE model training did not produce a candidate checkpoint.")

    best_graph_model.save(MODELS_DIR / "solar_graphsage_lstm_rolling_7.keras")
    joblib.dump(feature_scaler, MODELS_DIR / "solar_graphsage_lstm_rolling_feature_scaler.joblib")
    joblib.dump(target_scaler, MODELS_DIR / "solar_graphsage_lstm_rolling_target_scaler.joblib")
    graph_path = MODELS_DIR / "solar_graphsage_lstm_rolling_graph.json"
    graph_path.write_text(json.dumps(graph_config, indent=2), encoding="utf-8")
    graph_records = report.loc[report["model"].eq("Solar GraphSAGE + LSTM")]
    best_graph_seed = int(graph_records.loc[graph_records["validation_r2"].idxmax(), "seed"])
    config = {
        "data_path": str(DATA_PATH.relative_to(BASE_DIR)),
        "target": TARGET_COL,
        "base_features": BASE_FEATURE_COLS,
        "rolling_features": ROLLING_FEATURE_COLS,
        "sequence_length": SEQ_LEN,
        "validation_fraction_per_plant": VALIDATION_FRACTION,
        "training_validation_cutoff": str(CUTOFF_DATE.date()),
        "test_start_date": str(TEST_START_DATE.date()),
        "seeds": list(SEEDS),
        "sample_counts": sample_counts,
        "plants": plants,
        "weather_training_medians": median_config,
        "hyperparameters": {
            "knn_neighbors": K_NEIGHBORS,
            "graphsage_hidden_dimension": HIDDEN_DIM,
            "graphsage_aggregation": "mean",
            "lstm_units": list(LSTM_UNITS),
            "dropout": DROP_OUT,
            "optimizer": "Nadam",
            "learning_rate": LEARNING_RATE,
            "batch_size": BATCH_SIZE,
            "maximum_epochs": MAX_EPOCHS,
            "early_stopping_patience": PATIENCE,
        },
        "recommended_model": None,
        "saved_graph_checkpoint_seed": best_graph_seed,
    }
    config["recommended_model"] = print_final_summary(report)
    (MODELS_DIR / "solar_graphsage_lstm_rolling_config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    print(f"\nSaved experiment report: {report_path}")
    print(f"Saved GraphSAGE + LSTM: {MODELS_DIR / 'solar_graphsage_lstm_rolling_7.keras'}")
    print(f"Saved scalers, graph, and configuration under: {MODELS_DIR}")


if __name__ == "__main__":
    main()

"""Validation-only ablation of temporal and GraphSAGE feature fusion."""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from tensorflow.keras import Model
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import Dense, Dropout, Input, LSTM

import solar_graphsage_lstm_rolling_experiment as rolling

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
MODELS_DIR = BASE_DIR / "models"
BASELINE_REPORT = REPORTS_DIR / "solar_graphsage_lstm_rolling_experiment.csv"
SCREEN_SEED = 42
SCREEN_K = 3
SCREEN_HIDDEN_DIM = 16
SCREEN_DEPTH = 1


def set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    tf.keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()


def build_training_graph(
    plant_rows: dict[str, pd.DataFrame],
    target_splits: dict[str, dict[tuple[int, pd.Timestamp], float]],
    plants: list[str],
    feature_scaler: StandardScaler,
    feature_medians: np.ndarray,
    k_neighbors: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    profiles: list[np.ndarray] = []
    active_nodes: list[int] = []
    train_targets = target_splits["train"]
    for plant_index, plant in enumerate(plants):
        rows = plant_rows[plant]
        row_indices = [
            row_index
            for row_index in range(rolling.SEQ_LEN, len(rows))
            if (plant_index, rows.at[row_index, "Date"]) in train_targets
        ]
        if not row_indices:
            continue
        profile_rows = rows.iloc[row_indices][rolling.ROLLING_FEATURE_COLS].fillna(
            pd.Series(feature_medians, index=rolling.ROLLING_FEATURE_COLS)
        )
        profiles.append(feature_scaler.transform(profile_rows).mean(axis=0))
        active_nodes.append(plant_index)

    if len(active_nodes) < 2:
        raise ValueError("At least two plants must have training profiles to build a graph.")

    profile_matrix = np.stack(profiles)
    profile_matrix = StandardScaler().fit_transform(profile_matrix)
    norms = np.linalg.norm(profile_matrix, axis=1, keepdims=True)
    normalized_profiles = np.divide(
        profile_matrix, norms, out=np.zeros_like(profile_matrix), where=norms > 0
    )
    similarities = normalized_profiles @ normalized_profiles.T
    np.fill_diagonal(similarities, -np.inf)
    k = min(k_neighbors, len(active_nodes) - 1)
    adjacency = np.zeros((len(plants), len(plants)), dtype=np.float32)
    neighbors: dict[str, list[str]] = {plant: [] for plant in plants}
    for local_index, node_index in enumerate(active_nodes):
        local_neighbors = np.argsort(similarities[local_index])[-k:]
        for local_neighbor in local_neighbors:
            neighbor_index = active_nodes[local_neighbor]
            adjacency[node_index, neighbor_index] = 1.0
            adjacency[neighbor_index, node_index] = 1.0
            neighbors[plants[node_index]].append(plants[neighbor_index])

    degrees = adjacency.sum(axis=1)
    config: dict[str, Any] = {
        "method": "symmetric-union KNN over cosine similarity of training-only feature profiles",
        "profile_features": rolling.ROLLING_FEATURE_COLS,
        "profile_fit_scope": "training rows only",
        "k_neighbors": k,
        "plant_order": plants,
        "training_profile_plants": [plants[index] for index in active_nodes],
        "isolated_plants": [
            plants[index] for index, degree in enumerate(degrees) if degree == 0
        ],
        "edge_count_undirected": int(adjacency.sum() // 2),
        "self_loops": int(np.diag(adjacency).sum()),
        "symmetric": bool(np.array_equal(adjacency, adjacency.T)),
        "neighbors": neighbors,
        "adjacency": adjacency.tolist(),
    }
    return adjacency, config


@tf.keras.utils.register_keras_serializable(package="EnerVision")
class GraphSAGEOverHistory(tf.keras.layers.Layer):
    def __init__(
        self,
        adjacency: list[list[float]],
        units: int,
        depth: int = 1,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.adjacency_values = adjacency
        self.units = units
        self.depth = depth
        self.projections = [
            Dense(units, activation="relu", name=f"mean_projection_{index + 1}")
            for index in range(depth)
        ]

    def build(
        self,
        input_shape: tuple[tf.TensorShape, tf.TensorShape],
    ) -> None:
        feature_count = int(input_shape[0][-1])
        input_width = feature_count
        for projection in self.projections:
            projection.build((None, None, input_width * 2))
            input_width = self.units
        super().build(input_shape)

    def call(self, inputs: tuple[tf.Tensor, tf.Tensor]) -> tf.Tensor:
        history, node_mask = inputs
        node_features = tf.transpose(history, (0, 2, 1, 3))
        dynamic_shape = tf.shape(node_features)
        batch_size, steps, node_count = dynamic_shape[0], dynamic_shape[1], dynamic_shape[2]
        feature_count = dynamic_shape[3]
        node_features = tf.reshape(
            node_features, (batch_size * steps, node_count, feature_count)
        )
        repeated_mask = tf.repeat(node_mask[:, tf.newaxis, :], repeats=steps, axis=1)
        repeated_mask = tf.reshape(repeated_mask, (batch_size * steps, node_count, 1))
        adjacency = tf.cast(tf.convert_to_tensor(self.adjacency_values), node_features.dtype)
        for projection in self.projections:
            neighbor_count = tf.matmul(adjacency, repeated_mask)
            neighbor_sum = tf.matmul(adjacency, node_features * repeated_mask)
            neighbor_mean = tf.math.divide_no_nan(neighbor_sum, neighbor_count)
            node_features = projection(tf.concat([node_features, neighbor_mean], axis=-1))
        node_features = tf.reshape(
            node_features, (batch_size, steps, node_count, self.units)
        )
        return tf.transpose(node_features, (0, 2, 1, 3))

    def get_config(self) -> dict[str, Any]:
        config = super().get_config()
        config.update(
            {
                "adjacency": self.adjacency_values,
                "units": self.units,
                "depth": self.depth,
            }
        )
        return config


@tf.keras.utils.register_keras_serializable(package="EnerVision")
class LatestStep(tf.keras.layers.Layer):
    def call(self, inputs: tf.Tensor) -> tf.Tensor:
        return inputs[:, :, -1, :]


@tf.keras.utils.register_keras_serializable(package="EnerVision")
class FlattenPlants(tf.keras.layers.Layer):
    def __init__(self, node_count: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_count = node_count

    def call(self, inputs: tf.Tensor) -> tf.Tensor:
        shape = tf.shape(inputs)
        return tf.reshape(inputs, (shape[0] * self.node_count, shape[2], shape[3]))

    def get_config(self) -> dict[str, Any]:
        config = super().get_config()
        config.update({"node_count": self.node_count})
        return config


@tf.keras.utils.register_keras_serializable(package="EnerVision")
class RestorePlants(tf.keras.layers.Layer):
    def __init__(self, node_count: int, units: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_count = node_count
        self.units = units

    def call(self, inputs: tuple[tf.Tensor, tf.Tensor]) -> tf.Tensor:
        values, node_mask = inputs
        return tf.reshape(
            values, (tf.shape(node_mask)[0], self.node_count, self.units)
        )

    def get_config(self) -> dict[str, Any]:
        config = super().get_config()
        config.update({"node_count": self.node_count, "units": self.units})
        return config


@tf.keras.utils.register_keras_serializable(package="EnerVision")
class ResidualGraphFusion(tf.keras.layers.Layer):
    def __init__(self, feature_count: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.feature_count = feature_count
        self.projection = Dense(feature_count, use_bias=False)

    def build(self, input_shape: tuple[tf.TensorShape, tf.TensorShape]) -> None:
        self.projection.build(input_shape[1])
        self.gate = self.add_weight(
            name="graph_residual_gate",
            shape=(),
            initializer=tf.keras.initializers.Constant(0.1),
            trainable=True,
        )
        super().build(input_shape)

    def call(self, inputs: tuple[tf.Tensor, tf.Tensor]) -> tf.Tensor:
        original, graph = inputs
        return original + self.gate * self.projection(graph)

    def get_config(self) -> dict[str, Any]:
        config = super().get_config()
        config.update({"feature_count": self.feature_count})
        return config


def compile_model(model: Model) -> Model:
    model.compile(
        optimizer=tf.keras.optimizers.Nadam(learning_rate=rolling.LEARNING_RATE),
        loss="mse",
    )
    return model


def build_fusion_model(
    variant: str,
    node_count: int,
    feature_count: int,
    adjacency: np.ndarray,
    hidden_dim: int,
    depth: int,
) -> Model:
    history = Input(
        shape=(node_count, rolling.SEQ_LEN, feature_count), name="history"
    )
    node_mask = Input(shape=(node_count,), name="node_mask")
    graph = GraphSAGEOverHistory(
        adjacency.tolist(), hidden_dim, depth, name="graphsage_over_history"
    )([history, node_mask])
    if variant == "graph_only":
        features = LatestStep()(graph)
        features = Dense(16, activation="relu")(features)
        predictions = Dense(1, name="generation")(features)
    else:
        if variant == "concat":
            recurrent_input = tf.keras.layers.Concatenate(axis=-1)(
                [history, graph]
            )
        elif variant == "residual":
            recurrent_input = ResidualGraphFusion(feature_count)(
                [history, graph]
            )
        else:
            raise ValueError(f"Unknown fusion variant: {variant}")
        recurrent_input = FlattenPlants(node_count)(recurrent_input)
        temporal = LSTM(rolling.LSTM_UNITS[0], return_sequences=True)(
            recurrent_input
        )
        temporal = Dropout(rolling.DROP_OUT)(temporal)
        temporal = LSTM(rolling.LSTM_UNITS[1])(temporal)
        temporal = Dropout(rolling.DROP_OUT)(temporal)
        temporal = RestorePlants(node_count, rolling.LSTM_UNITS[1])(
            [temporal, node_mask]
        )
        temporal = Dense(16, activation="relu")(temporal)
        predictions = Dense(1, name="generation")(temporal)
    predictions = tf.keras.layers.Multiply()(
        [predictions, tf.keras.layers.Reshape((node_count, 1))(node_mask)]
    )
    return compile_model(Model({"history": history, "node_mask": node_mask}, predictions))


def read_baseline() -> dict[str, Any]:
    if not BASELINE_REPORT.exists():
        raise FileNotFoundError(
            f"Comparable rolling baseline report not found: {BASELINE_REPORT}"
        )
    baseline = pd.read_csv(BASELINE_REPORT)
    baseline = baseline.loc[
        baseline["model"].eq("Solar LSTM (12 features)")
        & baseline["seed"].eq(SCREEN_SEED)
    ]
    if len(baseline) != 1:
        raise ValueError("Expected one rolling LSTM baseline result for seed 42.")
    return baseline.iloc[0].to_dict()


def prepare_experiment() -> tuple[
    pd.DataFrame,
    dict[str, pd.DataFrame],
    dict[str, dict[tuple[int, pd.Timestamp], float]],
    list[str],
    StandardScaler,
    StandardScaler,
    np.ndarray,
    dict[str, float],
    dict[str, tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, list[pd.Timestamp]]],
]:
    solar = rolling.prepare_solar_data()
    plant_rows, target_splits, plants = rolling.create_plant_splits(solar)
    feature_scaler, target_scaler, feature_medians, median_config = (
        rolling.fit_training_transformers(plant_rows, target_splits, plants)
    )
    snapshots = rolling.make_snapshots(
        plant_rows,
        target_splits,
        plants,
        feature_scaler,
        target_scaler,
        feature_medians,
    )
    return (
        solar,
        plant_rows,
        target_splits,
        plants,
        feature_scaler,
        target_scaler,
        feature_medians,
        median_config,
        snapshots,
    )


def run_screen() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    baseline = read_baseline()
    (
        _,
        plant_rows,
        target_splits,
        plants,
        feature_scaler,
        target_scaler,
        feature_medians,
        median_config,
        snapshots,
    ) = prepare_experiment()
    sample_counts = {
        name: int(values[2].sum()) for name, values in snapshots.items()
    }
    expected_counts = {
        name: int(baseline[f"{name}_sample_count"])
        for name in ("train", "validation", "test")
    }
    if sample_counts != expected_counts:
        raise ValueError(
            f"Screen data does not match baseline plant/date sample counts: "
            f"{sample_counts} != {expected_counts}"
        )

    train_inputs, train_targets, train_weights, _ = snapshots["train"]
    validation_inputs, validation_targets, validation_weights, _ = snapshots[
        "validation"
    ]
    adjacency, graph_config = build_training_graph(
        plant_rows,
        target_splits,
        plants,
        feature_scaler,
        feature_medians,
        SCREEN_K,
    )
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    variants = ("graph_only", "concat", "residual")
    screen_rows: list[dict[str, Any]] = [
        {
            "model": "rolling_lstm_baseline",
            "variant": "temporal_only",
            "seed": SCREEN_SEED,
            "k_neighbors": None,
            "hidden_dimension": None,
            "graphsage_depth": None,
            "best_epoch": int(baseline["best_epoch"]),
            "training_duration_seconds": float(baseline["training_duration_seconds"]),
            "train_sample_count": sample_counts["train"],
            "validation_sample_count": sample_counts["validation"],
            **{
                f"validation_{metric}": float(baseline[f"validation_{metric}"])
                for metric in ("mae", "rmse", "r2", "mape")
            },
        }
    ]
    configs: dict[str, Any] = {}
    for variant in variants:
        print(
            f"Screening {variant}: K={SCREEN_K}, hidden={SCREEN_HIDDEN_DIM}, "
            f"depth={SCREEN_DEPTH}, seed={SCREEN_SEED}",
            flush=True,
        )
        set_seeds(SCREEN_SEED)
        tf.keras.backend.clear_session()
        model = build_fusion_model(
            variant,
            len(plants),
            len(rolling.ROLLING_FEATURE_COLS),
            adjacency,
            SCREEN_HIDDEN_DIM,
            SCREEN_DEPTH,
        )
        callbacks = [
            EarlyStopping(
                monitor="val_loss",
                patience=rolling.PATIENCE,
                restore_best_weights=True,
            ),
            ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=5,
                min_lr=1e-6,
            ),
        ]
        started = time.perf_counter()
        history = model.fit(
            train_inputs,
            train_targets,
            sample_weight=train_weights,
            validation_data=(validation_inputs, validation_targets, validation_weights),
            epochs=rolling.MAX_EPOCHS,
            batch_size=rolling.BATCH_SIZE,
            shuffle=False,
            callbacks=callbacks,
            verbose=0,
        )
        duration = time.perf_counter() - started
        metrics = rolling.evaluate(
            model,
            validation_inputs,
            validation_targets,
            validation_weights,
            target_scaler,
        )
        best_epoch = int(np.argmin(history.history["val_loss"]) + 1)
        checkpoint_name = (
            f"solar_graphsage_lstm_fusion_{variant}_screen_{run_stamp}_seed42.keras"
        )
        model.save(MODELS_DIR / checkpoint_name)
        row = {
            "model": f"graphsage_{variant}",
            "variant": variant,
            "seed": SCREEN_SEED,
            "k_neighbors": SCREEN_K,
            "hidden_dimension": SCREEN_HIDDEN_DIM,
            "graphsage_depth": SCREEN_DEPTH,
            "best_epoch": best_epoch,
            "training_duration_seconds": duration,
            "train_sample_count": sample_counts["train"],
            "validation_sample_count": metrics["sample_count"],
            "checkpoint": checkpoint_name,
            **{f"validation_{name}": value for name, value in metrics.items() if name != "sample_count"},
        }
        screen_rows.append(row)
        configs[variant] = {
            "variant": variant,
            "seed": SCREEN_SEED,
            "k_neighbors": SCREEN_K,
            "hidden_dimension": SCREEN_HIDDEN_DIM,
            "graphsage_depth": SCREEN_DEPTH,
            "checkpoint": checkpoint_name,
            "best_epoch": best_epoch,
            "training_duration_seconds": duration,
        }
        print(
            f"  validation R²={metrics['r2']:.6f}, "
            f"MAE={metrics['mae']:.6f} MU, best epoch={best_epoch}, "
            f"duration={duration:.1f}s",
            flush=True,
        )

    report = pd.DataFrame(screen_rows)
    screen_report_path = REPORTS_DIR / (
        f"solar_graphsage_lstm_fusion_screen_{run_stamp}.csv"
    )
    screen_config_path = MODELS_DIR / (
        f"solar_graphsage_lstm_fusion_screen_config_{run_stamp}.json"
    )
    feature_scaler_path = MODELS_DIR / (
        f"solar_graphsage_lstm_fusion_feature_scaler_{run_stamp}.joblib"
    )
    target_scaler_path = MODELS_DIR / (
        f"solar_graphsage_lstm_fusion_target_scaler_{run_stamp}.joblib"
    )
    graph_path = MODELS_DIR / f"solar_graphsage_lstm_fusion_graph_{run_stamp}.json"
    report.to_csv(screen_report_path, index=False)
    joblib.dump(feature_scaler, feature_scaler_path)
    joblib.dump(target_scaler, target_scaler_path)
    graph_path.write_text(json.dumps(graph_config, indent=2), encoding="utf-8")

    baseline_row = report.loc[report["variant"].eq("temporal_only")].iloc[0]
    eligible = report.loc[~report["variant"].eq("temporal_only")].copy()
    eligible = eligible.loc[
        (eligible["validation_r2"] > baseline_row["validation_r2"])
        & (eligible["validation_mae"] < baseline_row["validation_mae"])
    ]
    decision = (
        "continue_to_three_seed_confirmation"
        if not eligible.empty
        else "retain_rolling_feature_lstm"
    )
    selected_variant = (
        str(eligible.sort_values(["validation_r2", "validation_mae"], ascending=[False, True]).iloc[0]["variant"])
        if not eligible.empty
        else None
    )
    config = {
        "stage": "single-seed validation screening; no test metrics evaluated",
        "run_timestamp": run_stamp,
        "screen_report_path": str(screen_report_path.relative_to(BASE_DIR)),
        "screen_config_path": str(screen_config_path.relative_to(BASE_DIR)),
        "feature_scaler_path": str(feature_scaler_path.relative_to(BASE_DIR)),
        "target_scaler_path": str(target_scaler_path.relative_to(BASE_DIR)),
        "graph_path": str(graph_path.relative_to(BASE_DIR)),
        "decision": decision,
        "selected_variant_for_confirmation": selected_variant,
        "sample_counts": sample_counts,
        "baseline_source": str(BASELINE_REPORT.relative_to(BASE_DIR)),
        "features": rolling.ROLLING_FEATURE_COLS,
        "sequence_length": rolling.SEQ_LEN,
        "chronological_cutoff": str(rolling.CUTOFF_DATE.date()),
        "test_start": str(rolling.TEST_START_DATE.date()),
        "scaler_fit_scope": "training targets/features only",
        "weather_training_medians": median_config,
        "screen": configs,
        "graph": graph_config,
    }
    screen_config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print("\nScreen results saved:", screen_report_path)
    print("Screen configuration saved:", screen_config_path)
    print("Recommendation:", decision)
    if selected_variant:
        print("Candidate for seeds 42/43/44 confirmation:", selected_variant)
    else:
        print(
            "No graph ablation improved both validation R² and MAE over the "
            "seed-42 rolling LSTM. The rolling-feature LSTM remains preferred."
        )


def run_confirmation() -> None:
    screen_configs = sorted(
        MODELS_DIR.glob("solar_graphsage_lstm_fusion_screen_config_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    legacy_screen_config = MODELS_DIR / "solar_graphsage_lstm_fusion_screen_config.json"
    if not screen_configs and legacy_screen_config.exists():
        screen_configs.append(legacy_screen_config)
    if not screen_configs:
        raise FileNotFoundError("Run the validation screen before confirmation.")
    screen_config_path = screen_configs[0]
    screen_config = json.loads(screen_config_path.read_text(encoding="utf-8"))
    selected_variant = screen_config.get("selected_variant_for_confirmation")
    if selected_variant != "residual":
        raise ValueError(
            "The screen did not select residual fusion for confirmation; "
            "do not run confirmation on an unselected model."
        )

    (
        _,
        _,
        _,
        plants,
        _,
        target_scaler,
        _,
        _,
        snapshots,
    ) = prepare_experiment()
    sample_counts = {name: int(values[2].sum()) for name, values in snapshots.items()}
    expected_counts = {
        name: int(screen_config["sample_counts"][name])
        for name in ("train", "validation", "test")
    }
    if sample_counts != expected_counts:
        raise ValueError(f"Confirmation samples differ from screen: {sample_counts}")

    adjacency = np.asarray(screen_config["graph"]["adjacency"], dtype=np.float32)
    train_inputs, train_targets, train_weights, _ = snapshots["train"]
    validation_inputs, validation_targets, validation_weights, _ = snapshots[
        "validation"
    ]
    validation_rows: list[dict[str, Any]] = []
    checkpoints: dict[int, Path] = {}
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    for seed in rolling.SEEDS:
        print(
            f"Confirming residual fusion: K={SCREEN_K}, hidden={SCREEN_HIDDEN_DIM}, "
            f"depth={SCREEN_DEPTH}, seed={seed}",
            flush=True,
        )
        set_seeds(seed)
        tf.keras.backend.clear_session()
        model = build_fusion_model(
            "residual",
            len(plants),
            len(rolling.ROLLING_FEATURE_COLS),
            adjacency,
            SCREEN_HIDDEN_DIM,
            SCREEN_DEPTH,
        )
        callbacks = [
            EarlyStopping(
                monitor="val_loss",
                patience=rolling.PATIENCE,
                restore_best_weights=True,
            ),
            ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=5,
                min_lr=1e-6,
            ),
        ]
        started = time.perf_counter()
        history = model.fit(
            train_inputs,
            train_targets,
            sample_weight=train_weights,
            validation_data=(validation_inputs, validation_targets, validation_weights),
            epochs=rolling.MAX_EPOCHS,
            batch_size=rolling.BATCH_SIZE,
            shuffle=False,
            callbacks=callbacks,
            verbose=0,
        )
        duration = time.perf_counter() - started
        metrics = rolling.evaluate(
            model,
            validation_inputs,
            validation_targets,
            validation_weights,
            target_scaler,
        )
        best_epoch = int(np.argmin(history.history["val_loss"]) + 1)
        checkpoint = MODELS_DIR / (
            f"solar_graphsage_lstm_fusion_residual_confirm_{run_stamp}_seed{seed}.keras"
        )
        model.save(checkpoint)
        checkpoints[seed] = checkpoint
        validation_rows.append(
            {
                "model": "graphsage_residual",
                "variant": "residual",
                "seed": seed,
                "k_neighbors": SCREEN_K,
                "hidden_dimension": SCREEN_HIDDEN_DIM,
                "graphsage_depth": SCREEN_DEPTH,
                "best_epoch": best_epoch,
                "training_duration_seconds": duration,
                "train_sample_count": sample_counts["train"],
                "validation_sample_count": metrics["sample_count"],
                "checkpoint": checkpoint.name,
                **{
                    f"validation_{name}": value
                    for name, value in metrics.items()
                    if name != "sample_count"
                },
                "test_mae": np.nan,
                "test_rmse": np.nan,
                "test_r2": np.nan,
                "test_mape": np.nan,
                "test_sample_count": 0,
            }
        )
        print(
            f"  validation R²={metrics['r2']:.6f}, "
            f"MAE={metrics['mae']:.6f} MU, best epoch={best_epoch}, "
            f"duration={duration:.1f}s",
            flush=True,
        )
        del model

    validation_report = pd.DataFrame(validation_rows)
    baseline_report = pd.read_csv(BASELINE_REPORT)
    baseline_report = baseline_report.loc[
        baseline_report["model"].eq("Solar LSTM (12 features)")
    ].copy()
    baseline_report = baseline_report.rename(
        columns={
            "Validation_MAE": "validation_mae",
            "Validation_RMSE": "validation_rmse",
            "Validation_R2": "validation_r2",
            "Validation_MAPE": "validation_mape",
            "Test_MAE": "test_mae",
            "Test_RMSE": "test_rmse",
            "Test_R2": "test_r2",
            "Test_MAPE": "test_mape",
        }
    )
    baseline_report["model"] = "rolling_lstm_baseline"
    baseline_report["variant"] = "temporal_only"
    validation_candidate = validation_report.set_index("seed")
    validation_baseline = baseline_report.set_index("seed")
    seedwise_improvement = (
        (validation_candidate["validation_r2"] > validation_baseline["validation_r2"])
        & (validation_candidate["validation_mae"] < validation_baseline["validation_mae"])
    )
    candidate_mean_r2 = float(validation_candidate["validation_r2"].mean())
    baseline_mean_r2 = float(validation_baseline["validation_r2"].mean())
    candidate_mean_mae = float(validation_candidate["validation_mae"].mean())
    baseline_mean_mae = float(validation_baseline["validation_mae"].mean())
    validation_confirmed = bool(
        seedwise_improvement.all()
        and candidate_mean_r2 > baseline_mean_r2
        and candidate_mean_mae < baseline_mean_mae
    )

    if validation_confirmed:
        selected_seed = int(validation_candidate["validation_r2"].idxmax())
        test_inputs, test_targets, test_weights, _ = snapshots["test"]
        selected_model = tf.keras.models.load_model(checkpoints[selected_seed])
        test_metrics = rolling.evaluate(
            selected_model, test_inputs, test_targets, test_weights, target_scaler
        )
        selected_rows = validation_report["seed"].eq(selected_seed)
        for metric, value in test_metrics.items():
            validation_report.loc[selected_rows, f"test_{metric}"] = value
        decision = "KEEP residual GraphSAGE + LSTM as preferred candidate"
    else:
        selected_seed = None
        decision = "REVERT to rolling-feature Solar LSTM"

    output_report = pd.concat(
        [
            baseline_report[
                [
                    "model",
                    "variant",
                    "seed",
                    "best_epoch",
                    "training_duration_seconds",
                    "train_sample_count",
                    "validation_sample_count",
                    "test_sample_count",
                    "validation_mae",
                    "validation_rmse",
                    "validation_r2",
                    "validation_mape",
                    "test_mae",
                    "test_rmse",
                    "test_r2",
                    "test_mape",
                ]
            ],
            validation_report,
        ],
        ignore_index=True,
        sort=False,
    )
    confirmation_report_path = REPORTS_DIR / (
        f"solar_graphsage_lstm_fusion_confirmation_{run_stamp}.csv"
    )
    output_report.to_csv(confirmation_report_path, index=False)
    final_config_path = MODELS_DIR / (
        f"solar_graphsage_lstm_fusion_confirmation_config_{run_stamp}.json"
    )
    final_config = {
        "decision": decision,
        "validation_confirmed": validation_confirmed,
        "validation_improved_each_seed": {
            str(seed): bool(value) for seed, value in seedwise_improvement.items()
        },
        "candidate_mean_validation_r2": candidate_mean_r2,
        "baseline_mean_validation_r2": baseline_mean_r2,
        "candidate_mean_validation_mae": candidate_mean_mae,
        "baseline_mean_validation_mae": baseline_mean_mae,
        "selected_checkpoint_seed": selected_seed,
        "candidate_test_evaluated": validation_confirmed,
        "candidate_test_metrics": test_metrics if validation_confirmed else None,
        "sample_counts": sample_counts,
        "checkpoint_paths": {str(seed): str(path.relative_to(BASE_DIR)) for seed, path in checkpoints.items()},
    }
    final_config_path.write_text(json.dumps(final_config, indent=2), encoding="utf-8")
    print("\nThree-seed validation confirmation")
    print(f"  rolling LSTM mean val R² / MAE: {baseline_mean_r2:.6f} / {baseline_mean_mae:.6f}")
    print(f"  residual graph mean val R² / MAE: {candidate_mean_r2:.6f} / {candidate_mean_mae:.6f}")
    print(f"  improvement in each seed: {bool(seedwise_improvement.all())}")
    print("  decision:", decision)
    if validation_confirmed:
        print(
            "  selected graph test metrics (one final evaluation): "
            f"R²={test_metrics['r2']:.6f}, MAE={test_metrics['mae']:.6f} MU, "
            f"RMSE={test_metrics['rmse']:.6f} MU, MAPE={test_metrics['mape']:.4f}%"
        )
    else:
        print("  graph test set was not evaluated because validation did not confirm the gain.")
    print("  confirmation report:", confirmation_report_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("screen", "confirm"),
        default="screen",
        help="Run the single-seed validation ablation or confirm its selected candidate.",
    )
    args = parser.parse_args()
    if args.stage == "screen":
        run_screen()
    else:
        run_confirmation()


if __name__ == "__main__":
    main()

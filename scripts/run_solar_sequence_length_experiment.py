from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.models import Sequential

import run_solar_lstm_attention_experiment as pipeline


BASE_DIR = pipeline.BASE_DIR
MODELS_DIR = pipeline.MODELS_DIR
REPORTS_DIR = pipeline.REPORTS_DIR
BASELINE_MODEL_PATH = MODELS_DIR / "solar_lstm_rolling_7.keras"
BASELINE_REPORT_PATH = REPORTS_DIR / "solar_lstm_rolling_generation_experiment.csv"
REPORT_PATH = REPORTS_DIR / "solar_sequence_length_comparison.csv"
MANIFEST_PATH = MODELS_DIR / "solar_sequence_length_comparison_manifest.json"
SEQUENCE_LENGTHS = (14, 21)
ALL_SEQUENCE_LENGTHS = (7, *SEQUENCE_LENGTHS)
REFERENCE_METRICS = {
    "Validation_MAE": 0.14669904112815857,
    "Validation_RMSE": 0.24318671982698142,
    "Validation_R2": 0.8526325225830078,
    "Test_MAE": 0.14029693603515625,
    "Test_RMSE": 0.23404275073627287,
    "Test_R2": 0.8674271106719971,
}
BASELINE_FEATURE_SET = "With Rolling_Generation_7 (12 features)"


def artifact_paths(sequence_length: int) -> dict[str, Path]:
    if sequence_length == 7:
        return {
            "checkpoint": BASELINE_MODEL_PATH,
            "feature_scaler": (
                MODELS_DIR / "solar_sequence_length_7_feature_scaler.joblib"
            ),
            "target_scaler": (
                MODELS_DIR / "solar_sequence_length_7_target_scaler.joblib"
            ),
        }
    prefix = f"solar_lstm_sequence_{sequence_length}"
    return {
        "checkpoint": MODELS_DIR / f"{prefix}.keras",
        "feature_scaler": MODELS_DIR / f"{prefix}_feature_scaler.joblib",
        "target_scaler": MODELS_DIR / f"{prefix}_target_scaler.joblib",
    }


SELECTED_ARTIFACTS = {
    "checkpoint": MODELS_DIR / "solar_lstm_sequence_selected.keras",
    "feature_scaler": MODELS_DIR / "solar_lstm_sequence_selected_feature_scaler.joblib",
    "target_scaler": MODELS_DIR / "solar_lstm_sequence_selected_target_scaler.joblib",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wind_artifact_hashes() -> dict[str, str]:
    paths = [
        path
        for directory in (MODELS_DIR, REPORTS_DIR)
        for path in directory.iterdir()
        if path.is_file() and "wind" in path.name.lower()
    ]
    return {
        str(path.relative_to(BASE_DIR)): sha256(path)
        for path in sorted(paths)
    }


def ensure_output_paths_are_new() -> list[Path]:
    paths = [MANIFEST_PATH, REPORT_PATH, *SELECTED_ARTIFACTS.values()]
    for sequence_length in ALL_SEQUENCE_LENGTHS:
        paths.extend(
            path
            for name, path in artifact_paths(sequence_length).items()
            if not (sequence_length == 7 and name == "checkpoint")
        )
    collisions = [str(path) for path in paths if path.exists()]
    if collisions:
        raise FileExistsError(
            "Refusing to overwrite sequence experiment artifacts: "
            + ", ".join(collisions)
        )
    return paths


def read_recorded_baseline() -> dict[str, float]:
    if not BASELINE_REPORT_PATH.is_file():
        raise FileNotFoundError(f"Baseline report not found: {BASELINE_REPORT_PATH}")
    report = pd.read_csv(BASELINE_REPORT_PATH)
    matches = report.loc[report["Feature_Set"].eq(BASELINE_FEATURE_SET)]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {BASELINE_FEATURE_SET!r} row in "
            f"{BASELINE_REPORT_PATH}; found {len(matches)}."
        )
    row = matches.iloc[0]
    return {
        "Validation_MAE": float(row["Validation_MAE"]),
        "Validation_RMSE": float(row["Validation_RMSE"]),
        "Validation_R2": float(row["Validation_R2"]),
        "Test_MAE": float(row["Test_MAE"]),
        "Test_RMSE": float(row["Test_RMSE"]),
        "Test_R2": float(row["Test_R2"]),
    }


def assert_metrics_match(
    actual: dict[str, float], expected: dict[str, float], context: str
) -> None:
    mismatches = {
        name: (actual[name], expected[name])
        for name in expected
        if not np.isclose(actual[name], expected[name], rtol=1e-6, atol=1e-8)
    }
    if mismatches:
        raise RuntimeError(f"{context} does not match: {mismatches}")


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
        optimizer=tf.keras.optimizers.Nadam(learning_rate=pipeline.LEARNING_RATE),
        loss="mse",
    )
    return model


def create_sequences_for_window(
    plant_split_info: list[tuple[str, pd.DataFrame, int, int]],
    feature_scaler: Any,
    target_scaler: Any,
    sequence_length: int,
) -> tuple[
    tuple[tuple[np.ndarray, np.ndarray], ...],
    list[list[pd.Timestamp]],
]:
    sequences: list[list[np.ndarray]] = [[], [], []]
    targets: list[list[float]] = [[], [], []]
    target_dates: list[list[pd.Timestamp]] = [[], [], []]

    for _, group, val_start_idx, test_start_idx in plant_split_info:
        scaled_features = feature_scaler.transform(group[pipeline.FEATURE_COLS])
        scaled_targets = target_scaler.transform(
            group[[pipeline.TARGET_COL]]
        ).ravel()
        dates = group["Date"].tolist()

        for target_idx in range(sequence_length, len(group)):
            if target_idx < val_start_idx:
                split_idx = 0
            elif target_idx < test_start_idx:
                split_idx = 1
            else:
                split_idx = 2

            # End the input strictly before the row whose target is predicted.
            sequences[split_idx].append(
                scaled_features[target_idx - sequence_length : target_idx]
            )
            targets[split_idx].append(float(scaled_targets[target_idx]))
            target_dates[split_idx].append(pd.Timestamp(dates[target_idx]))

    result = tuple(
        (np.asarray(x, dtype=np.float32), np.asarray(y, dtype=np.float32))
        for x, y in zip(sequences, targets)
    )
    for split_name, (x_values, y_values) in zip(
        ("training", "validation", "test"), result
    ):
        if x_values.size == 0 or y_values.size == 0:
            raise ValueError(
                f"The {split_name} split has no sequences for window "
                f"{sequence_length}."
            )
        if x_values.shape[1:] != (sequence_length, len(pipeline.FEATURE_COLS)):
            raise RuntimeError(
                f"Unexpected {split_name} input shape for window {sequence_length}: "
                f"{x_values.shape}"
            )
    return result, target_dates


def validate_split_targets(
    target_dates: dict[int, list[list[pd.Timestamp]]],
) -> None:
    for split_index, split_name in ((1, "validation"), (2, "test")):
        expected = target_dates[7][split_index]
        for sequence_length in (14, 21):
            if target_dates[sequence_length][split_index] != expected:
                raise RuntimeError(
                    f"{split_name} target dates changed for sequence length "
                    f"{sequence_length}; refusing an unfair comparison."
                )


def metric_record(
    metrics: dict[str, float], prefix: str
) -> dict[str, float]:
    return {f"{prefix}_{name}": value for name, value in metrics.items()}


def main() -> None:
    if not pipeline.DATA_PATH.is_file():
        raise FileNotFoundError(f"Dataset not found: {pipeline.DATA_PATH}")
    if not BASELINE_MODEL_PATH.is_file():
        raise FileNotFoundError(f"Baseline checkpoint not found: {BASELINE_MODEL_PATH}")
    output_paths = ensure_output_paths_are_new()
    recorded_baseline = read_recorded_baseline()
    original_baseline_hash = sha256(BASELINE_MODEL_PATH)
    wind_hashes_before = wind_artifact_hashes()
    pipeline.set_seeds(pipeline.SEED)

    solar_df = pipeline.load_and_clean_solar_data(pipeline.DATA_PATH)
    train_df, plant_split_info, plant_boundaries = (
        pipeline.split_time_based_per_plant(solar_df)
    )
    feature_scaler, target_scaler = pipeline.fit_scalers(train_df)
    sequences_by_length: dict[
        int, tuple[tuple[tuple[np.ndarray, np.ndarray], ...], list[list[pd.Timestamp]]]
    ] = {}
    target_dates_by_length: dict[int, list[list[pd.Timestamp]]] = {}

    for sequence_length in ALL_SEQUENCE_LENGTHS:
        sequences, dates = create_sequences_for_window(
            plant_split_info,
            feature_scaler,
            target_scaler,
            sequence_length,
        )
        sequences_by_length[sequence_length] = (sequences, dates)
        target_dates_by_length[sequence_length] = dates
    validate_split_targets(target_dates_by_length)

    print("Verified: validation and test target dates match for 7, 14, and 21.")
    print(
        "Window lengths reduce early training targets only; per-plant split "
        "boundaries and scaler-fit rows remain fixed."
    )
    print("Training candidates: 14 and 21 only.")

    baseline_model = tf.keras.models.load_model(
        BASELINE_MODEL_PATH, compile=False
    )
    (_, _), (x_val_7, y_val_7), (_, _) = (
        sequences_by_length[7][0]
    )
    baseline_val = pipeline.calculate_metrics(
        baseline_model, x_val_7, y_val_7, target_scaler
    )
    baseline_metrics = metric_record(baseline_val, "Validation")
    assert_metrics_match(
        baseline_metrics,
        {
            key: recorded_baseline[key]
            for key in ("Validation_MAE", "Validation_RMSE", "Validation_R2")
        },
        "Existing seven-day baseline checkpoint validation",
    )

    results: dict[int, dict[str, Any]] = {
        7: {
            "model": baseline_model,
            "validation": baseline_val,
            "test": None,
            "best_epoch": None,
        }
    }
    for sequence_length in SEQUENCE_LENGTHS:
        pipeline.set_seeds(pipeline.SEED)
        (x_train, y_train), (x_val, y_val), _ = sequences_by_length[sequence_length][0]
        model = build_solar_lstm((sequence_length, len(pipeline.FEATURE_COLS)))
        callbacks = [
            EarlyStopping(
                monitor="val_loss",
                patience=pipeline.EARLY_STOPPING_PATIENCE,
                restore_best_weights=True,
            ),
            ReduceLROnPlateau(
                monitor="val_loss",
                factor=pipeline.REDUCE_LR_FACTOR,
                patience=pipeline.REDUCE_LR_PATIENCE,
                min_lr=pipeline.MIN_LEARNING_RATE,
            ),
        ]
        print(
            f"\nTraining sequence length {sequence_length}: "
            f"{len(x_train)} train, {len(x_val)} validation sequences."
        )
        history = model.fit(
            x_train,
            y_train,
            validation_data=(x_val, y_val),
            epochs=pipeline.MAX_EPOCHS,
            batch_size=pipeline.BATCH_SIZE,
            shuffle=False,
            callbacks=callbacks,
            verbose=2,
        )
        results[sequence_length] = {
            "model": model,
            "validation": pipeline.calculate_metrics(
                model, x_val, y_val, target_scaler
            ),
            "test": None,
            "best_epoch": int(np.argmin(history.history["val_loss"]) + 1),
            "training_samples": len(x_train),
        }

    # Decide the winner using validation R2 before evaluating any test split.
    selected_length = max(
        ALL_SEQUENCE_LENGTHS,
        key=lambda length: results[length]["validation"]["R2"],
    )
    selected_model_name = f"Solar LSTM (sequence length {selected_length})"

    for sequence_length in ALL_SEQUENCE_LENGTHS:
        _, _, (x_test, y_test) = sequences_by_length[sequence_length][0]
        results[sequence_length]["test"] = pipeline.calculate_metrics(
            results[sequence_length]["model"], x_test, y_test, target_scaler
        )
    baseline_test = results[7]["test"]
    if baseline_test is None:
        raise RuntimeError("Baseline test metrics were not calculated.")
    assert_metrics_match(
        {
            **metric_record(baseline_val, "Validation"),
            **metric_record(baseline_test, "Test"),
        },
        recorded_baseline,
        "Existing seven-day baseline checkpoint using reconstructed train-only scalers",
    )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(feature_scaler, artifact_paths(7)["feature_scaler"])
    joblib.dump(target_scaler, artifact_paths(7)["target_scaler"])
    for sequence_length in SEQUENCE_LENGTHS:
        paths = artifact_paths(sequence_length)
        results[sequence_length]["model"].save(paths["checkpoint"])
        joblib.dump(feature_scaler, paths["feature_scaler"])
        joblib.dump(target_scaler, paths["target_scaler"])

    selected_model_path = SELECTED_ARTIFACTS["checkpoint"]
    if selected_length == 7:
        shutil.copy2(BASELINE_MODEL_PATH, selected_model_path)
    else:
        shutil.copy2(
            artifact_paths(selected_length)["checkpoint"], selected_model_path
        )
    shutil.copy2(
        artifact_paths(selected_length)["feature_scaler"],
        SELECTED_ARTIFACTS["feature_scaler"],
    )
    shutil.copy2(
        artifact_paths(selected_length)["target_scaler"],
        SELECTED_ARTIFACTS["target_scaler"],
    )
    selected_feature_scaler = joblib.load(SELECTED_ARTIFACTS["feature_scaler"])
    selected_target_scaler = joblib.load(SELECTED_ARTIFACTS["target_scaler"])
    for scaler_name, actual, expected in (
        ("feature", selected_feature_scaler, feature_scaler),
        ("target", selected_target_scaler, target_scaler),
    ):
        if not (
            np.array_equal(actual.mean_, expected.mean_)
            and np.array_equal(actual.scale_, expected.scale_)
        ):
            raise RuntimeError(f"Selected {scaler_name} scaler failed verification.")

    selected_model = tf.keras.models.load_model(
        selected_model_path, compile=False
    )
    selected_sequences, _ = sequences_by_length[selected_length]
    (_, _), (x_selected_val, y_selected_val), (x_selected_test, y_selected_test) = (
        selected_sequences
    )
    selected_val_reloaded = pipeline.calculate_metrics(
        selected_model,
        x_selected_val,
        y_selected_val,
        selected_target_scaler,
    )
    selected_test_reloaded = pipeline.calculate_metrics(
        selected_model,
        x_selected_test,
        y_selected_test,
        selected_target_scaler,
    )
    assert_metrics_match(
        selected_val_reloaded,
        results[selected_length]["validation"],
        "Selected checkpoint validation metrics after reload",
    )
    if results[selected_length]["test"] is None:
        raise RuntimeError("Selected model test metrics were not calculated.")
    assert_metrics_match(
        selected_test_reloaded,
        results[selected_length]["test"],
        "Selected checkpoint test metrics after reload",
    )

    if sha256(BASELINE_MODEL_PATH) != original_baseline_hash:
        raise RuntimeError("The original Solar baseline checkpoint changed.")
    if wind_artifact_hashes() != wind_hashes_before:
        raise RuntimeError("A Wind artifact changed during the experiment.")

    split_date_ranges = {
        split_name: {
            "start": min(target_dates_by_length[7][split_idx]).date().isoformat(),
            "end": max(target_dates_by_length[7][split_idx]).date().isoformat(),
        }
        for split_idx, split_name in enumerate(("train", "validation", "test"))
    }
    split_metadata = {
        "training_validation_cutoff_exclusive": "2026-01-01",
        "validation_fraction_per_plant": pipeline.VALIDATION_FRACTION,
        "per_plant_boundaries": plant_boundaries,
        "target_date_ranges": split_date_ranges,
        "validation_target_dates_identical_for_all_windows": True,
        "test_target_dates_identical_for_all_windows": True,
        "sample_counts_by_window": {
            str(length): {
                "train": len(sequences_by_length[length][0][0][0]),
                "validation": len(sequences_by_length[length][0][1][0]),
                "test": len(sequences_by_length[length][0][2][0]),
            }
            for length in ALL_SEQUENCE_LENGTHS
        },
    }
    feature_scaler_hash = sha256(artifact_paths(7)["feature_scaler"])
    target_scaler_hash = sha256(artifact_paths(7)["target_scaler"])
    rows = []
    for length in ALL_SEQUENCE_LENGTHS:
        paths = artifact_paths(length)
        validation = results[length]["validation"]
        test = results[length]["test"]
        if test is None:
            raise RuntimeError(f"Test metrics missing for sequence length {length}.")
        rows.append(
            {
                "Model": f"Solar LSTM (sequence length {length})",
                "Sequence_Length": length,
                "Is_Selected": length == selected_length,
                "Validation_MAE": validation["MAE"],
                "Validation_RMSE": validation["RMSE"],
                "Validation_R2": validation["R2"],
                "Test_MAE": test["MAE"],
                "Test_RMSE": test["RMSE"],
                "Test_R2": test["R2"],
                "Best_Epoch": results[length]["best_epoch"],
                "Train_Samples": split_metadata["sample_counts_by_window"][str(length)][
                    "train"
                ],
                "Validation_Samples": split_metadata["sample_counts_by_window"][
                    str(length)
                ]["validation"],
                "Test_Samples": split_metadata["sample_counts_by_window"][str(length)][
                    "test"
                ],
                "Checkpoint_Path": str(paths["checkpoint"].resolve()),
                "Feature_Scaler_Path": str(paths["feature_scaler"].resolve()),
                "Target_Scaler_Path": str(paths["target_scaler"].resolve()),
                "Selected_Checkpoint_Path": str(selected_model_path.resolve()),
            }
        )

    manifest: dict[str, Any] = {
        "experiment": "Controlled Solar LSTM sequence-length comparison",
        "data_path": str(pipeline.DATA_PATH.resolve()),
        "target": pipeline.TARGET_COL,
        "feature_columns_in_order": pipeline.FEATURE_COLS,
        "tested_sequence_lengths": list(ALL_SEQUENCE_LENGTHS),
        "model_architecture": (
            "Input(window, 12) -> LSTM(64, return_sequences=True) -> Dropout(0.3) "
            "-> LSTM(32) -> Dropout(0.3) -> Dense(16, relu) -> Dense(1)"
        ),
        "training_settings": {
            "seed": pipeline.SEED,
            "optimizer": pipeline.OPTIMIZER,
            "learning_rate": pipeline.LEARNING_RATE,
            "loss": "mse",
            "batch_size": pipeline.BATCH_SIZE,
            "maximum_epochs": pipeline.MAX_EPOCHS,
            "shuffle": False,
            "early_stopping": {
                "monitor": "val_loss",
                "patience": pipeline.EARLY_STOPPING_PATIENCE,
                "restore_best_weights": True,
            },
            "reduce_lr_on_plateau": {
                "monitor": "val_loss",
                "factor": pipeline.REDUCE_LR_FACTOR,
                "patience": pipeline.REDUCE_LR_PATIENCE,
                "min_lr": pipeline.MIN_LEARNING_RATE,
            },
        },
        "preprocessing": {
            "source": "Reused from run_solar_lstm_attention_experiment.py",
            "generation_clipping": "DailyGeneration_MU clipped at lower bound 0.0",
            "lagged_generation": "Per-plant shift(1)",
            "rolling_generation_7": (
                "Per-plant shift(1).rolling(7, min_periods=7).mean()"
            ),
            "scaler_fit_rows": len(train_df),
            "scaler_fit_rule": "Feature and target StandardScaler fit on unchanged training rows only.",
            "scaler_sha256": {
                "feature": feature_scaler_hash,
                "target": target_scaler_hash,
            },
        },
        "split": split_metadata,
        "sequence_construction": {
            "rule": "For target at row t, input features are rows [t-sequence_length, t); target row is excluded from input.",
            "generation_features_use_only_prior_generation": True,
            "validation_and_test_target_dates_preserved": True,
            "training_sample_effect": (
                "Increasing window length removes initial training targets that do "
                "not have enough preceding history; it does not move split boundaries."
            ),
        },
        "baseline_reference": {
            "checkpoint": str(BASELINE_MODEL_PATH.resolve()),
            "checkpoint_sha256_before_run": original_baseline_hash,
            "recorded_metrics": recorded_baseline,
            "checkpoint_re_evaluated_with_train_only_scalers": baseline_metrics,
        },
        "metrics_by_sequence_length": {
            str(length): {
                "validation": results[length]["validation"],
                "test": results[length]["test"],
            }
            for length in ALL_SEQUENCE_LENGTHS
        },
        "selection": {
            "primary_metric": "validation R2",
            "selected_sequence_length": selected_length,
            "selected_model": f"Solar LSTM (sequence length {selected_length})",
            "selected_checkpoint_validation_metrics_after_reload": selected_val_reloaded,
            "selected_checkpoint_test_metrics_after_reload": selected_test_reloaded,
            "test_metrics_not_used_for_selection": True,
        },
        "artifacts": {
            "per_sequence_length": {
                str(length): {
                    key: str(path.resolve())
                    for key, path in artifact_paths(length).items()
                }
                for length in ALL_SEQUENCE_LENGTHS
            },
            "selected_model": {
                key: str(path.resolve())
                for key, path in SELECTED_ARTIFACTS.items()
            },
            "report": str(REPORT_PATH.resolve()),
            "manifest": str(MANIFEST_PATH.resolve()),
        },
        "wind_artifact_sha256_before_run": wind_hashes_before,
    }

    pd.DataFrame(rows).to_csv(REPORT_PATH, index=False)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nSolar sequence-length comparison")
    print(
        f"{'Window':>6} {'Val MAE':>10} {'Val RMSE':>10} {'Val R2':>10} "
        f"{'Test MAE':>10} {'Test RMSE':>10} {'Test R2':>10} {'Selected':>9}"
    )
    for row in rows:
        print(
            f"{row['Sequence_Length']:6d} {row['Validation_MAE']:10.6f} "
            f"{row['Validation_RMSE']:10.6f} {row['Validation_R2']:10.6f} "
            f"{row['Test_MAE']:10.6f} {row['Test_RMSE']:10.6f} "
            f"{row['Test_R2']:10.6f} {str(row['Is_Selected']):>9}"
        )
    print(f"Selected by validation R2: {selected_model_name}")
    print(f"Selected checkpoint: {selected_model_path}")
    print(f"Report: {REPORT_PATH}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Verified {len(output_paths)} output paths were new before training.")
    print("Original Solar checkpoint and Wind artifacts are unchanged.")


if __name__ == "__main__":
    main()

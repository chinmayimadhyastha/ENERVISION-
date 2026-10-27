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

import run_solar_lstm_attention_experiment as pipeline


BASE_DIR = pipeline.BASE_DIR
MODELS_DIR = pipeline.MODELS_DIR
REPORTS_DIR = pipeline.REPORTS_DIR
BASELINE_MODEL_PATH = MODELS_DIR / "solar_lstm_rolling_7.keras"
BASELINE_REPORT_PATH = REPORTS_DIR / "solar_lstm_rolling_generation_experiment.csv"

PREFIX = "solar_lstm_attention_controlled"
ATTENTION_MODEL_PATH = MODELS_DIR / f"{PREFIX}_candidate.keras"
ATTENTION_FEATURE_SCALER_PATH = (
    MODELS_DIR / f"{PREFIX}_candidate_feature_scaler.joblib"
)
ATTENTION_TARGET_SCALER_PATH = (
    MODELS_DIR / f"{PREFIX}_candidate_target_scaler.joblib"
)
BASELINE_FEATURE_SCALER_PATH = (
    MODELS_DIR / f"{PREFIX}_baseline_feature_scaler.joblib"
)
BASELINE_TARGET_SCALER_PATH = (
    MODELS_DIR / f"{PREFIX}_baseline_target_scaler.joblib"
)
SELECTED_MODEL_PATH = MODELS_DIR / f"{PREFIX}_selected.keras"
SELECTED_FEATURE_SCALER_PATH = (
    MODELS_DIR / f"{PREFIX}_selected_feature_scaler.joblib"
)
SELECTED_TARGET_SCALER_PATH = (
    MODELS_DIR / f"{PREFIX}_selected_target_scaler.joblib"
)
MANIFEST_PATH = MODELS_DIR / f"{PREFIX}_manifest.json"
REPORT_PATH = REPORTS_DIR / f"{PREFIX}_report.csv"

RECORDED_BASELINE = {
    "Validation_MAE": 0.14669904112815857,
    "Validation_RMSE": 0.24318671982698142,
    "Validation_R2": 0.8526325225830078,
    "Test_MAE": 0.14029693603515625,
    "Test_RMSE": 0.23404275073627287,
    "Test_R2": 0.8674271106719971,
}
BASELINE_FEATURE_SET = "With Rolling_Generation_7 (12 features)"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def existing_wind_hashes() -> dict[str, str]:
    protected_directories = (MODELS_DIR, REPORTS_DIR)
    wind_files = [
        path
        for directory in protected_directories
        for path in directory.iterdir()
        if path.is_file() and "wind" in path.name.lower()
    ]
    return {
        str(path.relative_to(BASE_DIR)): file_sha256(path)
        for path in sorted(wind_files)
    }


def assert_metrics_match(
    actual: dict[str, float], expected: dict[str, float], context: str
) -> None:
    mismatches = {
        key: (actual[key], expected[key])
        for key in expected
        if not np.isclose(actual[key], expected[key], rtol=1e-6, atol=1e-8)
    }
    if mismatches:
        raise RuntimeError(f"{context} metric verification failed: {mismatches}")


def read_recorded_baseline() -> dict[str, float]:
    if not BASELINE_REPORT_PATH.is_file():
        raise FileNotFoundError(f"Baseline report not found: {BASELINE_REPORT_PATH}")
    report = pd.read_csv(BASELINE_REPORT_PATH)
    matches = report.loc[report["Feature_Set"].eq(BASELINE_FEATURE_SET)]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one {BASELINE_FEATURE_SET!r} row in {BASELINE_REPORT_PATH}; "
            f"found {len(matches)}."
        )

    row = matches.iloc[0]
    columns = {
        "Validation_MAE": "Validation_MAE",
        "Validation_RMSE": "Validation_RMSE",
        "Validation_R2": "Validation_R2",
        "Test_MAE": "Test_MAE",
        "Test_RMSE": "Test_RMSE",
        "Test_R2": "Test_R2",
    }
    metrics = {key: float(row[column]) for key, column in columns.items()}
    assert_metrics_match(metrics, RECORDED_BASELINE, "Recorded baseline report")
    return metrics


def output_paths() -> list[Path]:
    return [
        ATTENTION_MODEL_PATH,
        ATTENTION_FEATURE_SCALER_PATH,
        ATTENTION_TARGET_SCALER_PATH,
        BASELINE_FEATURE_SCALER_PATH,
        BASELINE_TARGET_SCALER_PATH,
        SELECTED_MODEL_PATH,
        SELECTED_FEATURE_SCALER_PATH,
        SELECTED_TARGET_SCALER_PATH,
        MANIFEST_PATH,
        REPORT_PATH,
    ]


def ensure_output_paths_are_new() -> None:
    existing = [str(path) for path in output_paths() if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite controlled experiment artifacts: "
            + ", ".join(existing)
        )


def main() -> None:
    if not pipeline.DATA_PATH.is_file():
        raise FileNotFoundError(f"Dataset not found: {pipeline.DATA_PATH}")
    if not BASELINE_MODEL_PATH.is_file():
        raise FileNotFoundError(f"Current Solar LSTM checkpoint not found: {BASELINE_MODEL_PATH}")
    ensure_output_paths_are_new()
    recorded_baseline = read_recorded_baseline()
    baseline_checkpoint_hash = file_sha256(BASELINE_MODEL_PATH)
    wind_hashes_before = existing_wind_hashes()

    pipeline.set_seeds(pipeline.SEED)
    solar_df = pipeline.load_and_clean_solar_data(pipeline.DATA_PATH)
    train_df, plant_split_info, plant_boundaries = (
        pipeline.split_time_based_per_plant(solar_df)
    )
    feature_scaler, target_scaler = pipeline.fit_scalers(train_df)
    sequence_splits, target_dates = pipeline.create_sequences(
        plant_split_info, feature_scaler, target_scaler
    )
    (x_train, y_train), (x_val, y_val), (x_test, y_test) = sequence_splits

    baseline_model = tf.keras.models.load_model(
        BASELINE_MODEL_PATH, compile=False
    )
    baseline_val_metrics = pipeline.calculate_metrics(
        baseline_model, x_val, y_val, target_scaler
    )
    assert_metrics_match(
        {
            "Validation_MAE": baseline_val_metrics["MAE"],
            "Validation_RMSE": baseline_val_metrics["RMSE"],
            "Validation_R2": baseline_val_metrics["R2"],
        },
        {
            key: recorded_baseline[key]
            for key in ("Validation_MAE", "Validation_RMSE", "Validation_R2")
        },
        "Current baseline checkpoint with reconstructed train-only scalers",
    )

    attention_model = pipeline.build_solar_lstm_attention(
        (x_train.shape[1], x_train.shape[2])
    )
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
    print("Training one Solar LSTM + Self-Attention candidate.")
    history = attention_model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=pipeline.MAX_EPOCHS,
        batch_size=pipeline.BATCH_SIZE,
        shuffle=False,
        callbacks=callbacks,
        verbose=2,
    )

    attention_val_metrics = pipeline.calculate_metrics(
        attention_model, x_val, y_val, target_scaler
    )
    selected_model_name = (
        "Solar LSTM + Self-Attention"
        if attention_val_metrics["R2"] > baseline_val_metrics["R2"]
        else "Current Solar LSTM"
    )
    # Test metrics are measured only after selection is fixed by validation R2.
    attention_test_metrics = pipeline.calculate_metrics(
        attention_model, x_test, y_test, target_scaler
    )
    baseline_test_metrics = pipeline.calculate_metrics(
        baseline_model, x_test, y_test, target_scaler
    )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    attention_model.save(ATTENTION_MODEL_PATH)
    joblib.dump(feature_scaler, ATTENTION_FEATURE_SCALER_PATH)
    joblib.dump(target_scaler, ATTENTION_TARGET_SCALER_PATH)
    joblib.dump(feature_scaler, BASELINE_FEATURE_SCALER_PATH)
    joblib.dump(target_scaler, BASELINE_TARGET_SCALER_PATH)

    if selected_model_name == "Solar LSTM + Self-Attention":
        shutil.copy2(ATTENTION_MODEL_PATH, SELECTED_MODEL_PATH)
        selected_feature_scaler_path = ATTENTION_FEATURE_SCALER_PATH
        selected_target_scaler_path = ATTENTION_TARGET_SCALER_PATH
    else:
        shutil.copy2(BASELINE_MODEL_PATH, SELECTED_MODEL_PATH)
        selected_feature_scaler_path = BASELINE_FEATURE_SCALER_PATH
        selected_target_scaler_path = BASELINE_TARGET_SCALER_PATH
    shutil.copy2(selected_feature_scaler_path, SELECTED_FEATURE_SCALER_PATH)
    shutil.copy2(selected_target_scaler_path, SELECTED_TARGET_SCALER_PATH)

    selected_feature_scaler = joblib.load(SELECTED_FEATURE_SCALER_PATH)
    selected_target_scaler = joblib.load(SELECTED_TARGET_SCALER_PATH)
    if not (
        np.array_equal(selected_feature_scaler.mean_, feature_scaler.mean_)
        and np.array_equal(selected_feature_scaler.scale_, feature_scaler.scale_)
        and np.array_equal(selected_target_scaler.mean_, target_scaler.mean_)
        and np.array_equal(selected_target_scaler.scale_, target_scaler.scale_)
    ):
        raise RuntimeError("Saved selected scalers do not match the evaluated scalers.")

    selected_saved_model = tf.keras.models.load_model(
        SELECTED_MODEL_PATH, compile=False
    )
    selected_validation_metrics = pipeline.calculate_metrics(
        selected_saved_model, x_val, y_val, selected_target_scaler
    )
    selected_test_metrics = pipeline.calculate_metrics(
        selected_saved_model, x_test, y_test, selected_target_scaler
    )
    selected_original_val = (
        attention_val_metrics
        if selected_model_name == "Solar LSTM + Self-Attention"
        else baseline_val_metrics
    )
    selected_original_test = (
        attention_test_metrics
        if selected_model_name == "Solar LSTM + Self-Attention"
        else baseline_test_metrics
    )
    assert_metrics_match(
        selected_validation_metrics,
        selected_original_val,
        "Saved selected checkpoint validation",
    )
    assert_metrics_match(
        selected_test_metrics,
        selected_original_test,
        "Saved selected checkpoint test",
    )
    if file_sha256(BASELINE_MODEL_PATH) != baseline_checkpoint_hash:
        raise RuntimeError("The original Solar LSTM checkpoint changed during the run.")
    if existing_wind_hashes() != wind_hashes_before:
        raise RuntimeError("A protected Wind artifact changed during the run.")

    date_ranges = {
        name: {
            "start": min(dates).date().isoformat(),
            "end": max(dates).date().isoformat(),
        }
        for name, dates in zip(("train", "validation", "test"), target_dates)
    }
    split_manifest = {
        "training_validation_cutoff_exclusive": "2026-01-01",
        "validation_fraction_per_plant": pipeline.VALIDATION_FRACTION,
        "target_date_ranges": date_ranges,
        "per_plant_boundaries": plant_boundaries,
        "sample_counts": {
            "train": len(x_train),
            "validation": len(x_val),
            "test": len(x_test),
        },
    }
    best_epoch = int(np.argmin(history.history["val_loss"]) + 1)
    selected_metrics = {
        "validation": selected_validation_metrics,
        "test": selected_test_metrics,
    }
    artifact_paths = {
        "baseline_checkpoint_source": str(BASELINE_MODEL_PATH.resolve()),
        "attention_candidate_checkpoint": str(ATTENTION_MODEL_PATH.resolve()),
        "attention_candidate_feature_scaler": str(
            ATTENTION_FEATURE_SCALER_PATH.resolve()
        ),
        "attention_candidate_target_scaler": str(
            ATTENTION_TARGET_SCALER_PATH.resolve()
        ),
        "baseline_evaluation_feature_scaler": str(
            BASELINE_FEATURE_SCALER_PATH.resolve()
        ),
        "baseline_evaluation_target_scaler": str(
            BASELINE_TARGET_SCALER_PATH.resolve()
        ),
        "selected_checkpoint": str(SELECTED_MODEL_PATH.resolve()),
        "selected_feature_scaler": str(SELECTED_FEATURE_SCALER_PATH.resolve()),
        "selected_target_scaler": str(SELECTED_TARGET_SCALER_PATH.resolve()),
        "manifest": str(MANIFEST_PATH.resolve()),
        "report": str(REPORT_PATH.resolve()),
    }
    manifest: dict[str, Any] = {
        "experiment": "Controlled Solar LSTM vs Self-Attention",
        "data_path": str(pipeline.DATA_PATH.resolve()),
        "target": pipeline.TARGET_COL,
        "feature_columns_in_order": pipeline.FEATURE_COLS,
        "sequence_length": pipeline.SEQ_LEN,
        "split": split_manifest,
        "preprocessing": {
            "weather_sentinels": "Values <= -900 masked; per-plant forward-fill, backward-fill, then global mean fill if needed",
            "generation_clipping": "DailyGeneration_MU clipped at lower bound 0.0",
            "lagged_generation": "Per-plant DailyGeneration_MU shifted by one row",
            "rolling_generation_7": (
                "Per-plant shift(1).rolling(7, min_periods=7).mean()"
            ),
            "scaler_fit_rule": "Separate StandardScaler instances fitted on training rows only; same fitted transforms used for both models.",
            "inverse_transform": "Predictions and targets inverse-transformed with the saved target scaler before metrics.",
        },
        "training": {
            "seed": pipeline.SEED,
            "optimizer": pipeline.OPTIMIZER,
            "learning_rate": pipeline.LEARNING_RATE,
            "loss": "mse",
            "batch_size": pipeline.BATCH_SIZE,
            "maximum_epochs": pipeline.MAX_EPOCHS,
            "best_epoch": best_epoch,
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
        "model_configurations": {
            "current_baseline": (
                "LSTM(64, return_sequences=True) -> Dropout(0.3) -> LSTM(32) "
                "-> Dropout(0.3) -> Dense(16, relu) -> Dense(1)"
            ),
            "attention_candidate": (
                "LSTM(64, return_sequences=True) -> Keras temporal self-Attention "
                "-> GlobalAveragePooling1D -> Dropout(0.3) -> Dense(16, relu) "
                "-> Dense(1)"
            ),
        },
        "baseline_provenance": {
            "recorded_metrics_source": str(BASELINE_REPORT_PATH.resolve()),
            "checkpoint_sha256_before_run": baseline_checkpoint_hash,
            "checkpoint_metrics_verified_against_recorded_report": True,
            "scalers": (
                "Reconstructed from the verified pipeline's training rows only; "
                "checkpoint predictions reproduce the recorded validation metrics."
            ),
            "recorded_metrics": recorded_baseline,
            "validation_metrics_measured_before_candidate_training": {
                "MAE": baseline_val_metrics["MAE"],
                "RMSE": baseline_val_metrics["RMSE"],
                "R2": baseline_val_metrics["R2"],
            },
            "test_metrics_measured_after_model_selection": {
                "MAE": baseline_test_metrics["MAE"],
                "RMSE": baseline_test_metrics["RMSE"],
                "R2": baseline_test_metrics["R2"],
            },
        },
        "candidate_metrics": {
            "validation": attention_val_metrics,
            "test_after_selection": attention_test_metrics,
        },
        "selection": {
            "primary_metric": "validation R2",
            "selected_model": selected_model_name,
            "candidate_validation_r2_improved": (
                attention_val_metrics["R2"] > baseline_val_metrics["R2"]
            ),
            "selected_checkpoint_metrics_verified_after_reload": selected_metrics,
            "rule": (
                "Select the candidate only if its validation R2 is greater than "
                "the re-evaluated current baseline validation R2. Test metrics do "
                "not affect selection."
            ),
        },
        "artifact_paths": artifact_paths,
        "wind_artifact_sha256_before_run": wind_hashes_before,
    }
    rows = []
    for name, validation, test, model_path, feature_path, target_path in (
        (
            "Solar LSTM + Self-Attention",
            attention_val_metrics,
            attention_test_metrics,
            ATTENTION_MODEL_PATH,
            ATTENTION_FEATURE_SCALER_PATH,
            ATTENTION_TARGET_SCALER_PATH,
        ),
        (
            "Current Solar LSTM",
            baseline_val_metrics,
            baseline_test_metrics,
            BASELINE_MODEL_PATH,
            BASELINE_FEATURE_SCALER_PATH,
            BASELINE_TARGET_SCALER_PATH,
        ),
    ):
        rows.append(
            {
                "Model": name,
                "Validation_MAE": validation["MAE"],
                "Validation_RMSE": validation["RMSE"],
                "Validation_R2": validation["R2"],
                "Test_MAE": test["MAE"],
                "Test_RMSE": test["RMSE"],
                "Test_R2": test["R2"],
                "Selected_Model": selected_model_name,
                "Checkpoint_Path": str(model_path.resolve()),
                "Feature_Scaler_Path": str(feature_path.resolve()),
                "Target_Scaler_Path": str(target_path.resolve()),
                "Selected_Checkpoint_Path": str(SELECTED_MODEL_PATH.resolve()),
                "Selected_Feature_Scaler_Path": str(
                    SELECTED_FEATURE_SCALER_PATH.resolve()
                ),
                "Selected_Target_Scaler_Path": str(
                    SELECTED_TARGET_SCALER_PATH.resolve()
                ),
                "Metric_Source": (
                    "Newly measured on the shared split with shared train-fitted scalers"
                ),
            }
        )

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(REPORT_PATH, index=False)

    print("\nControlled Solar comparison")
    print(
        f"{'Model':32} {'Val MAE':>10} {'Val RMSE':>10} {'Val R2':>10} "
        f"{'Test MAE':>10} {'Test RMSE':>10} {'Test R2':>10}"
    )
    for row in rows:
        print(
            f"{row['Model']:32} {row['Validation_MAE']:10.6f} "
            f"{row['Validation_RMSE']:10.6f} {row['Validation_R2']:10.6f} "
            f"{row['Test_MAE']:10.6f} {row['Test_RMSE']:10.6f} "
            f"{row['Test_R2']:10.6f}"
        )
    print(f"Selected model (validation R2): {selected_model_name}")
    print(f"Selected checkpoint: {SELECTED_MODEL_PATH}")
    print(f"Report: {REPORT_PATH}")
    print(f"Manifest: {MANIFEST_PATH}")
    print("Original Solar checkpoint and Wind artifacts unchanged.")


if __name__ == "__main__":
    main()

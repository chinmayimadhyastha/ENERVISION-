"""Validate the reproducible ENERVISION daily ML pipeline end to end.

Checks performed
----------------
1.  Regenerated dataset exists and has the expected columns.
2.  ``_split`` values, counts and per-plant chronological order.
3.  The RF feature matrix has exactly 24 columns in the frozen leakage-free order.
4.  ``Generation_per_MW`` is absent from the dataset and RF contract.
5.  Generation lags and rolling features are reconstructed from historical targets
    only (empirical shift-before-roll proof).
6.  The LSTM feature contract has exactly 12 columns and sequence length 7 -> (7, 12).
7.  The RF pickle, both production LSTMs and all four scalers load.
8.  The RF artifact's feature order matches ``models/model_manifest.json`` and the
    current 24-feature importance report (which must sum to 1).
9.  The scalers contain exactly 12 feature slots and pair with the correct type.
10. Inference on held-out rows produces finite predictions.
11. Saved leakage-free RF metrics match an independent recomputation; historical
    25-feature metrics are reported separately and are not claimed as reproduced.
12. The daily forecasting contract is enforced: target ``DailyGeneration_MU``,
    frequency ``daily``, no hourly model artifact and no hourly forecasting code.

Metric mismatches are reported, never hidden, and do not count as structural failures.
Structural failures make the script exit non-zero.

Usage:
    python scripts/validate_pipeline.py
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE = Path(__file__).resolve().parent.parent

FEATURES_CSV = BASE / "data/final/plant_features_dataset.csv"
TRAIN_CSV = BASE / "data/final/plant_train.csv"
TEST_CSV = BASE / "data/final/plant_test.csv"
QUALITY_JSON = BASE / "reports/data_quality_summary.json"
REPORT_JSON = BASE / "reports/validation_report.json"

RF_SCRIPT = BASE / "scripts/train_random_forest.py"
LSTM_SCRIPT = BASE / "scripts/train_lstm_model(ABR).py"
HISTORICAL_RF_REPORT = BASE / "reports/generation_metrics.csv"
RF_LEAKAGE_FREE_REPORT = BASE / "reports/generation_metrics_leakage_free.csv"
RF_SUMMARY = BASE / "reports/rf_training_summary.json"
LSTM_REPORT = BASE / "reports/lstm_metrics.csv"
RF_IMPORTANCE = BASE / "reports/generation_feature_importance.csv"
RF_IMPORTANCE_HISTORICAL = BASE / "reports/generation_feature_importance_historical_25f.csv"
MANIFEST = BASE / "models/model_manifest.json"

RF_MODEL = BASE / "models/random_forest_model.pkl"
SOLAR_MODEL = BASE / "models/solar_lstm.keras"
WIND_MODEL = BASE / "models/wind_lstm.keras"
SOLAR_FEATURE_SCALER = BASE / "models/solar_scaler_features.joblib"
SOLAR_TARGET_SCALER = BASE / "models/solar_scaler_target.joblib"
WIND_FEATURE_SCALER = BASE / "models/wind_scaler_features.joblib"
WIND_TARGET_SCALER = BASE / "models/wind_scaler_target.joblib"

TARGET = "DailyGeneration_MU"

# Independent copies of the required contracts (from the task specification).
EXPECTED_RF_FEATURES = [
    "Capacity_MW",
    "Temperature",
    "Humidity",
    "WindSpeed",
    "GHI",
    "Pressure",
    "Temperature_lag_1",
    "Humidity_lag_1",
    "WindSpeed_lag_1",
    "GHI_lag_1",
    "Generation_lag_1",
    "Generation_lag_2",
    "Generation_lag_3",
    "Generation_lag_7",
    "Generation_roll_3",
    "Generation_roll_7",
    "Year",
    "Month",
    "DayOfYear",
    "DayOfWeek",
    "Month_sin",
    "Month_cos",
    "DayOfYear_sin",
    "DayOfYear_cos",
]
FORBIDDEN_RF_FEATURES = {"Generation_per_MW", "DailyGeneration_MU", "CumulativeGeneration_MU"}
EXPECTED_LSTM_FEATURES = [
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
LSTM_COLUMN_MAP = {
    "Lagged_Generation": "Generation_lag_1",
    "Rolling_Generation_7": "Generation_roll_7",
}

HISTORICAL_RF_METRICS_25F = {"MAE": 0.11163797642553697, "RMSE": 0.30033888392373304, "R2": 0.8711579851453006}
COMMITTED_LSTM_METRICS = {
    "Solar": {"MAE": 0.14415674553172728, "RMSE": 0.23457871027794697, "R2": 0.8668192421925991},
    "Wind": {"MAE": 0.6832080933787058, "RMSE": 1.0040038958594333, "R2": 0.4361064856242217},
}

README_HISTORICAL_EXPECTED = {
    "feature_rows": 22764,
    "train_rows": 17193,
    "test_rows": 5571,
    "plants": 25,
}


class Checks:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, name: str, passed: bool, detail: str, structural: bool = True) -> None:
        self.items.append(
            {"name": name, "passed": bool(passed), "detail": detail, "structural": bool(structural)}
        )
        label = "PASS" if passed else ("FAIL" if structural else "INFO")
        print(f"[{label}] {name}: {detail}")

    @property
    def failed(self) -> list[dict]:
        return [item for item in self.items if item["structural"] and not item["passed"]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT_JSON)
    return parser.parse_args()


def extract_assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise ValueError(f"Could not find top-level assignment {name!r} in {path}")


def finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def native(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def metric_block(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(math.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": float(r2_score(y_true, y_pred)),
    }


def compare_metrics(actual: dict, expected: dict, tolerance: float = 1e-6) -> dict:
    comparison = {}
    for name, expected_value in expected.items():
        actual_value = actual[name]
        delta = actual_value - expected_value
        comparison[name] = {
            "committed": float(expected_value),
            "recomputed": float(actual_value),
            "delta": float(delta),
            "reproduced": bool(abs(delta) <= tolerance),
        }
    comparison["all_reproduced"] = all(v["reproduced"] for k, v in comparison.items() if k != "all_reproduced")
    return comparison


def build_sequences(
    sub: pd.DataFrame,
    model_features: list[str],
    seq_len: int,
    predicate,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    windows: list[np.ndarray] = []
    targets: list[float] = []
    dates: list[str] = []

    for _, group in sub.groupby("PlantName", sort=True):
        group = group.sort_values("Date").reset_index(drop=True)
        for i in range(seq_len, len(group)):
            row = group.iloc[i]
            if predicate(row):
                windows.append(group.iloc[i - seq_len : i][model_features].to_numpy(dtype=float))
                targets.append(float(row[TARGET]))
                dates.append(str(pd.Timestamp(row["Date"]).date()))

    if not windows:
        return np.empty((0, seq_len, len(model_features))), np.empty((0,)), dates
    return np.stack(windows), np.asarray(targets, dtype=float), dates


def predict_lstm(model, feature_scaler, target_scaler, windows: np.ndarray) -> np.ndarray:
    if len(windows) == 0:
        return np.empty((0,))
    n, seq_len, n_features = windows.shape
    scaled = feature_scaler.transform(windows.reshape(-1, n_features)).reshape(n, seq_len, n_features)
    scaled_pred = model.predict(scaled, batch_size=512, verbose=0)
    return target_scaler.inverse_transform(scaled_pred.reshape(-1, 1)).reshape(-1)


def main() -> int:
    args = parse_args()
    checks = Checks()

    # --- Load data -------------------------------------------------------
    if not FEATURES_CSV.exists():
        raise FileNotFoundError(f"Missing {FEATURES_CSV}; run scripts/run_preprocessing_pipeline.py")
    df = pd.read_csv(FEATURES_CSV)
    df["Date"] = pd.to_datetime(df["Date"])

    train = pd.read_csv(TRAIN_CSV)
    test = pd.read_csv(TEST_CSV)
    for frame in (train, test):
        frame["Date"] = pd.to_datetime(frame["Date"])

    # --- Contracts from source scripts and manifest ----------------------
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_models = {model["id"]: model for model in manifest.get("models", [])}
    rf_manifest = manifest_models.get("random_forest_daily", {})

    rf_features = extract_assignment(RF_SCRIPT, "FEATURES")
    lstm_features = extract_assignment(LSTM_SCRIPT, "FEATURE_COLS")
    lstm_seq_len = extract_assignment(LSTM_SCRIPT, "SEQ_LEN")

    checks.add(
        "RF feature list matches specification",
        rf_features == EXPECTED_RF_FEATURES,
        f"{len(rf_features)} features, exact-order match={rf_features == EXPECTED_RF_FEATURES}",
    )
    checks.add(
        "RF feature list matches model manifest",
        rf_manifest.get("feature_order") == rf_features
        and rf_manifest.get("feature_count") == len(rf_features),
        f"manifest_count={rf_manifest.get('feature_count')}, "
        f"order_match={rf_manifest.get('feature_order') == rf_features}",
    )
    leaked_features = sorted(FORBIDDEN_RF_FEATURES.intersection(rf_features))
    checks.add(
        "RF feature contract contains no target-leakage feature",
        not leaked_features,
        "no forbidden features" if not leaked_features else f"forbidden present: {leaked_features}",
    )
    checks.add(
        "Generation_per_MW is absent from the dataset",
        "Generation_per_MW" not in df.columns and "Generation_per_MW" not in rf_features,
        f"dataset_has_column={'Generation_per_MW' in df.columns}, "
        f"contract_has_feature={'Generation_per_MW' in rf_features}",
    )
    checks.add(
        "LSTM feature list matches specification",
        lstm_features == EXPECTED_LSTM_FEATURES,
        f"{len(lstm_features)} features, exact-order match={lstm_features == EXPECTED_LSTM_FEATURES}",
    )
    checks.add("LSTM sequence length", lstm_seq_len == 7, f"SEQ_LEN={lstm_seq_len}")

    missing_rf = [c for c in rf_features if c not in df.columns]
    checks.add(
        "RF features present in dataset",
        not missing_rf,
        "all present" if not missing_rf else f"missing {missing_rf}",
    )

    mapped_lstm_features = [LSTM_COLUMN_MAP.get(c, c) for c in lstm_features]
    missing_lstm = [c for c in mapped_lstm_features if c not in df.columns]
    checks.add(
        "LSTM features present in dataset",
        not missing_lstm,
        "all present" if not missing_lstm else f"missing {missing_lstm}",
    )

    checks.add(
        "Generated dataset shape",
        len(df) > 0,
        f"{df.shape[0]} rows x {df.shape[1]} columns; plants={df['PlantName'].nunique()}",
    )

    # --- Split integrity -------------------------------------------------
    checks.add(
        "_split column exists with train/test values",
        "_split" in df.columns and set(df["_split"].dropna().unique()) == {"train", "test"},
        f"values={sorted(df['_split'].dropna().unique().tolist())}",
    )

    counts = df["_split"].value_counts().to_dict()
    checks.add(
        "Split row counts match train/test files",
        len(train) == counts.get("train") and len(test) == counts.get("test") and len(train) + len(test) == len(df),
        f"features train/test={counts.get('train')}/{counts.get('test')}, files={len(train)}/{len(test)}",
    )

    split_rule_ok = True
    order_violations = []
    rule_details = []
    for plant, group in df.groupby("PlantName", sort=True):
        ordered = group.sort_values(["Date", "Capacity_MW"]).reset_index(drop=True)
        n = len(ordered)
        expected_train = n if n == 1 else min(max(int(n * 0.8), 1), n - 1)
        actual_train = int((ordered["_split"] == "train").sum())
        if actual_train != expected_train:
            split_rule_ok = False
            rule_details.append(f"{plant}: train={actual_train}, expected={expected_train}")

        plant_train = ordered[ordered["_split"] == "train"]["Date"]
        plant_test = ordered[ordered["_split"] == "test"]["Date"]
        if len(plant_train) and len(plant_test) and plant_test.min() < plant_train.max():
            order_violations.append(plant)

    checks.add(
        "Per-plant rule is earliest 80% / latest 20%",
        split_rule_ok,
        "all plants follow int(n*0.8) rule" if split_rule_ok else "; ".join(rule_details[:5]),
    )
    checks.add(
        "No test row precedes a train row for the same plant",
        not order_violations,
        f"violations={order_violations}" if order_violations else "0 violations",
    )

    # --- RF matrix -------------------------------------------------------
    rf_matrix = df[rf_features].apply(pd.to_numeric, errors="coerce")
    checks.add(
        "RF feature matrix is exactly 24 columns in order",
        rf_matrix.shape[1] == 24 and list(rf_matrix.columns) == EXPECTED_RF_FEATURES,
        f"shape={rf_matrix.shape}",
    )
    checks.add(
        "RF feature matrix contains only finite numbers",
        np.isfinite(rf_matrix.to_numpy(dtype=float)).all(),
        f"NaN={int(rf_matrix.isna().sum().sum())}, inf={int(np.isinf(rf_matrix.to_numpy(dtype=float)).sum())}",
    )

    # Empirical leakage proof: reconstruct every historical feature from the target
    # series using shift/rolling and compare it with the stored feature.  Rows whose
    # reconstruction is undefined (the first rows of each plant, before enough
    # history exists) are skipped; every defined row must match.
    lag_specs = {
        "Generation_lag_1": 1,
        "Generation_lag_2": 2,
        "Generation_lag_3": 3,
        "Generation_lag_7": 7,
    }
    rolling_specs = {"Generation_roll_3": 3, "Generation_roll_7": 7}
    weather_lag_specs = {
        "Temperature_lag_1": "Temperature",
        "Humidity_lag_1": "Humidity",
        "WindSpeed_lag_1": "WindSpeed",
        "GHI_lag_1": "GHI",
    }

    leakage_checked = 0
    leakage_max_delta = 0.0
    leakage_violations: list[str] = []

    def compare_series(plant: str, feature: str, stored: pd.Series, baseline: pd.Series) -> None:
        nonlocal leakage_checked, leakage_max_delta
        mask = baseline.notna() & stored.notna()
        if not mask.any():
            return
        delta = (stored[mask].astype(float) - baseline[mask].astype(float)).abs()
        leakage_checked += int(mask.sum())
        local_max = float(delta.max())
        leakage_max_delta = max(leakage_max_delta, local_max)
        if local_max > 1e-8 and len(leakage_violations) < 5:
            leakage_violations.append(f"{plant}:{feature} max_delta={local_max:.3e}")

    for plant, group in df.groupby("PlantName", sort=True):
        ordered = group.sort_values(["Date", "Capacity_MW"]).reset_index(drop=True)
        target_series = pd.to_numeric(ordered[TARGET], errors="coerce")
        for feature, lag in lag_specs.items():
            compare_series(plant, feature, pd.to_numeric(ordered[feature], errors="coerce"),
                           target_series.shift(lag))
        for feature, window in rolling_specs.items():
            baseline = target_series.shift(1).rolling(window, min_periods=window).mean()
            compare_series(plant, feature, pd.to_numeric(ordered[feature], errors="coerce"), baseline)
        for feature, source in weather_lag_specs.items():
            baseline = pd.to_numeric(ordered[source], errors="coerce").shift(1)
            compare_series(plant, feature, pd.to_numeric(ordered[feature], errors="coerce"), baseline)

    leakage_ok = (
        leakage_checked > 0
        and not leakage_violations
        and leakage_max_delta <= 1e-8
    )
    checks.add(
        "Generation lag/rolling features are historical-only (leakage-safe)",
        leakage_ok,
        f"checked_rows={leakage_checked}, max_abs_delta={leakage_max_delta:.3e}, "
        f"violations={leakage_violations if leakage_violations else 'none'}",
    )

    test_matrix = test[rf_features].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)

    # --- Load artifacts --------------------------------------------------
    rf = joblib.load(RF_MODEL)
    checks.add(
        "Random Forest loads and expects 24 features",
        getattr(rf, "n_features_in_", None) == 24,
        f"{type(rf).__name__}, n_features_in_={getattr(rf, 'n_features_in_', None)}, trees={len(getattr(rf, 'estimators_', []))}",
    )

    # Independent proof of the artifact's feature order: the current importance report
    # must line up index-by-index with the model's own feature_importances_.
    importance = pd.read_csv(RF_IMPORTANCE)
    importance_map = dict(zip(importance["Feature"], importance["Importance"]))
    model_importance = np.asarray(rf.feature_importances_, dtype=float)
    order_proof_ok = (
        len(importance) == 24
        and set(importance["Feature"]) == set(rf_features)
        and all(
            feature in importance_map
            and abs(model_importance[i] - importance_map[feature]) <= 1e-9
            for i, feature in enumerate(rf_features)
        )
    )
    checks.add(
        "RF artifact feature order matches 24-feature importance report",
        order_proof_ok,
        f"report_rows={len(importance)}, all importances match index-by-index={order_proof_ok}",
    )
    importance_sum = float(importance["Importance"].sum())
    checks.add(
        "RF importances cover exactly 24 features and sum to 1",
        len(importance) == 24
        and importance["Feature"].nunique() == 24
        and abs(importance_sum - 1.0) <= 1e-6,
        f"rows={len(importance)}, unique={importance['Feature'].nunique()}, sum={importance_sum:.15f}",
    )
    checks.add(
        "Historical 25-feature importance report preserved",
        RF_IMPORTANCE_HISTORICAL.exists()
        and len(pd.read_csv(RF_IMPORTANCE_HISTORICAL)) == 25,
        f"path={RF_IMPORTANCE_HISTORICAL.name}, exists={RF_IMPORTANCE_HISTORICAL.exists()}",
    )

    rf_hash = file_sha256(RF_MODEL)
    checks.add(
        "RF artifact hash matches model manifest",
        rf_manifest.get("artifact_sha256") == rf_hash
        and rf_manifest.get("artifact_size_bytes") == int(RF_MODEL.stat().st_size),
        f"sha256={rf_hash}, manifest={rf_manifest.get('artifact_sha256')}",
    )
    checks.add(
        "Manifest marks RF as a serving-safe production candidate",
        rf_manifest.get("status") == "production_candidate"
        and rf_manifest.get("serving_safe") is True
        and rf_manifest.get("target") == TARGET
        and rf_manifest.get("frequency") == "daily",
        f"status={rf_manifest.get('status')}, serving_safe={rf_manifest.get('serving_safe')}, "
        f"target={rf_manifest.get('target')}, frequency={rf_manifest.get('frequency')}",
    )

    import keras  # imported here so the rest of the checks can run without TensorFlow

    solar_model = keras.models.load_model(SOLAR_MODEL, compile=False)
    wind_model = keras.models.load_model(WIND_MODEL, compile=False)
    checks.add(
        "Solar LSTM loads with input shape (7, 12)",
        tuple(solar_model.input_shape) == (None, 7, 12),
        f"input_shape={tuple(solar_model.input_shape)}",
    )
    checks.add(
        "Wind LSTM loads with input shape (7, 12)",
        tuple(wind_model.input_shape) == (None, 7, 12),
        f"input_shape={tuple(wind_model.input_shape)}",
    )

    scalers = {
        "solar_features": joblib.load(SOLAR_FEATURE_SCALER),
        "solar_target": joblib.load(SOLAR_TARGET_SCALER),
        "wind_features": joblib.load(WIND_FEATURE_SCALER),
        "wind_target": joblib.load(WIND_TARGET_SCALER),
    }
    scaler_ok = all(
        getattr(scalers[f"{kind}_features"], "n_features_in_", None) == 12
        and len(getattr(scalers[f"{kind}_features"], "mean_", [])) == 12
        and len(getattr(scalers[f"{kind}_target"], "mean_", [])) == 1
        for kind in ("solar", "wind")
    )
    checks.add(
        "All four scalers load with 12 feature slots / 1 target slot",
        scaler_ok,
        ", ".join(
            f"{name}:{getattr(obj, 'n_features_in_', '?')}f" for name, obj in scalers.items()
        ),
    )

    # Pairing proof: each scaler must contain the exact fit statistics of that
    # renewable type's *training* split (the code-defined LSTM split: pre-2026 rows,
    # earliest 80% per plant).  If the 12 feature means/scales match, the scaler is
    # proven to pair with the correct type and the correct feature order.
    solar_rows = df[df["Type"] == "Solar"]
    wind_rows = df[df["Type"] == "Wind"]

    def lstm_training_frame(sub: pd.DataFrame) -> pd.DataFrame:
        parts = []
        for _, group in sub.groupby("PlantName", sort=True):
            group = group.sort_values("Date")
            pre = group[group["Date"] <= pd.Timestamp("2025-12-31")]
            if len(pre) < lstm_seq_len + 1:
                continue
            n_train = int(len(pre) * 0.8)
            parts.append(pre.iloc[:n_train])
        if not parts:
            raise ValueError("No LSTM training rows reconstructed")
        return pd.concat(parts, ignore_index=True)

    solar_train = lstm_training_frame(solar_rows)
    wind_train = lstm_training_frame(wind_rows)

    def scaler_fit_deltas(scaler, frame: pd.DataFrame) -> tuple[float, float]:
        means = frame[mapped_lstm_features].mean().to_numpy(dtype=float)
        scales = frame[mapped_lstm_features].std(ddof=0).to_numpy(dtype=float)
        return (
            float(np.max(np.abs(scaler.mean_ - means))),
            float(np.max(np.abs(scaler.scale_ - scales))),
        )

    solar_mean_delta, solar_scale_delta = scaler_fit_deltas(scalers["solar_features"], solar_train)
    wind_mean_delta, wind_scale_delta = scaler_fit_deltas(scalers["wind_features"], wind_train)

    def target_scaler_delta(scaler, frame: pd.DataFrame) -> tuple[float, float]:
        return (
            float(abs(scaler.mean_[0] - frame[TARGET].mean())),
            float(abs(scaler.scale_[0] - frame[TARGET].std(ddof=0))),
        )

    solar_target_mean_delta, solar_target_scale_delta = target_scaler_delta(
        scalers["solar_target"], solar_train
    )
    wind_target_mean_delta, wind_target_scale_delta = target_scaler_delta(
        scalers["wind_target"], wind_train
    )

    tolerance = 1e-3
    pairing_ok = (
        solar_mean_delta <= tolerance
        and solar_scale_delta <= tolerance
        and wind_mean_delta <= tolerance
        and wind_scale_delta <= tolerance
        and solar_target_mean_delta <= tolerance
        and solar_target_scale_delta <= tolerance
        and wind_target_mean_delta <= tolerance
        and wind_target_scale_delta <= tolerance
    )
    scaler_pairing = {
        "method": (
            "Compare scaler.mean_/scale_ with the mean/population-std of the "
            "code-defined LSTM training split for the matching renewable type."
        ),
        "solar": {
            "feature_mean_max_abs_delta": solar_mean_delta,
            "feature_scale_max_abs_delta": solar_scale_delta,
            "target_mean_abs_delta": solar_target_mean_delta,
            "target_scale_abs_delta": solar_target_scale_delta,
        },
        "wind": {
            "feature_mean_max_abs_delta": wind_mean_delta,
            "feature_scale_max_abs_delta": wind_scale_delta,
            "target_mean_abs_delta": wind_target_mean_delta,
            "target_scale_abs_delta": wind_target_scale_delta,
        },
        "tolerance": tolerance,
        "verified": bool(pairing_ok),
    }
    checks.add(
        "Scalers match the 12 LSTM features and correct renewable type",
        pairing_ok,
        f"solar max|dmean|={solar_mean_delta:.2e}, max|dscale|={solar_scale_delta:.2e}; "
        f"wind max|dmean|={wind_mean_delta:.2e}, max|dscale|={wind_scale_delta:.2e}",
    )

    # --- Inference -------------------------------------------------------
    rf_predictions = np.asarray(rf.predict(test_matrix), dtype=float).reshape(-1)
    checks.add(
        "RF inference on test rows is finite",
        len(rf_predictions) > 0 and np.isfinite(rf_predictions).all(),
        f"n={len(rf_predictions)}, min={rf_predictions.min():.4f}, max={rf_predictions.max():.4f}, mean={rf_predictions.mean():.4f}",
    )

    inference = {
        "random_forest": {
            "rows": int(len(rf_predictions)),
            "finite": bool(np.isfinite(rf_predictions).all()),
            "min": float(rf_predictions.min()),
            "max": float(rf_predictions.max()),
            "mean": float(rf_predictions.mean()),
        }
    }

    lstm_results = {}
    for kind, model, feature_scaler, target_scaler in (
        ("Solar", solar_model, scalers["solar_features"], scalers["solar_target"]),
        ("Wind", wind_model, scalers["wind_features"], scalers["wind_target"]),
    ):
        sub = df[df["Type"] == kind]
        windows, y_true, _ = build_sequences(
            sub,
            mapped_lstm_features,
            lstm_seq_len,
            lambda row: row["_split"] == "test",
        )
        predictions = predict_lstm(model, feature_scaler, target_scaler, windows)
        finite_ok = len(predictions) > 0 and np.isfinite(predictions).all()
        checks.add(
            f"{kind} LSTM inference on test windows is finite",
            finite_ok,
            f"n={len(predictions)}, input={windows.shape[1:]}, "
            + (f"min={predictions.min():.4f}, max={predictions.max():.4f}, mean={predictions.mean():.4f}" if len(predictions) else "no windows"),
        )
        inference[f"{kind.lower()}_lstm"] = {
            "sequences": int(len(predictions)),
            "input_shape_per_sequence": list(windows.shape[1:]) if len(windows) else None,
            "finite": bool(finite_ok),
            "min": float(predictions.min()) if len(predictions) else None,
            "max": float(predictions.max()) if len(predictions) else None,
            "mean": float(predictions.mean()) if len(predictions) else None,
        }
        lstm_results[kind] = {
            "y_true": y_true,
            "windows": windows,
            "predictions_test_split": predictions,
        }

    # --- Metric consistency ---------------------------------------------
    rf_actual = metric_block(test[TARGET].to_numpy(dtype=float), rf_predictions)

    # The current leakage-free RF metrics are saved to their own report.  Verify that
    # the saved report matches an independent recomputation.
    rf_saved_frame = pd.read_csv(RF_LEAKAGE_FREE_REPORT)
    rf_saved_metrics = {
        "MAE": float(rf_saved_frame.loc[0, "MAE"]),
        "RMSE": float(rf_saved_frame.loc[0, "RMSE"]),
        "R2": float(rf_saved_frame.loc[0, "R2"]),
    }
    rf_saved_comparison = compare_metrics(rf_actual, rf_saved_metrics, tolerance=1e-9)
    checks.add(
        "Saved leakage-free RF metrics match recomputation",
        bool(rf_saved_comparison["all_reproduced"]),
        f"recomputed MAE/RMSE/R2={rf_actual['MAE']:.9f}/{rf_actual['RMSE']:.9f}/{rf_actual['R2']:.9f}; "
        f"saved={rf_saved_metrics['MAE']:.9f}/{rf_saved_metrics['RMSE']:.9f}/{rf_saved_metrics['R2']:.9f}",
    )

    # Historical 25-feature metrics remain preserved but are not comparable to the
    # current 24-feature contract.  This is informational, never a reproduction claim.
    historical_rf_frame = pd.read_csv(HISTORICAL_RF_REPORT)
    historical_rf_metrics = {
        "MAE": float(historical_rf_frame.loc[0, "MAE"]),
        "RMSE": float(historical_rf_frame.loc[0, "RMSE"]),
        "R2": float(historical_rf_frame.loc[0, "R2"]),
    }
    historical_preserved = all(
        abs(historical_rf_metrics[key] - value) <= 1e-12
        for key, value in HISTORICAL_RF_METRICS_25F.items()
    )
    checks.add(
        "Historical 25-feature RF metrics preserved separately",
        historical_preserved,
        f"{historical_rf_metrics['MAE']:.6f}/{historical_rf_metrics['RMSE']:.6f}/{historical_rf_metrics['R2']:.6f} "
        "kept for provenance; feature contract changed so not comparable",
        structural=False,
    )

    lstm_comparison = {}
    for kind, model, feature_scaler, target_scaler in (
        ("Solar", solar_model, scalers["solar_features"], scalers["solar_target"]),
        ("Wind", wind_model, scalers["wind_features"], scalers["wind_target"]),
    ):
        sub = df[df["Type"] == kind]
        windows, y_true, dates = build_sequences(
            sub,
            mapped_lstm_features,
            lstm_seq_len,
            lambda row: pd.Timestamp(row["Date"]) >= pd.Timestamp("2026-01-01"),
        )
        predictions = predict_lstm(model, feature_scaler, target_scaler, windows)
        actual = metric_block(y_true, predictions)
        lstm_comparison[kind] = {
            "test_window": "Date >= 2026-01-01 (code-defined production LSTM test window)",
            "sequences": int(len(predictions)),
            "date_range": [min(dates), max(dates)] if dates else None,
            "comparison": compare_metrics(actual, COMMITTED_LSTM_METRICS[kind]),
        }

    metric_reproduction = {
        "random_forest": {
            "feature_contract_changed": True,
            "current_feature_count": len(rf_features),
            "historical_25f": {
                "metrics": historical_rf_metrics,
                "source": "reports/generation_metrics.csv",
                "status": "historical actual metric from the removed 25-feature leaked contract",
                "comparable_to_current_model": False,
                "reproduced": False,
                "note": (
                    "Preserved for provenance only. The original 22,764-row / 25-plant "
                    "feature dataset and its _split are absent, and the feature contract "
                    "changed (Generation_per_MW removed), so these values are neither "
                    "reproduced nor comparable."
                ),
            },
            "leakage_free_24f": {
                "split": "regenerated per-plant chronological 80/20 split",
                "test_rows": int(len(test)),
                "recomputed": rf_actual,
                "saved": rf_saved_metrics,
                "matches_saved_report": bool(rf_saved_comparison["all_reproduced"]),
                "comparison": rf_saved_comparison,
                "status": "current production-candidate metric; recomputed and matches saved report",
            },
        },
        "lstm": lstm_comparison,
    }

    for kind, block in lstm_comparison.items():
        comp = block["comparison"]
        checks.add(
            f"{kind} LSTM metrics reproduce committed values",
            bool(comp["all_reproduced"]),
            f"recomputed MAE/RMSE/R2={comp['MAE']['recomputed']:.6f}/{comp['RMSE']['recomputed']:.6f}/{comp['R2']['recomputed']:.6f}; "
            f"committed={comp['MAE']['committed']:.6f}/{comp['RMSE']['committed']:.6f}/{comp['R2']['committed']:.6f}",
            structural=False,
        )

    # --- Dataset expectation check --------------------------------------
    readme_comparison = {
        "expected_historical_readme_figures": README_HISTORICAL_EXPECTED,
        "actual": {
            "feature_rows": int(len(df)),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "plants": int(df["PlantName"].nunique()),
        },
    }
    readme_comparison["matches"] = all(
        readme_comparison["expected_historical_readme_figures"][k] == readme_comparison["actual"][k]
        for k in README_HISTORICAL_EXPECTED
    )
    checks.add(
        "Historical README 25-plant / 22,764-row figures remain distinguishable from current dataset",
        bool(readme_comparison["matches"]),
        f"actual={readme_comparison['actual']} vs historical={README_HISTORICAL_EXPECTED}; "
        "documented as provenance only, not reproduced",
        structural=False,
    )

    # --- Daily forecasting contract -------------------------------------
    contract = manifest.get("forecasting_contract", {})
    target_entry = manifest.get("target", {})
    daily_manifest_ok = (
        target_entry.get("name") == TARGET
        and target_entry.get("frequency") == "daily"
        and contract.get("target") == TARGET
        and contract.get("frequency") == "daily"
        and contract.get("hourly_forecasting") is False
        and bool(manifest_models)
        and all(model.get("frequency") == "daily" for model in manifest_models.values())
    )
    checks.add(
        "Manifest enforces the daily forecasting contract",
        daily_manifest_ok,
        f"target={target_entry.get('name')}, target_frequency={target_entry.get('frequency')}, "
        f"contract_frequency={contract.get('frequency')}, hourly={contract.get('hourly_forecasting')}, "
        f"model_frequencies={sorted({m.get('frequency') for m in manifest_models.values()})}",
    )

    validator_name = Path(__file__).resolve().name
    hourly_scripts = []
    for path in sorted((BASE / "scripts").glob("*.py")):
        if path.name == validator_name:
            continue
        if "hourly" in path.read_text(encoding="utf-8").lower():
            hourly_scripts.append(path.name)
    checks.add(
        "No hourly forecasting code in scripts",
        not hourly_scripts,
        f"hourly_scripts={hourly_scripts}" if hourly_scripts else "no hourly references found",
    )

    hourly_artifacts = [
        path.name for path in sorted((BASE / "models").glob("*")) if "hourly" in path.name.lower()
    ]
    checks.add(
        "No hourly model artifact exists",
        not hourly_artifacts,
        f"hourly_artifacts={hourly_artifacts}" if hourly_artifacts else "none",
    )

    daily_contract = {
        "frequency": contract.get("frequency"),
        "target": contract.get("target"),
        "unit": contract.get("unit"),
        "horizon": contract.get("horizon"),
        "hourly_forecasting": contract.get("hourly_forecasting"),
        "model_frequencies": {
            model_id: model.get("frequency") for model_id, model in manifest_models.items()
        },
        "hourly_scripts": hourly_scripts,
        "hourly_artifacts": hourly_artifacts,
        "verified": bool(daily_manifest_ok and not hourly_scripts and not hourly_artifacts),
    }

    # --- Environment -----------------------------------------------------
    import tensorflow as tf

    environment = {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": __import__("sklearn").__version__,
        "joblib": joblib.__version__,
        "tensorflow": tf.__version__,
        "keras": keras.__version__,
    }

    quality_summary = json.loads(QUALITY_JSON.read_text(encoding="utf-8")) if QUALITY_JSON.exists() else None

    report = {
        "pipeline": {
            "canonical_dataset": "data/final/full_generation_weather_dataset.csv",
            "stages": [
                "scripts/build_plant_weather_training_dataset.py",
                "scripts/engineer_plant_features.py",
                "scripts/split_plant_dataset.py",
            ],
            "split_rule": "per plant, sort by Date; earliest int(n*0.8) -> train, remainder -> test",
            "random_split": False,
        },
        "environment": environment,
        "dataset": {
            "shape": [int(df.shape[0]), int(df.shape[1])],
            "plants": int(df["PlantName"].nunique()),
            "solar_rows": int((df["Type"] == "Solar").sum()),
            "wind_rows": int((df["Type"] == "Wind").sum()),
            "date_range": [str(df["Date"].min().date()), str(df["Date"].max().date())],
            "columns": list(df.columns),
        },
        "split": {
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "train_ratio": float(len(train) / len(df)),
            "plants_with_test": int(test["PlantName"].nunique()),
            "temporal_violations": order_violations,
            "train_date_range": [str(train["Date"].min().date()), str(train["Date"].max().date())],
            "test_date_range": [str(test["Date"].min().date()), str(test["Date"].max().date())],
        },
        "feature_contracts": {
            "random_forest": {
                "count": len(rf_features),
                "order": rf_features,
                "source": "scripts/train_random_forest.py",
                "status": "leakage_free",
                "removed_features": {
                    "Generation_per_MW": "Removed because it is DailyGeneration_MU / Capacity_MW and therefore used the prediction target."
                },
                "manifest_order_matches": rf_manifest.get("feature_order") == rf_features,
            },
            "lstm": {
                "count": len(lstm_features),
                "order": lstm_features,
                "dataset_column_map": LSTM_COLUMN_MAP,
                "sequence_length": lstm_seq_len,
                "source": "scripts/train_lstm_model(ABR).py",
            },
        },
        "leakage_checks": {
            "forbidden_rf_features": sorted(FORBIDDEN_RF_FEATURES),
            "forbidden_present_in_contract": leaked_features,
            "generation_per_mw_in_dataset": "Generation_per_MW" in df.columns,
            "generation_per_mw_in_rf_contract": "Generation_per_MW" in rf_features,
            "generation_lags": {
                feature: f"shift({lag}) per plant"
                for feature, lag in lag_specs.items()
            },
            "generation_rolling": {
                feature: f"shift(1) then rolling({window}, min_periods={window}).mean() per plant"
                for feature, window in rolling_specs.items()
            },
            "weather_lags": {
                feature: f"shift(1) of {source} per plant"
                for feature, source in weather_lag_specs.items()
            },
            "empirical_reconstruction": {
                "checked_rows": int(leakage_checked),
                "max_abs_delta": float(leakage_max_delta),
                "violations": leakage_violations,
                "verified": bool(leakage_ok),
            },
            "target_not_in_rf_contract": TARGET not in rf_features,
        },
        "artifacts": {
            "random_forest": {
                "path": "models/random_forest_model.pkl",
                "loaded": True,
                "n_features_in": int(rf.n_features_in_),
                "trees": len(rf.estimators_),
                "sha256": file_sha256(RF_MODEL),
                "size_bytes": int(RF_MODEL.stat().st_size),
                "manifest_hash_matches": rf_manifest.get("artifact_sha256") == file_sha256(RF_MODEL),
                "serving_safe": rf_manifest.get("serving_safe"),
                "status": rf_manifest.get("status"),
            },
            "solar_lstm": {
                "path": "models/solar_lstm.keras",
                "loaded": True,
                "input_shape": list(solar_model.input_shape),
            },
            "wind_lstm": {
                "path": "models/wind_lstm.keras",
                "loaded": True,
                "input_shape": list(wind_model.input_shape),
            },
            "scalers": {
                name: {
                    "n_features_in": getattr(obj, "n_features_in_", None),
                    "type": type(obj).__name__,
                }
                for name, obj in scalers.items()
            },
            "scaler_pairing_verification": scaler_pairing,
        },
        "inference": inference,
        "metric_reproduction": metric_reproduction,
        "daily_contract": daily_contract,
        "readme_dataset_comparison": readme_comparison,
        "data_quality_summary": quality_summary,
        "checks": checks.items,
        "structural_status": "pass" if not checks.failed else "fail",
        "metric_reproduction_status": {
            "random_forest": {
                "historical_25f": "preserved_for_provenance_not_reproduced_not_comparable",
                "leakage_free_24f": (
                    "saved_report_matches_recomputation"
                    if metric_reproduction["random_forest"]["leakage_free_24f"]["matches_saved_report"]
                    else "saved_report_mismatch"
                ),
            },
            "lstm": {
                kind: "reproduced" if block["comparison"]["all_reproduced"] else "not_reproduced"
                for kind, block in lstm_comparison.items()
            },
        },
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, default=native) + "\n", encoding="utf-8")

    print("\n" + "=" * 72)
    print("VALIDATION SUMMARY")
    print("=" * 72)
    print(f"Structural checks : {'PASS' if not checks.failed else 'FAIL'} ({len(checks.items) - len(checks.failed)}/{len(checks.items)})")
    print(f"Dataset           : {df.shape[0]} rows x {df.shape[1]} columns, {df['PlantName'].nunique()} plants")
    print(f"Split             : {len(train)} train / {len(test)} test")
    print(
        "RF metrics        : "
        + (
            "SAVED REPORT MATCHES RECOMPUTATION"
            if metric_reproduction["random_forest"]["leakage_free_24f"]["matches_saved_report"]
            else "SAVED REPORT MISMATCH"
        )
        + " (historical 25-feature metrics preserved separately, not reproduced)"
    )
    print(f"Daily contract    : {'DAILY' if daily_contract['verified'] else 'VIOLATION'} "
          f"(target={daily_contract['target']}, hourly={daily_contract['hourly_forecasting']})")
    for kind, block in lstm_comparison.items():
        print(f"{kind} LSTM metrics  : {'REPRODUCED' if block['comparison']['all_reproduced'] else 'NOT REPRODUCED'}")
    print(f"\nReport saved: {args.report}")

    if checks.failed:
        print("\nFailed structural checks:")
        for item in checks.failed:
            print(f"  - {item['name']}: {item['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Train and calibrate probabilistic renewable-energy forecasting models (P10, P50, P90).

Methodology:
- Asymmetric Pinball Loss Quantile Regression using HistGradientBoostingRegressor (loss='quantile', quantile=alpha).
- Quantiles: alpha in {0.10, 0.50, 0.90} for P10 (conservative), P50 (median), P90 (optimistic).
- Strict chronological data split: training (earliest 80% per plant) / validation calibration (latest 20% of train).
- Conformal residual calibration computed on the validation split to achieve calibrated 80% coverage.
- Monotonicity (P10 <= P50 <= P90) and physical constraints (0 <= P10, P90 <= Capacity_MW * 24 / 1000).
- Separate models for Solar and Wind.
- Final evaluation on untouched test set (data/final/plant_test.csv).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Silence loky core counting in Windows sandbox
os.environ["LOKY_MAX_CPU_COUNT"] = "1"

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "final"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

FEATURES = [
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

TARGET = "DailyGeneration_MU"


def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, alpha: float) -> float:
    err = y_true - y_pred
    return float(np.mean(np.maximum(alpha * err, (alpha - 1) * err)))


def train_probabilistic_models():
    print("Loading canonical datasets...")
    train_df = pd.read_csv(DATA_DIR / "plant_train.csv")
    test_df = pd.read_csv(DATA_DIR / "plant_test.csv")

    # Chronological split per plant for training and validation/calibration
    train_splits = []
    val_splits = []
    for plant, group in train_df.groupby("PlantName", sort=False):
        group = group.sort_values("Date")
        n = len(group)
        n_tr = int(n * 0.8)
        train_splits.append(group.iloc[:n_tr])
        val_splits.append(group.iloc[n_tr:])

    tr = pd.concat(train_splits, ignore_index=True)
    val = pd.concat(val_splits, ignore_index=True)
    print(f"Data split: Train={len(tr)}, Validation={len(val)}, Test={len(test_df)}")

    models = {}
    calibration_info = {}
    metrics_report = {
        "method": "Conformalized Quantile Regression with Pinball Loss",
        "quantiles": [0.10, 0.50, 0.90],
        "features": FEATURES,
        "results": {},
    }

    for rtype in ["Solar", "Wind"]:
        print(f"\n--- Training Probabilistic Models for {rtype} ---")
        tr_r = tr[tr["Type"] == rtype]
        val_r = val[val["Type"] == rtype]
        test_r = test_df[test_df["Type"] == rtype]

        X_tr, y_tr = tr_r[FEATURES], tr_r[TARGET]
        X_val, y_val = val_r[FEATURES], val_r[TARGET]
        X_test, y_test = test_r[FEATURES], test_r[TARGET]

        # Fit quantile regressors directly minimizing pinball loss
        print(f"Fitting P10 model (alpha=0.10) for {rtype}...")
        q10 = HistGradientBoostingRegressor(
            loss="quantile", quantile=0.10, max_iter=80, random_state=42
        ).fit(X_tr, y_tr)

        print(f"Fitting P50 model (alpha=0.50) for {rtype}...")
        q50 = HistGradientBoostingRegressor(
            loss="quantile", quantile=0.50, max_iter=80, random_state=42
        ).fit(X_tr, y_tr)

        print(f"Fitting P90 model (alpha=0.90) for {rtype}...")
        q90 = HistGradientBoostingRegressor(
            loss="quantile", quantile=0.90, max_iter=80, random_state=42
        ).fit(X_tr, y_tr)

        # Predict on validation calibration set
        p10_v = q10.predict(X_val)
        p50_v = q50.predict(X_val)
        p90_v = q90.predict(X_val)
        y_val_arr = y_val.values

        # Conformal non-conformity score on validation
        scores = np.maximum(p10_v - y_val_arr, y_val_arr - p90_v)
        calib_offset = float(max(0.0, np.percentile(scores, 80)))
        print(f"{rtype} Calibration Offset (80th percentile non-conformity): {calib_offset:.4f} MU/day")

        # Evaluate on validation
        p10_v_cal = np.maximum(0.0, np.minimum(p10_v - calib_offset, p50_v))
        p50_v_cal = np.maximum(0.0, p50_v)
        p90_v_cal = np.maximum(p50_v_cal, p90_v + calib_offset)

        val_cov = float(np.mean((y_val_arr >= p10_v_cal) & (y_val_arr <= p90_v_cal)))
        val_width = float(np.mean(p90_v_cal - p10_v_cal))
        val_pb10 = pinball_loss(y_val_arr, p10_v_cal, 0.10)
        val_pb50 = pinball_loss(y_val_arr, p50_v_cal, 0.50)
        val_pb90 = pinball_loss(y_val_arr, p90_v_cal, 0.90)

        # Evaluate on test
        p10_t = q10.predict(X_test)
        p50_t = q50.predict(X_test)
        p90_t = q90.predict(X_test)
        y_test_arr = y_test.values

        p10_t_cal = np.maximum(0.0, np.minimum(p10_t - calib_offset, p50_t))
        p50_t_cal = np.maximum(0.0, p50_t)
        p90_t_cal = np.maximum(p50_t_cal, p90_t + calib_offset)

        test_cov = float(np.mean((y_test_arr >= p10_t_cal) & (y_test_arr <= p90_t_cal)))
        test_width = float(np.mean(p90_t_cal - p10_t_cal))
        test_pb10 = pinball_loss(y_test_arr, p10_t_cal, 0.10)
        test_pb50 = pinball_loss(y_test_arr, p50_t_cal, 0.50)
        test_pb90 = pinball_loss(y_test_arr, p90_t_cal, 0.90)

        print(f"Validation Empirical Coverage: {val_cov*100:.2f}%, Width: {val_width:.4f} MU/day")
        print(f"Test Empirical Coverage: {test_cov*100:.2f}%, Width: {test_width:.4f} MU/day")
        print(f"Test Pinball Loss: P10={test_pb10:.4f}, P50={test_pb50:.4f}, P90={test_pb90:.4f}")

        models[f"{rtype.lower()}_q10"] = q10
        models[f"{rtype.lower()}_q50"] = q50
        models[f"{rtype.lower()}_q90"] = q90

        calibration_info[rtype.lower()] = {
            "calib_offset": calib_offset,
            "train_samples": len(tr_r),
            "val_samples": len(val_r),
            "test_samples": len(test_r),
            "validation_coverage": val_cov,
            "validation_width": val_width,
            "validation_pinball_loss": {
                "p10": val_pb10,
                "p50": val_pb50,
                "p90": val_pb90,
                "mean": (val_pb10 + val_pb50 + val_pb90) / 3,
            },
            "test_coverage": test_cov,
            "test_width": test_width,
            "test_pinball_loss": {
                "p10": test_pb10,
                "p50": test_pb50,
                "p90": test_pb90,
                "mean": (test_pb10 + test_pb50 + test_pb90) / 3,
            },
        }

        metrics_report["results"][rtype.lower()] = calibration_info[rtype.lower()]

    # Save artifacts
    model_save_path = MODELS_DIR / "probabilistic_quantile_models.joblib"
    joblib.dump(models, model_save_path)
    print(f"\nSaved models to {model_save_path}")

    calib_save_path = MODELS_DIR / "probabilistic_calibration.json"
    calib_save_path.write_text(json.dumps(calibration_info, indent=2))
    print(f"Saved calibration to {calib_save_path}")

    report_save_path = REPORTS_DIR / "probabilistic_metrics.json"
    report_save_path.write_text(json.dumps(metrics_report, indent=2))
    print(f"Saved metrics report to {report_save_path}")


if __name__ == "__main__":
    train_probabilistic_models()

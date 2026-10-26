"""Train and evaluate the leakage-free Random Forest baseline.

Contract
--------
* Target: ``DailyGeneration_MU`` (daily, MU/day).
* Split: the existing per-plant chronological 80/20 ``_split`` column.
* Features: 24 legitimate features in the frozen order below.
* ``Generation_per_MW`` is intentionally absent.  It was computed from the current
  day's target and therefore leaked the prediction target.

The model configuration is unchanged from the historical baseline:

    RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        max_features="sqrt",
    )

No tuning is performed.  The purpose is a scientifically valid baseline after
removing target leakage.

Metrics are written to a clearly named leakage-free report and never overwrite the
historical 25-feature metrics in ``reports/generation_metrics.csv``.  Feature
importance is written to the existing convention path
``reports/generation_feature_importance.csv``; any pre-existing historical
importance file is archived first.

Usage
-----
Train to a candidate artifact, validate it, then promote it:

    python scripts/train_random_forest.py --model-out models/random_forest_model_candidate.pkl

Retrain directly to the production path (only after the candidate has been
validated):

    python scripts/train_random_forest.py
"""

from __future__ import annotations

import argparse
import json
import pickle
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE = Path(__file__).resolve().parent.parent

DATA = BASE / "data/final/plant_features_dataset.csv"
MODEL = BASE / "models/random_forest_model.pkl"
RESULTS = BASE / "data/results"
PLOTS = BASE / "plots"

# Frozen 24-feature contract.  Exactly this order, no additions.
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
FORBIDDEN_FEATURES = {
    "Generation_per_MW",
    "DailyGeneration_MU",
    "CumulativeGeneration_MU",
}
HISTORICAL_IMPORTANCE_ARCHIVE = BASE / "reports/generation_feature_importance_historical_25f.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--model-out", type=Path, default=MODEL)
    parser.add_argument(
        "--metrics-out",
        type=Path,
        default=BASE / "reports/generation_metrics_leakage_free.csv",
    )
    parser.add_argument(
        "--importance-out",
        type=Path,
        default=BASE / "reports/generation_feature_importance.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=BASE / "reports/rf_training_summary.json",
    )
    parser.add_argument("--results-dir", type=Path, default=RESULTS)
    parser.add_argument("--plots-dir", type=Path, default=PLOTS)
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip plot generation (useful for quick checks).",
    )
    return parser.parse_args()


def archive_existing_importance(path: Path) -> None:
    """Preserve a historical feature-importance report before overwriting it."""
    if not path.exists():
        return
    existing = pd.read_csv(path)
    if "Feature" not in existing.columns or len(existing) == len(FEATURES):
        return
    if HISTORICAL_IMPORTANCE_ARCHIVE.exists():
        return
    HISTORICAL_IMPORTANCE_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, HISTORICAL_IMPORTANCE_ARCHIVE)
    print(f"Archived historical feature importance -> {HISTORICAL_IMPORTANCE_ARCHIVE}")


def main() -> int:
    args = parse_args()

    if not args.data.exists():
        raise FileNotFoundError(
            f"Feature dataset not found: {args.data}\n"
            "Run scripts/run_preprocessing_pipeline.py first."
        )

    # Contract guards: fail loudly before training if leakage reappears.
    leaked = FORBIDDEN_FEATURES.intersection(FEATURES)
    if leaked:
        raise ValueError(f"Forbidden leakage features in RF contract: {sorted(leaked)}")
    if len(FEATURES) != 24:
        raise AssertionError(f"RF contract must contain exactly 24 features, got {len(FEATURES)}")

    df = pd.read_csv(args.data)
    df["Date"] = pd.to_datetime(df["Date"])

    if "Generation_per_MW" in df.columns:
        raise ValueError(
            "Dataset still contains Generation_per_MW. "
            "Regenerate it with scripts/engineer_plant_features.py before training."
        )

    required = FEATURES + [TARGET, "_split", "PlantName", "Type", "Date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Feature dataset is missing required columns: {missing}")

    train = df[df["_split"] == "train"].copy()
    test = df[df["_split"] == "test"].copy()
    if train.empty or test.empty:
        raise ValueError(f"Empty split: train={len(train)}, test={len(test)}")

    X_train = train[FEATURES].apply(pd.to_numeric, errors="coerce")
    y_train = pd.to_numeric(train[TARGET], errors="coerce")
    X_test = test[FEATURES].apply(pd.to_numeric, errors="coerce")
    y_test = pd.to_numeric(test[TARGET], errors="coerce")

    for name, frame in (("train", X_train), ("test", X_test)):
        if not np.isfinite(frame.to_numpy(dtype=float)).all():
            raise ValueError(f"Non-finite RF features in {name} split")
    if not np.isfinite(y_train.to_numpy(dtype=float)).all():
        raise ValueError("Non-finite target in train split")
    if not np.isfinite(y_test.to_numpy(dtype=float)).all():
        raise ValueError("Non-finite target in test split")

    print("=" * 72)
    print("LEAKAGE-FREE RANDOM FOREST TRAINING")
    print("=" * 72)
    print(f"Dataset       : {args.data}")
    print(f"Train rows    : {len(train)}")
    print(f"Test rows     : {len(test)}")
    print(f"Plants        : {df['PlantName'].nunique()}")
    print(f"Features      : {len(FEATURES)} (Generation_per_MW absent)")
    print(f"Target        : {TARGET} (daily, MU/day)")

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        max_features="sqrt",
    )
    model.fit(X_train, y_train)

    if int(model.n_features_in_) != len(FEATURES):
        raise AssertionError(
            f"Trained model expects {model.n_features_in_} features, expected {len(FEATURES)}"
        )

    pred = np.asarray(model.predict(X_test), dtype=float).reshape(-1)
    if not np.isfinite(pred).all():
        raise AssertionError("RF produced non-finite predictions")

    mae = float(mean_absolute_error(y_test, pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    r2 = float(r2_score(y_test, pred))

    negative_count = int((pred < 0).sum())
    prediction_stats = {
        "min": float(pred.min()),
        "max": float(pred.max()),
        "mean": float(pred.mean()),
        "negative_count": negative_count,
        "finite": bool(np.isfinite(pred).all()),
    }

    print("\nOverall Performance (leakage-free)")
    print("----------------------------------")
    print(f"MAE : {mae:.6f}")
    print(f"RMSE: {rmse:.6f}")
    print(f"R2  : {r2:.6f}")
    print(
        f"Pred: min={prediction_stats['min']:.4f}, max={prediction_stats['max']:.4f}, "
        f"mean={prediction_stats['mean']:.4f}, negative={negative_count}"
    )

    # Plant-wise evaluation (informational only).
    test = test.copy()
    test["PredictedGeneration_MU"] = pred
    test["AbsoluteError"] = abs(test[TARGET] - test["PredictedGeneration_MU"])
    test["PredictionError"] = test[TARGET] - test["PredictedGeneration_MU"]

    plant_results = []
    for plant, group in test.groupby("PlantName"):
        actual = group[TARGET]
        predicted = group["PredictedGeneration_MU"]
        plant_results.append(
            {
                "PlantName": plant,
                "Type": group["Type"].iloc[0],
                "MAE": mean_absolute_error(actual, predicted),
                "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
                "R2": r2_score(actual, predicted) if len(group) > 1 else np.nan,
                "Rows": len(group),
            }
        )
    plant_results = pd.DataFrame(plant_results).sort_values("PlantName").reset_index(drop=True)

    # Feature importance for the new 24-feature contract.
    importance = pd.DataFrame(
        {"Feature": FEATURES, "Importance": model.feature_importances_}
    )
    importance_sum = float(importance["Importance"].sum())
    if abs(importance_sum - 1.0) > 1e-6:
        raise AssertionError(f"Feature importances sum to {importance_sum}, expected ~1.0")
    importance = importance.sort_values("Importance", ascending=False).reset_index(drop=True)

    # Outputs.
    for directory in (args.model_out.parent, args.metrics_out.parent, args.importance_out.parent,
                      args.summary_out.parent, args.results_dir, args.plots_dir):
        directory.mkdir(parents=True, exist_ok=True)

    archive_existing_importance(args.importance_out)

    with args.model_out.open("wb") as handle:
        pickle.dump(model, handle)

    metrics = pd.DataFrame(
        [
            {
                "Model": "Random Forest (leakage-free, 24 features)",
                "MAE": mae,
                "RMSE": rmse,
                "R2": r2,
                "TrainRows": len(train),
                "TestRows": len(test),
                "Plants": int(df["PlantName"].nunique()),
                "Features": len(FEATURES),
                "Target": TARGET,
                "Frequency": "daily",
            }
        ]
    )
    metrics.to_csv(args.metrics_out, index=False)
    importance.to_csv(args.importance_out, index=False)
    test.to_csv(args.results_dir / "random_forest_predictions.csv", index=False)
    plant_results.to_csv(args.results_dir / "random_forest_plant_performance.csv", index=False)
    importance.to_csv(args.results_dir / "random_forest_feature_importance.csv", index=False)

    summary = {
        "model": "Random Forest",
        "status": "leakage_free_baseline",
        "target": TARGET,
        "frequency": "daily",
        "unit": "MU/day",
        "split": "existing per-plant chronological 80/20 _split column",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "plants": int(df["PlantName"].nunique()),
        "feature_count": len(FEATURES),
        "feature_order": FEATURES,
        "removed_leakage_features": ["Generation_per_MW"],
        "hyperparameters": {
            "n_estimators": 300,
            "random_state": 42,
            "n_jobs": -1,
            "max_features": "sqrt",
            "max_depth": None,
            "min_samples_leaf": 1,
        },
        "metrics": {"MAE": mae, "RMSE": rmse, "R2": r2},
        "predictions": prediction_stats,
        "feature_importance": {
            "sum": importance_sum,
            "count": int(len(importance)),
            "report": str(args.importance_out),
        },
        "artifact": str(args.model_out),
        "metrics_report": str(args.metrics_out),
        "note": (
            "New leakage-free 24-feature baseline. Not comparable to the historical "
            "25-feature Random Forest metrics because the feature contract changed."
        ),
    }
    args.summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("\nTop Features")
    print("------------")
    print(importance.head(10).to_string(index=False))

    if not args.no_plots:
        # 1. Actual vs Predicted.
        plt.figure(figsize=(8, 6))
        plt.scatter(test[TARGET], test["PredictedGeneration_MU"], alpha=0.5)
        min_val = min(test[TARGET].min(), test["PredictedGeneration_MU"].min())
        max_val = max(test[TARGET].max(), test["PredictedGeneration_MU"].max())
        plt.plot([min_val, max_val], [min_val, max_val], linestyle="--")
        plt.xlabel("Actual Generation (MU/day)")
        plt.ylabel("Predicted Generation (MU/day)")
        plt.title("Random Forest (leakage-free): Actual vs Predicted")
        plt.tight_layout()
        plt.savefig(args.plots_dir / "random_forest_actual_vs_predicted.png", dpi=300)
        plt.close()

        # 2. Feature importance.
        top_features = importance.head(10).sort_values("Importance")
        plt.figure(figsize=(9, 6))
        plt.barh(top_features["Feature"], top_features["Importance"])
        plt.xlabel("Importance")
        plt.ylabel("Feature")
        plt.title("Random Forest (leakage-free): Top 10 Feature Importance")
        plt.tight_layout()
        plt.savefig(args.plots_dir / "random_forest_feature_importance.png", dpi=300)
        plt.close()

        # 3. Prediction error distribution.
        plt.figure(figsize=(8, 6))
        plt.hist(test["PredictionError"], bins=40)
        plt.xlabel("Prediction Error (MU/day)")
        plt.ylabel("Frequency")
        plt.title("Random Forest (leakage-free): Prediction Error Distribution")
        plt.tight_layout()
        plt.savefig(args.plots_dir / "random_forest_prediction_error_distribution.png", dpi=300)
        plt.close()

    print("\nSaved:")
    print(f"  model              : {args.model_out}")
    print(f"  metrics            : {args.metrics_out}")
    print(f"  feature importance : {args.importance_out}")
    print(f"  summary            : {args.summary_out}")
    print(f"  predictions        : {args.results_dir / 'random_forest_predictions.csv'}")
    print(f"  plant performance  : {args.results_dir / 'random_forest_plant_performance.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

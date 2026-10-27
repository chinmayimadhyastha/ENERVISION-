"""Model metrics and feature-importance reporting.

Metrics come from the committed manifest/report files.  The historical leaked
25-feature Random Forest metrics and importances are kept in a separately named
block and explicitly marked as not comparable to the current 24-feature model.
"""

from __future__ import annotations

import pandas as pd

from backend.utils.errors import ApiError

CURRENT_IMPORTANCE_METHOD = "random_forest_impurity"

METRIC_DEFINITIONS = {
    "MAE": "Mean absolute error in MU/day on the chronological test split.",
    "RMSE": "Root mean squared error in MU/day on the chronological test split.",
    "R2": "Coefficient of determination on the chronological test split.",
}

COMPARISON_POLICY = {
    "historical_25_feature_metrics_comparable_to_current": False,
    "reason": (
        "The historical Random Forest used the leaked Generation_per_MW feature and a "
        "different dataset/split that is not present in the repository. Its metrics are "
        "preserved for provenance only and must not be compared with the current model."
    ),
    "current_random_forest_features": 24,
    "historical_random_forest_features": 25,
}


class ModelReportService:
    def __init__(self, config, contracts: dict) -> None:
        self.config = config
        self.contracts = contracts
        self.models: dict[str, dict] = contracts["models"]

    # ------------------------------------------------------------- performance
    def performance(self) -> dict:
        rf = self.models["random_forest_daily"]
        solar = self.models["solar_lstm_daily"]
        wind = self.models["wind_lstm_daily"]

        historical = dict(
            rf.get("metrics", {}).get("historical_committed_metrics_25f", {})
        )
        historical["comparable_to_current_24_feature_model"] = False
        historical["leakage_affected"] = True
        historical["usage"] = "provenance_only"

        current = dict(rf.get("metrics", {}).get("leakage_free_metrics_24f", {}))

        return {
            "frequency": self.config.FREQUENCY,
            "target": self.config.TARGET,
            "unit": self.config.TARGET_UNIT,
            "metric_definitions": dict(METRIC_DEFINITIONS),
            "comparison_policy": dict(COMPARISON_POLICY),
            "models": {
                "random_forest": {
                    "model_id": rf["id"],
                    "display_name": rf.get("display_name"),
                    "family": "random_forest",
                    "status": rf.get("status"),
                    "frequency": rf.get("frequency"),
                    "target": rf.get("target"),
                    "feature_count": rf.get("feature_count"),
                    "metrics": {
                        "current_leakage_free_24_feature": current,
                        "historical_25_feature_reference": historical,
                    },
                    "evaluation_split": rf.get("train_test_split"),
                    "training_date_range": rf.get("training_date_range"),
                    "test_date_range": rf.get("test_date_range"),
                    "prediction_stats": rf.get("prediction_stats"),
                    "source_metrics_file": "reports/generation_metrics_leakage_free.csv",
                    "source_historical_metrics_file": "reports/generation_metrics.csv",
                    "notes": list(rf.get("notes", [])),
                },
                "solar_lstm": {
                    "model_id": solar["id"],
                    "display_name": solar.get("display_name"),
                    "family": "lstm",
                    "status": solar.get("status"),
                    "frequency": solar.get("frequency"),
                    "target": solar.get("target"),
                    "feature_count": solar.get("feature_count"),
                    "sequence_length": solar.get("sequence_length"),
                    "metrics": {
                        "committed_actual": dict(solar.get("evaluation_metrics", {})),
                        "regenerated_pipeline_reference": dict(
                            solar.get("regenerated_pipeline_metrics", {})
                        ),
                    },
                    "evaluation_split": solar.get("train_test_split"),
                    "training_date_range": solar.get("training_date_range"),
                    "test_date_range": solar.get("test_date_range"),
                    "source_metrics_file": "reports/lstm_metrics.csv",
                    "notes": list(solar.get("notes", [])),
                },
                "wind_lstm": {
                    "model_id": wind["id"],
                    "display_name": wind.get("display_name"),
                    "family": "lstm",
                    "status": wind.get("status"),
                    "frequency": wind.get("frequency"),
                    "target": wind.get("target"),
                    "feature_count": wind.get("feature_count"),
                    "sequence_length": wind.get("sequence_length"),
                    "metrics": {
                        "committed_actual": dict(wind.get("evaluation_metrics", {})),
                        "regenerated_pipeline_reference": dict(
                            wind.get("regenerated_pipeline_metrics", {})
                        ),
                    },
                    "evaluation_split": wind.get("train_test_split"),
                    "training_date_range": wind.get("training_date_range"),
                    "test_date_range": wind.get("test_date_range"),
                    "source_metrics_file": "reports/lstm_metrics.csv",
                    "notes": list(wind.get("notes", [])),
                },
            },
            "notes": [
                "Current Random Forest metrics come from the leakage-free 24-feature "
                "artifact and its chronological per-plant split.",
                "Historical 25-feature metrics are reported only as provenance and are "
                "not comparable to the current model.",
                "LSTM metrics are the committed actuals. Regenerated-pipeline values are "
                "reported separately and are not a reproduction of the committed metric.",
                "No metric on this endpoint is synthesised or interpolated.",
            ],
        }

    # ------------------------------------------------------- feature importance
    def feature_importance(self) -> dict:
        path = self.config.FEATURE_IMPORTANCE_PATH
        if not path.exists():
            raise ApiError(
                "REPORT_UNAVAILABLE",
                (
                    "The Random Forest feature-importance report is missing. "
                    "Restore reports/generation_feature_importance.csv."
                ),
                503,
                {"path": str(path)},
            )

        try:
            frame = pd.read_csv(path)
        except Exception as exc:
            raise ApiError(
                "REPORT_INVALID",
                "The feature-importance report could not be read.",
                503,
                {"path": str(path)},
            ) from exc

        required = {"Feature", "Importance"}
        if not required.issubset(frame.columns) or frame.empty:
            raise ApiError(
                "REPORT_INVALID",
                "The feature-importance report must contain Feature and Importance columns.",
                503,
                {"columns": list(frame.columns)},
            )
        if "Generation_per_MW" in set(frame["Feature"]):
            raise ApiError(
                "REPORT_INVALID",
                (
                    "The feature-importance report contains Generation_per_MW, which "
                    "leaked the prediction target."
                ),
                503,
            )
        if len(frame) != self.config.RF_FEATURE_COUNT:
            raise ApiError(
                "REPORT_INVALID",
                (
                    f"The feature-importance report contains {len(frame)} features; "
                    f"the current contract requires {self.config.RF_FEATURE_COUNT}."
                ),
                503,
            )

        frame = frame.sort_values("Importance", ascending=False).reset_index(drop=True)
        total = float(frame["Importance"].sum())
        features = [
            {
                "rank": index + 1,
                "feature": str(row.Feature),
                "importance": float(row.Importance),
            }
            for index, row in enumerate(frame.itertuples(index=False))
        ]

        payload = {
            "model_id": "random_forest_daily",
            "frequency": self.config.FREQUENCY,
            "target": self.config.TARGET,
            "method": CURRENT_IMPORTANCE_METHOD,
            "method_description": (
                "Mean decrease in impurity (Gini importance) from the fitted "
                "scikit-learn RandomForestRegressor. This is not SHAP and not permutation "
                "importance."
            ),
            "shap_used": False,
            "feature_count": len(features),
            "importance_sum": total,
            "features": features,
            "notes": [
                "Impurity importance is model-internal and can favour continuous or "
                "high-cardinality features.",
                "No SHAP values exist in this repository and none are claimed here.",
                "Generation_per_MW is absent because it leaked the prediction target.",
            ],
        }

        historical_path = self.config.REPORTS_DIR / (
            "generation_feature_importance_historical_25f.csv"
        )
        if historical_path.exists():
            historical_frame = pd.read_csv(historical_path)
            if {"Feature", "Importance"}.issubset(historical_frame.columns):
                historical_frame = historical_frame.sort_values(
                    "Importance", ascending=False
                ).reset_index(drop=True)
                payload["historical_25_feature_reference"] = {
                    "method": CURRENT_IMPORTANCE_METHOD,
                    "leakage_affected": True,
                    "comparable_to_current": False,
                    "features": [
                        {
                            "rank": index + 1,
                            "feature": str(row.Feature),
                            "importance": float(row.Importance),
                        }
                        for index, row in enumerate(
                            historical_frame.itertuples(index=False)
                        )
                    ],
                    "note": (
                        "Historical importances from the removed 25-feature model. They "
                        "include Generation_per_MW and are not comparable to the current "
                        "24-feature model."
                    ),
                }
        return payload

"""Model artifact loading and inference.

The Random Forest, both LSTMs and all four scalers are loaded exactly once at
application startup.  Any missing or incompatible artifact aborts startup; the
backend never substitutes a mock model.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd

from backend.services.probabilistic_service import ProbabilisticService
from backend.utils.errors import ApiError, ArtifactError

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


@dataclass(frozen=True)
class RfPrediction:
    raw: float
    served: float
    clamp_applied: bool
    confidence: dict | None = None
    explanation: list[dict] | None = None
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None


@dataclass(frozen=True)
class LstmPrediction:
    raw: float
    served: float
    clamp_applied: bool
    confidence: dict | None = None
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None


class ModelService:
    """Holds the production models and enforces their inference contracts."""

    def __init__(self, config, contracts: dict, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.contracts = contracts
        self.logger = logger or logging.getLogger("enervision.models")

        self.rf_features: list[str] = contracts["rf_features"]
        self.lstm_features: list[str] = contracts["lstm_features"]
        self.lstm_column_map: dict[str, str] = contracts["lstm_column_map"]
        self.sequence_length: int = contracts["sequence_length"]
        self.model_metadata: dict[str, dict] = contracts["models"]

        self.rf = None
        self.solar_lstm = None
        self.wind_lstm = None
        self.solar_feature_scaler = None
        self.solar_target_scaler = None
        self.wind_feature_scaler = None
        self.wind_target_scaler = None
        self.probabilistic = ProbabilisticService(config, logger=self.logger)
        self.loaded = False
        self.load_durations: dict[str, float] = {}

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        self._require_artifacts()
        self._load_random_forest()
        self._load_scalers()
        self._load_lstms()
        self.probabilistic.load()
        self.loaded = True
        self.logger.info("All production model artifacts loaded and contract-validated.")

    def _require_artifacts(self) -> None:
        missing = [
            f"{name}: {path}"
            for name, path in self.config.artifact_paths().items()
            if not path.exists()
        ]
        if missing:
            raise ArtifactError(
                "Required production artifacts are missing:\n  "
                + "\n  ".join(missing)
                + "\nRestore the frozen model artifacts before starting the API."
            )

    def _load_random_forest(self) -> None:
        started = time.time()
        path = self.config.RF_MODEL_PATH
        try:
            self.rf = joblib.load(path)
        except Exception as exc:
            raise ArtifactError(
                f"Random Forest artifact could not be loaded: {path} ({exc}). "
                "It must be loadable with scikit-learn 1.6.1."
            ) from exc

        n_features = getattr(self.rf, "n_features_in_", None)
        if n_features != self.config.RF_FEATURE_COUNT:
            raise ArtifactError(
                f"Random Forest expects {n_features!r} features; "
                f"the frozen contract requires {self.config.RF_FEATURE_COUNT}."
            )
        if not hasattr(self.rf, "predict"):
            raise ArtifactError("The Random Forest artifact has no predict method.")

        actual_names = list(getattr(self.rf, "feature_names_in_", []))
        if actual_names and actual_names != self.rf_features:
            raise ArtifactError(
                "Random Forest feature_names_in_ does not match the manifest order.\n"
                f"model:    {actual_names}\nmanifest: {self.rf_features}"
            )
        if "Generation_per_MW" in actual_names:
            raise ArtifactError(
                "The loaded Random Forest uses Generation_per_MW, which leaks the target."
            )

        self.load_durations["random_forest"] = round(time.time() - started, 3)
        self.logger.info(
            "Random Forest loaded in %.2fs with %s features.",
            self.load_durations["random_forest"],
            n_features,
        )

    def _load_scalers(self) -> None:
        started = time.time()
        self.solar_feature_scaler = self._load_scaler(
            self.config.SOLAR_FEATURE_SCALER_PATH,
            expected_features=12,
            expected_names=self.lstm_features,
        )
        self.solar_target_scaler = self._load_scaler(
            self.config.SOLAR_TARGET_SCALER_PATH,
            expected_features=1,
            expected_names=[self.config.TARGET],
        )
        self.wind_feature_scaler = self._load_scaler(
            self.config.WIND_FEATURE_SCALER_PATH,
            expected_features=12,
            expected_names=self.lstm_features,
        )
        self.wind_target_scaler = self._load_scaler(
            self.config.WIND_TARGET_SCALER_PATH,
            expected_features=1,
            expected_names=[self.config.TARGET],
        )
        self.load_durations["scalers"] = round(time.time() - started, 3)
        self.logger.info(
            "Four LSTM scalers loaded in %.2fs.", self.load_durations["scalers"]
        )

    def _load_scaler(self, path, expected_features: int, expected_names: list[str]):
        try:
            scaler = joblib.load(path)
        except Exception as exc:
            raise ArtifactError(f"Scaler artifact could not be loaded: {path} ({exc})") from exc
        if not hasattr(scaler, "transform") or not hasattr(scaler, "inverse_transform"):
            raise ArtifactError(f"Artifact is not a usable scaler: {path}")
        n_features = getattr(scaler, "n_features_in_", None)
        if n_features != expected_features:
            raise ArtifactError(
                f"Scaler {path.name} expects {n_features!r} features; "
                f"expected {expected_features}."
            )
        names = list(getattr(scaler, "feature_names_in_", []))
        if names and names != expected_names:
            raise ArtifactError(
                f"Scaler {path.name} was fitted on feature names {names}; "
                f"the manifest contract requires {expected_names}."
            )
        return scaler

    def _load_lstms(self) -> None:
        started = time.time()
        try:
            import keras  # imported lazily so tests can inspect imports cleanly
        except Exception as exc:
            raise ArtifactError(
                "TensorFlow/Keras could not be imported. The LSTM artifacts require "
                "tensorflow==2.19.0 and keras==3.10.0."
            ) from exc

        self.solar_lstm = self._load_keras_model(keras, self.config.SOLAR_MODEL_PATH)
        self.wind_lstm = self._load_keras_model(keras, self.config.WIND_MODEL_PATH)
        self.load_durations["lstms"] = round(time.time() - started, 3)
        self.logger.info("Solar and Wind LSTMs loaded in %.2fs.", self.load_durations["lstms"])

    def _load_keras_model(self, keras, path):
        try:
            model = keras.models.load_model(path, compile=False)
        except Exception as exc:
            raise ArtifactError(f"Keras model could not be loaded: {path} ({exc})") from exc

        input_shape = tuple(model.input_shape)
        if (
            len(input_shape) != 3
            or input_shape[1] != self.sequence_length
            or input_shape[2] != self.config.LSTM_FEATURE_COUNT
        ):
            raise ArtifactError(
                f"Keras model {path.name} has input shape {input_shape}; "
                f"expected (None, {self.sequence_length}, "
                f"{self.config.LSTM_FEATURE_COUNT})."
            )
        output_shape = tuple(model.output_shape)
        if output_shape != (None, 1):
            raise ArtifactError(
                f"Keras model {path.name} has output shape {output_shape}; "
                "expected (None, 1)."
            )
        return model

    # -------------------------------------------------------------- inference
    def predict_rf(
        self,
        features,
        renewable_type: str = "Solar",
        plant_capacity_mw: float | None = None,
    ) -> RfPrediction:
        if not self.loaded or self.rf is None:
            raise ApiError(
                "MODEL_SERVICE_UNAVAILABLE",
                "The Random Forest model is not loaded.",
                503,
            )
        vector = np.asarray(features, dtype=float)
        if vector.shape != (self.config.RF_FEATURE_COUNT,):
            raise ApiError(
                "INVALID_FEATURE_VECTOR",
                f"Random Forest inference requires {self.config.RF_FEATURE_COUNT} features; "
                f"received shape {vector.shape}.",
                500,
            )
        if not np.isfinite(vector).all():
            raise ApiError(
                "INVALID_FEATURE_VECTOR",
                "Random Forest inference received a non-finite feature value.",
                500,
            )

        raw = float(
            np.asarray(
                self.rf.predict(pd.DataFrame([vector], columns=self.rf_features))
            ).reshape(-1)[0]
        )
        if not np.isfinite(raw):
            raise ApiError(
                "MODEL_INFERENCE_FAILED",
                "The Random Forest produced a non-finite prediction.",
                500,
            )
        served = max(raw, 0.0)

        # Calibrated Quantile Regression (P10, P50, P90)
        prob = self.probabilistic.predict_quantiles(
            features=vector,
            feature_names=self.rf_features,
            renewable_type=renewable_type,
            plant_capacity_mw=plant_capacity_mw,
            point_prediction=served,
        )
        confidence = prob.as_confidence_dict()
        tree_preds = np.array([tree.predict(vector.reshape(1, -1))[0] for tree in self.rf.estimators_])
        confidence["std_dev"] = round(float(np.std(tree_preds)), 4)

        # Local tree-based explainability (feature contribution decomposition)
        explanation = self.explain_rf_prediction(vector)

        return RfPrediction(
            raw=raw,
            served=served,
            clamp_applied=raw < 0.0,
            confidence=confidence,
            explanation=explanation,
            p10=prob.p10,
            p50=prob.p50,
            p90=prob.p90,
        )

    def explain_rf_prediction(self, features) -> list[dict]:
        """Compute local feature contributions across all decision trees in the random forest."""
        vector = np.asarray(features, dtype=float).reshape(1, -1)
        contributions = np.zeros(len(self.rf_features))

        for tree in self.rf.estimators_:
            t = tree.tree_
            nodes = tree.decision_path(vector).indices
            for i in range(len(nodes) - 1):
                curr_node, next_node = nodes[i], nodes[i + 1]
                contributions[t.feature[curr_node]] += (t.value[next_node][0][0] - t.value[curr_node][0][0])
        contributions /= len(self.rf.estimators_)

        ranked_indices = np.argsort(-np.abs(contributions))
        explanations = []
        for rank, idx in enumerate(ranked_indices, start=1):
            feat_name = self.rf_features[idx]
            val = float(vector[0, idx])
            contrib = float(contributions[idx])
            explanations.append({
                "feature": feat_name,
                "value": round(val, 4),
                "impact": round(contrib, 4),
                "direction": "positive" if contrib >= 0 else "negative",
                "rank": rank,
            })
        return explanations

    def predict_lstm(
        self,
        renewable_type: str,
        sequence,
        plant_capacity_mw: float | None = None,
    ) -> LstmPrediction:
        if not self.loaded:
            raise ApiError(
                "MODEL_SERVICE_UNAVAILABLE",
                "The LSTM models are not loaded.",
                503,
            )
        model, feature_scaler, target_scaler = self._lstm_bundle(renewable_type)

        window = np.asarray(sequence, dtype=float)
        expected = (self.sequence_length, self.config.LSTM_FEATURE_COUNT)
        if window.shape != expected:
            raise ApiError(
                "INVALID_SEQUENCE_SHAPE",
                f"{renewable_type} LSTM inference requires shape {expected}; "
                f"received {window.shape}.",
                500,
            )
        if not np.isfinite(window).all():
            raise ApiError(
                "INVALID_SEQUENCE_SHAPE",
                f"{renewable_type} LSTM inference received non-finite feature values.",
                500,
            )

        feature_names = list(getattr(feature_scaler, "feature_names_in_", []))
        scaled = feature_scaler.transform(
            pd.DataFrame(window, columns=feature_names) if feature_names else window
        )
        prediction = model.predict(scaled.reshape(1, *expected), verbose=0)
        scaled_target = float(np.asarray(prediction).reshape(-1)[0])
        target_names = list(getattr(target_scaler, "feature_names_in_", []))
        target_input = (
            pd.DataFrame([[scaled_target]], columns=target_names)
            if target_names
            else np.asarray([[scaled_target]], dtype=float)
        )
        raw = float(target_scaler.inverse_transform(target_input)[0, 0])
        if not np.isfinite(raw):
            raise ApiError(
                "MODEL_INFERENCE_FAILED",
                f"The {renewable_type} LSTM produced a non-finite prediction.",
                500,
            )

        # Serving-layer physical constraint.  The neural network is not
        # constrained to non-negative outputs; the raw value is preserved.
        served = max(raw, 0.0)

        # Calibrated Probabilistic Quantiles (P10, P50, P90)
        prob = self.probabilistic.predict_quantiles(
            features=None,
            feature_names=[],
            renewable_type=renewable_type,
            plant_capacity_mw=plant_capacity_mw,
            point_prediction=served,
        )
        confidence = prob.as_confidence_dict()
        rmse = 0.2346 if renewable_type.lower() == "solar" else 1.0040
        confidence["std_dev"] = round(rmse, 4)

        return LstmPrediction(
            raw=raw,
            served=served,
            clamp_applied=raw < 0.0,
            confidence=confidence,
            p10=prob.p10,
            p50=prob.p50,
            p90=prob.p90,
        )

    def _lstm_bundle(self, renewable_type: str):
        key = str(renewable_type).strip().lower()
        if key == "solar":
            return self.solar_lstm, self.solar_feature_scaler, self.solar_target_scaler
        if key == "wind":
            return self.wind_lstm, self.wind_feature_scaler, self.wind_target_scaler
        raise ApiError(
            "UNSUPPORTED_PLANT_TYPE",
            f"No LSTM model exists for plant type {renewable_type!r}.",
            422,
            {"type": renewable_type, "supported_types": ["Solar", "Wind"]},
        )

    # ----------------------------------------------------------------- status
    def status(self) -> dict:
        return {
            "random_forest": "loaded" if self.rf is not None else "unavailable",
            "solar_lstm": "loaded" if self.solar_lstm is not None else "unavailable",
            "wind_lstm": "loaded" if self.wind_lstm is not None else "unavailable",
            "solar_feature_scaler": "loaded"
            if self.solar_feature_scaler is not None
            else "unavailable",
            "solar_target_scaler": "loaded"
            if self.solar_target_scaler is not None
            else "unavailable",
            "wind_feature_scaler": "loaded"
            if self.wind_feature_scaler is not None
            else "unavailable",
            "wind_target_scaler": "loaded"
            if self.wind_target_scaler is not None
            else "unavailable",
        }

    def contract_summary(self) -> dict:
        return {
            "random_forest": {
                "model_id": "random_forest_daily",
                "feature_count": len(self.rf_features),
                "feature_order": list(self.rf_features),
                "target": self.config.TARGET,
                "frequency": self.config.FREQUENCY,
                "unit": self.config.TARGET_UNIT,
                "forbidden_features": ["Generation_per_MW"],
                "requires_target_day_weather": True,
                "requires_prediction_day_target": False,
            },
            "lstm": {
                "model_ids": ["solar_lstm_daily", "wind_lstm_daily"],
                "feature_count": len(self.lstm_features),
                "feature_order": list(self.lstm_features),
                "sequence_length": self.sequence_length,
                "target": self.config.TARGET,
                "frequency": self.config.FREQUENCY,
                "unit": self.config.TARGET_UNIT,
                "column_map": dict(self.lstm_column_map),
                "requires_target_day_weather": False,
                "target_day_weather_note": (
                    "The training sequence is the seven feature rows preceding the target "
                    "date. Target-day weather is not an input. Multi-step rollout needs "
                    "weather for intermediate predicted days."
                ),
            },
        }

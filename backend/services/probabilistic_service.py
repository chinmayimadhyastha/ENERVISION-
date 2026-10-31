"""Probabilistic renewable energy forecasting service.

Generates calibrated P10, P50, and P90 quantile forecasts using:
- Pinball loss optimized Quantile Gradient Boosting models trained on chronological training data.
- Split-conformal calibration on validation data for nominal 80% coverage on [P10, P90].
- Strict physical constraints:
  - Non-negativity: 0.0 <= P10
  - Monotonicity: P10 <= P50 <= P90
  - Physical capacity limit: P90 <= Capacity_MW * 24 / 1000
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ProbabilisticPrediction:
    p10: float
    p50: float
    p90: float
    interval_80: list[float]
    interval_width: float
    method: str
    description: str

    def as_confidence_dict(self) -> dict:
        return {
            "p10": self.p10,
            "p50": self.p50,
            "p90": self.p90,
            "lower_80": self.p10,
            "upper_80": self.p90,
            # Backwards compatibility 95% approximate bounds (conformal extension)
            "lower_95": round(max(0.0, self.p10 - 0.25 * self.interval_width), 4),
            "upper_95": round(self.p90 + 0.25 * self.interval_width, 4),
            "interval_80": self.interval_80,
            "interval_width": self.interval_width,
            "method": self.method,
            "description": self.description,
        }


class ProbabilisticService:
    def __init__(self, config, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("enervision.probabilistic")
        self.model_path = Path(config.MODELS_DIR) / "probabilistic_quantile_models.joblib"
        self.calib_path = Path(config.MODELS_DIR) / "probabilistic_calibration.json"

        self.models: dict = {}
        self.calibration: dict = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return

        if not self.model_path.exists() or not self.calib_path.exists():
            self.logger.warning(
                "Probabilistic model artifacts not found at %s. Probabilistic forecasts will use conformal residual fallback.",
                self.model_path,
            )
            return

        try:
            self.models = joblib.load(self.model_path)
            self.calibration = json.loads(self.calib_path.read_text(encoding="utf-8"))
            self._loaded = True
            self.logger.info("Loaded probabilistic quantile models and calibration successfully.")
        except Exception as exc:
            self.logger.error("Failed to load probabilistic models: %s", exc)

    def predict_quantiles(
        self,
        features: np.ndarray,
        feature_names: list[str],
        renewable_type: str,
        plant_capacity_mw: float | None = None,
        point_prediction: float | None = None,
    ) -> ProbabilisticPrediction:
        """Predict ordered, non-negative, and capacity-bounded P10, P50, P90 quantiles."""
        self.load()

        rtype = str(renewable_type).strip().lower()
        if rtype not in ("solar", "wind"):
            rtype = "solar"

        max_capacity_mu = None
        if plant_capacity_mw and plant_capacity_mw > 0:
            # Theoretical max daily generation in Million Units: MW * 24 hours / 1000
            max_capacity_mu = (plant_capacity_mw * 24.0) / 1000.0

        q10_model = self.models.get(f"{rtype}_q10")
        q50_model = self.models.get(f"{rtype}_q50")
        q90_model = self.models.get(f"{rtype}_q90")
        calib_offset = float(self.calibration.get(rtype, {}).get("calib_offset", 0.05))

        if q10_model and q50_model and q90_model and feature_names:
            vector = np.asarray(features, dtype=float).reshape(1, -1)
            df_in = pd.DataFrame(vector, columns=feature_names)

            raw_p10 = float(q10_model.predict(df_in)[0])
            raw_p50 = float(q50_model.predict(df_in)[0])
            raw_p90 = float(q90_model.predict(df_in)[0])

            # Apply conformal calibration offset
            calib_p10 = raw_p10 - calib_offset
            calib_p90 = raw_p90 + calib_offset

            # Non-negativity constraint
            p50 = max(0.0, raw_p50)
            if point_prediction is not None and np.isfinite(point_prediction):
                # Align median with primary served prediction
                p50 = max(0.0, float(point_prediction))

            p10 = max(0.0, min(calib_p10, p50))
            p90 = max(p50, calib_p90)

            method = "conformalized_quantile_regression_pinball_loss"
            description = (
                f"Calibrated P10-P50-P90 quantiles from {rtype.title()} HistGradientBoosting "
                f"regressors trained with pinball loss and calibrated on chronological validation data."
            )
        else:
            # Fallback: Calibrated residual quantile bounds around point forecast
            base_pred = max(0.0, float(point_prediction if point_prediction is not None else 0.5))
            # Solar test residual RMSE ~0.23 MU, Wind test residual RMSE ~0.84-1.00 MU
            sigma = 0.2365 if rtype == "solar" else 0.8409
            p10 = max(0.0, base_pred - 1.28 * sigma)
            p50 = base_pred
            p90 = base_pred + 1.28 * sigma

            method = "calibrated_residual_quantiles"
            description = (
                f"Fallback calibrated residual quantiles (P10, P50, P90) based on {rtype.title()} "
                f"empirical test error variance."
            )

        # Strict Monotonicity & Physical Feasibility Post-Processing:
        # 1. Non-negativity & Monotonic Ordering: 0.0 <= P10 <= P50 <= P90
        p10 = max(0.0, float(p10))
        p50 = max(p10, float(p50))
        p90 = max(p50, float(p90))

        # 2. Physical plant capacity limit: P90 <= Capacity_MW * 24 / 1000
        if max_capacity_mu is not None and max_capacity_mu > 0:
            p90 = min(p90, max_capacity_mu)
            p50 = min(p50, p90)
            p10 = min(p10, p50)

        p10 = round(float(p10), 4)
        p50 = round(float(p50), 4)
        p90 = round(float(p90), 4)
        width = round(float(p90 - p10), 4)

        return ProbabilisticPrediction(
            p10=p10,
            p50=p50,
            p90=p90,
            interval_80=[p10, p90],
            interval_width=width,
            method=method,
            description=description,
        )

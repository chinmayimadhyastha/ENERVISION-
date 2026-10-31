"""Model performance, registry, and feature-importance endpoints."""

from __future__ import annotations

import pandas as pd
from flask import Blueprint, current_app, jsonify, request

from backend.services.feature_builder import WEATHER_FIELDS
from backend.utils.errors import ApiError
from backend.utils.serialization import to_jsonable
from backend.utils.validation import parse_plant_id

bp = Blueprint("models", __name__, url_prefix="/api")


@bp.get("/model-performance")
def model_performance():
    container = current_app.extensions["enervision"]
    return jsonify(to_jsonable(container.reports.performance()))


@bp.get("/feature-importance")
def feature_importance():
    container = current_app.extensions["enervision"]
    return jsonify(to_jsonable(container.reports.feature_importance()))


@bp.get("/models")
def list_models():
    container = current_app.extensions["enervision"]
    manifest = container.manifest
    raw_models = manifest.get("models", [])
    if isinstance(raw_models, dict):
        models_list = list(raw_models.values())
    else:
        models_list = list(raw_models)

    results = []
    for meta in models_list:
        m_id = meta.get("id", meta.get("model_id"))
        metrics = meta.get("metrics", meta.get("evaluation_metrics", {}))
        results.append({
            "model_id": m_id,
            "name": meta.get("display_name", meta.get("name", m_id)),
            "algorithm": meta.get("model_type", meta.get("algorithm", "Unknown")),
            "family": meta.get("family", "lstm" if "lstm" in str(m_id) else "random_forest"),
            "status": meta.get("status", "production"),
            "feature_count": meta.get("feature_count", 0),
            "sequence_length": meta.get("sequence_length"),
            "metrics": metrics,
            "artifact_path": meta.get("artifact_path", ""),
        })
    return jsonify({"count": len(results), "models": results})


@bp.get("/models/<model_id>")
def get_model(model_id: str):
    container = current_app.extensions["enervision"]
    raw_models = container.manifest.get("models", [])
    if isinstance(raw_models, dict):
        models_dict = raw_models
    else:
        models_dict = {m.get("id", m.get("model_id")): m for m in raw_models}

    # Support shorthand alias lookups
    alias_map = {
        "random_forest": "random_forest_daily",
        "rf": "random_forest_daily",
        "solar_lstm": "solar_lstm_daily",
        "wind_lstm": "wind_lstm_daily",
    }
    target_id = alias_map.get(model_id, model_id)

    if target_id not in models_dict:
        raise ApiError("MODEL_NOT_FOUND", f"Model {model_id!r} not found in model registry.", 404)
    meta = models_dict[target_id]
    return jsonify({"model_id": target_id, **meta})


@bp.get("/explainability/<plant_id>")
def explainability_by_plant(plant_id: str):
    container = current_app.extensions["enervision"]
    pid = parse_plant_id(plant_id)
    plant = container.data.require_plant(pid)
    frame = container.data.get_frame(plant.plant_name)
    base_date = plant.last_observed_date
    observed = frame[frame["Date"] <= pd.Timestamp(base_date)].sort_values("Date")
    if len(observed) < 7:
        raise ApiError("INSUFFICIENT_HISTORY", "Plant has insufficient history for feature explanation.", 400)

    last_observed = observed.iloc[-1]
    capacity_mw = float(last_observed["Capacity_MW"])
    weather_payload = {f: float(last_observed[f]) for f in WEATHER_FIELDS}
    prev_observed = observed.iloc[-2] if len(observed) >= 2 else last_observed
    previous_weather = {f: float(prev_observed[f]) for f in WEATHER_FIELDS}
    generation_history = [float(v) for v in observed["DailyGeneration_MU"].tolist()[-7:]]

    vector = container.feature_builder.rf_row(
        base_date,
        capacity_mw,
        weather_payload,
        previous_weather,
        generation_history,
    )
    explanations = container.models.explain_rf_prediction(vector)
    return jsonify({
        "plant_id": plant.plant_id,
        "plant_name": plant.plant_name,
        "base_date": base_date.isoformat(),
        "model": "random_forest_daily",
        "method": "tree_path_decomposition",
        "description": "Local feature contributions across decision trees for the latest observed feature vector.",
        "top_features": explanations[:10],
        "all_features": explanations,
    })

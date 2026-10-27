"""Model performance and feature-importance endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from backend.utils.serialization import to_jsonable

bp = Blueprint("models", __name__, url_prefix="/api")


@bp.get("/model-performance")
def model_performance():
    container = current_app.extensions["enervision"]
    return jsonify(to_jsonable(container.reports.performance()))


@bp.get("/feature-importance")
def feature_importance():
    container = current_app.extensions["enervision"]
    return jsonify(to_jsonable(container.reports.feature_importance()))

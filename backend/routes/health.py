"""Health endpoint."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from backend.utils.serialization import to_jsonable

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    container = current_app.extensions["enervision"]
    return jsonify(to_jsonable(container.health()))

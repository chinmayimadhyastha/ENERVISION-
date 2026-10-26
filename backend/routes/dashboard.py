"""Dashboard summary endpoint."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from backend.utils.serialization import to_jsonable

bp = Blueprint("dashboard", __name__, url_prefix="/api")


@bp.get("/dashboard")
def dashboard():
    container = current_app.extensions["enervision"]
    return jsonify(to_jsonable(container.analytics.dashboard()))

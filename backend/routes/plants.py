"""Plant catalogue and plant detail endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.utils.serialization import to_jsonable
from backend.utils.validation import parse_limit

bp = Blueprint("plants", __name__, url_prefix="/api")


@bp.get("/plants")
def list_plants():
    container = current_app.extensions["enervision"]
    payload = container.plants.list_plants(
        type_filter=request.args.get("type"),
        district=request.args.get("district"),
    )
    return jsonify(to_jsonable(payload))


@bp.get("/plants/<plant_id>")
def plant_detail(plant_id: str):
    container = current_app.extensions["enervision"]
    limit = parse_limit(
        request.args.get("history_limit"),
        name="history_limit",
        default=container.config.DEFAULT_HISTORY_LIMIT,
        minimum=1,
        maximum=container.config.MAX_HISTORY_LIMIT,
    )
    payload = container.plants.detail(plant_id, history_limit=limit)
    return jsonify(to_jsonable(payload))

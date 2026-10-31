"""Observed daily generation history, plant-level or aggregated."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.utils.serialization import to_jsonable
from backend.utils.validation import (
    optional_text,
    parse_date_range,
    parse_plant_id,
)

bp = Blueprint("history", __name__, url_prefix="/api")


@bp.get("/generation-history")
@bp.get("/generation")
def generation_history():
    container = current_app.extensions["enervision"]
    raw_plant_id = optional_text(request.args.get("plant_id"))
    plant_id = parse_plant_id(raw_plant_id) if raw_plant_id else None
    start, end = parse_date_range(
        request.args.get("start_date"), request.args.get("end_date")
    )
    payload = container.plants.generation_history(
        plant_id=plant_id,
        type_filter=request.args.get("type"),
        start=start,
        end=end,
    )
    return jsonify(to_jsonable(payload))


@bp.get("/generation/history")
def generation_history_alias():
    return generation_history()


@bp.get("/generation/<plant_id>")
def generation_by_plant(plant_id: str):
    container = current_app.extensions["enervision"]
    pid = parse_plant_id(plant_id)
    start, end = parse_date_range(
        request.args.get("start_date"), request.args.get("end_date")
    )
    payload = container.plants.generation_history(
        plant_id=pid,
        type_filter=request.args.get("type"),
        start=start,
        end=end,
    )
    return jsonify(to_jsonable(payload))

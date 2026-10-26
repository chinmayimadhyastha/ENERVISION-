"""Descriptive analytics endpoint."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.utils.serialization import to_jsonable
from backend.utils.validation import (
    optional_text,
    parse_date_range,
    parse_plant_id,
)

bp = Blueprint("analytics", __name__, url_prefix="/api")


@bp.get("/analytics")
def analytics():
    container = current_app.extensions["enervision"]
    raw_plant_id = optional_text(request.args.get("plant_id"))
    plant_id = parse_plant_id(raw_plant_id) if raw_plant_id else None
    start, end = parse_date_range(
        request.args.get("start_date"), request.args.get("end_date")
    )
    payload = container.analytics.analytics(
        plant_id=plant_id,
        type_filter=request.args.get("type"),
        start=start,
        end=end,
    )
    return jsonify(to_jsonable(payload))

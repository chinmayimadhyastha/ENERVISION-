"""Historical observed weather.

Future weather is explicitly unavailable: a request that reaches beyond the
plant's last observed weather date returns a structured 422 instead of silently
truncating or reusing historical weather as a forecast.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.utils.serialization import to_jsonable
from backend.utils.validation import parse_date_range, parse_plant_id

bp = Blueprint("weather", __name__, url_prefix="/api")


@bp.get("/weather")
def weather():
    container = current_app.extensions["enervision"]
    plant_id = parse_plant_id(request.args.get("plant_id"))
    start, end = parse_date_range(
        request.args.get("start_date"), request.args.get("end_date")
    )
    payload = container.weather.historical(plant_id, start=start, end=end)
    return jsonify(to_jsonable(payload))

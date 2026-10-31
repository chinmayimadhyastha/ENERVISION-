"""Historical observed weather."""

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


@bp.get("/weather/<plant_id>")
def weather_by_plant(plant_id: str):
    container = current_app.extensions["enervision"]
    pid = parse_plant_id(plant_id)
    start, end = parse_date_range(
        request.args.get("start_date"), request.args.get("end_date")
    )
    payload = container.weather.historical(pid, start=start, end=end)
    return jsonify(to_jsonable(payload))

"""Daily forecast endpoint."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.schemas.forecast_schema import serialize_forecast
from backend.utils.serialization import to_jsonable
from backend.utils.validation import (
    parse_horizon,
    parse_iso_date,
    parse_model,
    parse_plant_id,
)

bp = Blueprint("forecasts", __name__, url_prefix="/api")


@bp.get("/forecast")
def forecast():
    container = current_app.extensions["enervision"]
    plant_id = parse_plant_id(request.args.get("plant_id"))
    model = parse_model(request.args.get("model"))
    horizon = parse_horizon(
        request.args.get("horizon"),
        default=container.config.DEFAULT_HORIZON,
        maximum=container.config.MAX_HORIZON,
    )
    base_date = parse_iso_date(request.args.get("base_date"), "base_date")

    result = container.forecast.forecast(
        plant_id=plant_id,
        model_requested=model,
        horizon=horizon,
        base_date=base_date,
    )
    payload = serialize_forecast(result, container.config)
    return jsonify(to_jsonable(payload))

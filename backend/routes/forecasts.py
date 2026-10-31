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


MODEL_ALIASES = {
    "random_forest": "rf",
    "random_forest_daily": "rf",
    "rf": "rf",
    "lstm": "lstm",
    "solar_lstm": "lstm",
    "solar_lstm_daily": "lstm",
    "wind_lstm": "lstm",
    "wind_lstm_daily": "lstm",
    "auto": "auto",
}


@bp.route("/forecast", methods=["GET", "POST"])
@bp.route("/forecasts", methods=["GET", "POST"])
def forecast():
    container = current_app.extensions["enervision"]

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        raw_plant_id = data.get("plant_id")
        raw_model = data.get("model") or data.get("model_type")
        raw_horizon = str(data.get("horizon")) if data.get("horizon") is not None else None
        raw_base_date = data.get("base_date")
        raw_weather_provider = data.get("weather_provider")
        inc_conf = str(data.get("include_confidence", data.get("confidence", ""))).lower() in ("1", "true", "yes")
        inc_expl = str(data.get("include_explanation", data.get("explain", ""))).lower() in ("1", "true", "yes")
    else:
        raw_plant_id = request.args.get("plant_id")
        raw_model = request.args.get("model") or request.args.get("model_type")
        raw_horizon = request.args.get("horizon")
        raw_base_date = request.args.get("base_date")
        raw_weather_provider = request.args.get("weather_provider")
        inc_conf = request.args.get("include_confidence", request.args.get("confidence", "")).lower() in ("1", "true", "yes")
        inc_expl = request.args.get("include_explanation", request.args.get("explain", "")).lower() in ("1", "true", "yes")

    if raw_model:
        raw_model = MODEL_ALIASES.get(str(raw_model).lower(), raw_model)

    plant_id = parse_plant_id(raw_plant_id)
    model = parse_model(raw_model)
    horizon = parse_horizon(
        raw_horizon,
        default=container.config.DEFAULT_HORIZON,
        maximum=container.config.MAX_HORIZON,
    )
    base_date = parse_iso_date(raw_base_date, "base_date")

    result = container.forecast.forecast(
        plant_id=plant_id,
        model_requested=model,
        horizon=horizon,
        base_date=base_date,
        weather_provider=raw_weather_provider,
    )
    payload = serialize_forecast(result, container.config, include_confidence=inc_conf, include_explanation=inc_expl)

    # Persist successful forecast to database if available
    if result.status == "ok" and getattr(container, "db", None) is not None:
        try:
            from backend.db.models import ForecastRecordModel, PredictionItemModel
            import uuid
            f_id = f"fc_{uuid.uuid4().hex[:12]}"
            with container.db.session() as session:
                rec = ForecastRecordModel(
                    forecast_id=f_id,
                    plant_id=plant_id,
                    model_id=result.model or "unknown",
                    model_family=result.model_family or "unknown",
                    horizon_days=horizon,
                    base_date=result.base_date,
                    status=result.status,
                )
                session.add(rec)
                session.flush()
                for i, entry in enumerate(result.entries, start=1):
                    p_item = PredictionItemModel(
                        forecast_id=f_id,
                        horizon_day=i,
                        date=entry.date,
                        prediction=entry.prediction,
                        raw_prediction=entry.raw_prediction,
                        clamp_applied=entry.clamp_applied,
                        unit=container.config.TARGET_UNIT,
                        confidence_lower=entry.confidence.get("lower_95") if entry.confidence else None,
                        confidence_upper=entry.confidence.get("upper_95") if entry.confidence else None,
                        confidence_method=entry.confidence.get("method") if entry.confidence else None,
                    )
                    session.add(p_item)
        except Exception:
            pass

    return jsonify(to_jsonable(payload))


@bp.get("/forecast/<plant_id>")
def forecast_by_plant_path(plant_id: str):
    container = current_app.extensions["enervision"]
    pid = parse_plant_id(plant_id)
    model = parse_model(request.args.get("model"))
    horizon = parse_horizon(
        request.args.get("horizon"),
        default=container.config.DEFAULT_HORIZON,
        maximum=container.config.MAX_HORIZON,
    )
    base_date = parse_iso_date(request.args.get("base_date"), "base_date")
    inc_conf = request.args.get("include_confidence", request.args.get("confidence", "")).lower() in ("1", "true", "yes")
    inc_expl = request.args.get("include_explanation", request.args.get("explain", "")).lower() in ("1", "true", "yes")
    raw_weather_provider = request.args.get("weather_provider")

    result = container.forecast.forecast(
        plant_id=pid,
        model_requested=model,
        horizon=horizon,
        base_date=base_date,
        weather_provider=raw_weather_provider,
    )
    payload = serialize_forecast(result, container.config, include_confidence=inc_conf, include_explanation=inc_expl)
    return jsonify(to_jsonable(payload))


@bp.route("/forecast/explain", methods=["GET", "POST"])
def explain_forecast():
    container = current_app.extensions["enervision"]
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        raw_plant_id = data.get("plant_id")
        raw_model = data.get("model") or data.get("model_type")
    else:
        raw_plant_id = request.args.get("plant_id")
        raw_model = request.args.get("model") or request.args.get("model_type")

    if raw_model:
        raw_model = MODEL_ALIASES.get(str(raw_model).lower(), raw_model)

    plant_id = parse_plant_id(raw_plant_id)
    model = parse_model(raw_model)

    explanation = container.explanation.explain_plant(plant_id, model_requested=model)
    return jsonify(to_jsonable(explanation))


@bp.get("/forecast/<plant_id>/explain")
def explain_forecast_by_path(plant_id: str):
    container = current_app.extensions["enervision"]
    pid = parse_plant_id(plant_id)
    raw_model = request.args.get("model") or request.args.get("model_type")
    if raw_model:
        raw_model = MODEL_ALIASES.get(str(raw_model).lower(), raw_model)
    model = parse_model(raw_model)

    explanation = container.explanation.explain_plant(pid, model_requested=model)
    return jsonify(to_jsonable(explanation))

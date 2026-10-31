"""Serialization of daily forecast results.

The response surface is deliberately explicit about:

* daily frequency and ``MU/day`` units;
* the difference between ``raw_prediction`` and the physically served
  ``prediction = max(raw_prediction, 0)``;
* ``confidence: null`` by default unless requested;
* exactly which weather inputs are missing when a forecast cannot be produced.
"""

from __future__ import annotations

from backend.services.feature_builder import WEATHER_FIELDS
from backend.utils.serialization import iso_date

CONFIDENCE_NOTE = (
    "No calibrated probabilistic forecasting model exists for these artifacts, so no "
    "confidence interval or probability is reported by default. The value is null rather than invented."
)


def _post_processing(entries) -> dict:
    affected = [entry.date.isoformat() for entry in entries if entry.clamp_applied]
    return {
        "applied": bool(affected),
        "method": "max(raw_prediction, 0.0)",
        "reason": (
            "Daily energy generation cannot be negative. The serving layer clamps negative "
            "raw model outputs to zero; the unmodified raw value is preserved in "
            "raw_prediction."
        ),
        "affected_dates": affected,
    }


def _input_contract(result, config) -> dict:
    if result.model_family == "lstm":
        sequence_shape = None
        if result.entries:
            sequence_shape = result.entries[0].sequence_shape
        return {
            "model_family": "lstm",
            "input_shape": [config.LSTM_SEQUENCE_LENGTH, config.LSTM_FEATURE_COUNT],
            "sequence_length": config.LSTM_SEQUENCE_LENGTH,
            "feature_count": config.LSTM_FEATURE_COUNT,
            "target_day_weather_required": False,
            "intermediate_day_weather_required": result.horizon_days > 1,
            "uses_prediction_day_target": False,
            "observed_input_shape": sequence_shape,
        }
    return {
        "model_family": "random_forest",
        "input_shape": [config.RF_FEATURE_COUNT],
        "feature_count": config.RF_FEATURE_COUNT,
        "target_day_weather_required": True,
        "uses_prediction_day_target": False,
        "forbidden_features": ["Generation_per_MW"],
    }


def serialize_forecast(result, config, include_confidence: bool = False, include_explanation: bool = False) -> dict:
    forecasts = []
    for index, entry in enumerate(result.entries, start=1):
        item = {
            "date": entry.date.isoformat(),
            "horizon_day": index,
            "frequency": config.FREQUENCY,
            "unit": config.TARGET_UNIT,
            "prediction": entry.prediction,
            "raw_prediction": entry.raw_prediction,
            "clamp_applied": entry.clamp_applied,
            "confidence": entry.confidence if include_confidence else None,
        }
        if getattr(entry, "p10", None) is not None:
            item["p10"] = entry.p10
            item["p50"] = entry.p50
            item["p90"] = entry.p90
        if entry.features is not None:
            item["features"] = dict(entry.features)
        if include_explanation and getattr(entry, "explanation", None) is not None:
            item["explanation"] = entry.explanation
        forecasts.append(item)

    top_confidence = None
    confidence_note = CONFIDENCE_NOTE
    if include_confidence and forecasts and forecasts[0].get("confidence"):
        top_confidence = forecasts[0]["confidence"]
        confidence_note = top_confidence.get("description", CONFIDENCE_NOTE)

    payload = {
        "status": result.status,
        "frequency": config.FREQUENCY,
        "target": config.TARGET,
        "unit": config.TARGET_UNIT,
        "horizon_days": result.horizon_days,
        "model_requested": result.model_requested,
        "model": result.model,
        "model_family": result.model_family,
        "plant": result.plant.as_dict(),
        "base_date": iso_date(result.base_date),
        "forecast_dates": [day.isoformat() for day in result.forecast_dates],
        "confidence": top_confidence,
        "confidence_note": confidence_note,
        "input_contract": _input_contract(result, config),
        "future_weather": {
            "provider": result.provider,
            "provider_available": result.future_weather_available,
            "is_forecast": result.status == "ok"
            and (
                result.model_family == "random_forest"
                or result.horizon_days > 1
            ),
            "required_for_this_request": bool(result.required_weather),
        },
        "post_processing": _post_processing(result.entries),
        "forecast_count": len(forecasts),
        "forecasts": forecasts,
        "forecast": forecasts,
        "history_context": result.history_context,
        "notes": list(result.notes),
    }

    if result.status == "weather_required":
        payload["required_weather"] = result.required_weather
        payload["missing_weather"] = result.missing_weather
        payload["missing_weather_summary"] = {
            "dates": [day.isoformat() for day in result.forecast_dates],
            "inputs": list(WEATHER_FIELDS),
            "count": len(result.missing_weather),
        }
        payload["reason"] = (
            "Required weather is unavailable. No prediction was generated and no weather value "
            "was fabricated or reused from another date."
        )

    if result.status == "insufficient_history":
        payload["insufficient_history"] = result.insufficient_history
        payload["reason"] = (
            "The plant does not have enough preceding observations to build the model input. "
            "No prediction was generated."
        )

    return payload

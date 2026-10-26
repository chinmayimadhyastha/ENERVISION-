"""Model-manifest loading and contract validation.

The manifest is the authoritative source for feature order, sequence length,
target, unit and metric provenance.  The backend imports these definitions
instead of maintaining a second hand-written copy.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.utils.errors import ArtifactError

FORBIDDEN_RF_FEATURE = "Generation_per_MW"


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise ArtifactError(
            f"Model manifest is missing: {path}. "
            "Restore models/model_manifest.json before starting the API."
        )
    try:
        with path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"Model manifest could not be read: {path} ({exc})") from exc

    if not isinstance(manifest, dict):
        raise ArtifactError(f"Model manifest must contain a JSON object: {path}")
    return manifest


def _models_by_id(manifest: dict) -> dict[str, dict]:
    models = manifest.get("models")
    if not isinstance(models, list) or not models:
        raise ArtifactError("The model manifest does not declare any models.")
    result = {}
    for model in models:
        model_id = model.get("id")
        if not model_id:
            raise ArtifactError("A model entry in the manifest is missing its 'id'.")
        result[model_id] = model
    return result


def validate_manifest(manifest: dict, config) -> dict:
    """Validate the frozen daily contract and return normalised contracts."""

    contract = manifest.get("forecasting_contract", {})
    if contract.get("frequency") != "daily":
        raise ArtifactError("The manifest does not declare daily forecasting.")
    if contract.get("target") != config.TARGET:
        raise ArtifactError(
            f"Manifest target {contract.get('target')!r} does not match "
            f"the backend target {config.TARGET!r}."
        )
    if contract.get("unit") != config.TARGET_UNIT:
        raise ArtifactError(
            f"Manifest unit {contract.get('unit')!r} does not match "
            f"the backend unit {config.TARGET_UNIT!r}."
        )
    if contract.get("hourly_forecasting") is not False:
        raise ArtifactError("The manifest must explicitly disable hourly forecasting.")

    feature_contracts = manifest.get("feature_contracts", {})
    rf_contract = feature_contracts.get("random_forest", {})
    lstm_contract = feature_contracts.get("lstm", {})

    rf_features = list(rf_contract.get("order") or [])
    if len(rf_features) != config.RF_FEATURE_COUNT:
        raise ArtifactError(
            f"The manifest declares {len(rf_features)} Random Forest features; "
            f"expected {config.RF_FEATURE_COUNT}."
        )
    if FORBIDDEN_RF_FEATURE in rf_features:
        raise ArtifactError(
            f"{FORBIDDEN_RF_FEATURE} is present in the Random Forest contract. "
            "It leaks the prediction target and must never be used."
        )

    lstm_features = list(lstm_contract.get("order") or [])
    if len(lstm_features) != config.LSTM_FEATURE_COUNT:
        raise ArtifactError(
            f"The manifest declares {len(lstm_features)} LSTM features; "
            f"expected {config.LSTM_FEATURE_COUNT}."
        )
    sequence_length = lstm_contract.get("sequence_length")
    if sequence_length != config.LSTM_SEQUENCE_LENGTH:
        raise ArtifactError(
            f"The manifest declares LSTM sequence length {sequence_length!r}; "
            f"expected {config.LSTM_SEQUENCE_LENGTH}."
        )

    column_map = dict(lstm_contract.get("dataset_column_map") or {})
    if column_map.get("Lagged_Generation") != "Generation_lag_1":
        raise ArtifactError(
            "Manifest mapping for Lagged_Generation must be Generation_lag_1."
        )
    if column_map.get("Rolling_Generation_7") != "Generation_roll_7":
        raise ArtifactError(
            "Manifest mapping for Rolling_Generation_7 must be Generation_roll_7."
        )

    models = _models_by_id(manifest)
    for required_id in ("random_forest_daily", "solar_lstm_daily", "wind_lstm_daily"):
        if required_id not in models:
            raise ArtifactError(f"The manifest is missing required model {required_id!r}.")

    rf_model = models["random_forest_daily"]
    if list(rf_model.get("feature_order") or []) != rf_features:
        raise ArtifactError(
            "The Random Forest model feature_order disagrees with feature_contracts."
        )
    if FORBIDDEN_RF_FEATURE in (rf_model.get("feature_order") or []):
        raise ArtifactError(f"{FORBIDDEN_RF_FEATURE} must not appear in the model order.")

    for model_id in ("solar_lstm_daily", "wind_lstm_daily"):
        model = models[model_id]
        if list(model.get("feature_order") or []) != lstm_features:
            raise ArtifactError(
                f"{model_id} feature_order disagrees with the LSTM feature contract."
            )
        if model.get("sequence_length") != config.LSTM_SEQUENCE_LENGTH:
            raise ArtifactError(
                f"{model_id} sequence_length must be {config.LSTM_SEQUENCE_LENGTH}."
            )

    return {
        "manifest": manifest,
        "models": models,
        "rf_features": rf_features,
        "lstm_features": lstm_features,
        "lstm_column_map": column_map,
        "sequence_length": sequence_length,
    }

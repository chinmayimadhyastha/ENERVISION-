"""Request validation helpers.

Validation errors are raised as :class:`ApiError` with HTTP 400.  A request
whose structure is valid but whose underlying data is insufficient is raised
by the service layer as HTTP 422 instead.
"""

from __future__ import annotations

import re
from datetime import date

from backend.utils.errors import ApiError

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INTEGER = re.compile(r"^\d+$")

VALID_MODELS = ("rf", "lstm", "auto")
VALID_TYPES = {"solar": "Solar", "wind": "Wind"}


def require_query_param(raw: str | None, name: str) -> str:
    if raw is None:
        raise ApiError(
            "MISSING_PARAMETER",
            f"Query parameter '{name}' is required.",
            400,
            {"parameter": name},
        )
    value = raw.strip()
    if not value:
        raise ApiError(
            "INVALID_PARAMETER",
            f"Query parameter '{name}' must not be empty.",
            400,
            {"parameter": name},
        )
    return value


def parse_plant_id(raw: str | None) -> str:
    value = require_query_param(raw, "plant_id")
    if "/" in value or "\\" in value:
        raise ApiError(
            "INVALID_PARAMETER",
            "Query parameter 'plant_id' contains invalid characters.",
            400,
            {"parameter": "plant_id"},
        )
    return value.lower()


def parse_model(raw: str | None) -> str:
    if raw is None or not raw.strip():
        return "auto"
    value = raw.strip().lower()
    if value not in VALID_MODELS:
        raise ApiError(
            "INVALID_MODEL",
            "Query parameter 'model' must be one of: rf, lstm, auto.",
            400,
            {"parameter": "model", "allowed_values": list(VALID_MODELS)},
        )
    return value


def parse_horizon(raw: str | None, *, default: int, maximum: int) -> int:
    if raw is None or not raw.strip():
        return default
    value = raw.strip()
    if not _INTEGER.fullmatch(value):
        raise ApiError(
            "INVALID_HORIZON",
            (
                "Query parameter 'horizon' must be an integer number of future days. "
                "Hourly horizons such as '3h' are not supported."
            ),
            400,
            {"parameter": "horizon", "minimum": 1, "maximum": maximum},
        )

    horizon = int(value)
    if not 1 <= horizon <= maximum:
        raise ApiError(
            "INVALID_HORIZON",
            f"Query parameter 'horizon' must be between 1 and {maximum} future days.",
            400,
            {"parameter": "horizon", "minimum": 1, "maximum": maximum},
        )
    return horizon


def parse_iso_date(raw: str | None, name: str) -> date | None:
    if raw is None or not raw.strip():
        return None
    value = raw.strip()
    if not _ISO_DATE.fullmatch(value):
        raise ApiError(
            "INVALID_DATE",
            f"Query parameter '{name}' must be an ISO date in YYYY-MM-DD format.",
            400,
            {"parameter": name},
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(
            "INVALID_DATE",
            f"Query parameter '{name}' is not a valid calendar date.",
            400,
            {"parameter": name},
        ) from exc


def parse_date_range(
    start_raw: str | None,
    end_raw: str | None,
) -> tuple[date | None, date | None]:
    start = parse_iso_date(start_raw, "start_date")
    end = parse_iso_date(end_raw, "end_date")
    if start and end and start > end:
        raise ApiError(
            "INVALID_DATE_RANGE",
            "Query parameter 'start_date' must be on or before 'end_date'.",
            400,
            {"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
    return start, end


def parse_type(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    value = raw.strip().lower()
    if value not in VALID_TYPES:
        raise ApiError(
            "INVALID_TYPE",
            "Query parameter 'type' must be either 'Solar' or 'Wind'.",
            400,
            {"parameter": "type", "allowed_values": ["Solar", "Wind"]},
        )
    return VALID_TYPES[value]


def parse_limit(raw: str | None, *, name: str, default: int, minimum: int, maximum: int) -> int:
    if raw is None or not raw.strip():
        return default
    value = raw.strip()
    if not _INTEGER.fullmatch(value):
        raise ApiError(
            "INVALID_PARAMETER",
            f"Query parameter '{name}' must be an integer.",
            400,
            {"parameter": name},
        )
    number = int(value)
    if not minimum <= number <= maximum:
        raise ApiError(
            "INVALID_PARAMETER",
            f"Query parameter '{name}' must be between {minimum} and {maximum}.",
            400,
            {"parameter": name, "minimum": minimum, "maximum": maximum},
        )
    return number


def optional_text(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value or None

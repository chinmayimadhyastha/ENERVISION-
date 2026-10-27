"""JSON serialization helpers.

pandas/numpy scalars and ``NaN`` are converted to ordinary JSON types so no
route ever emits ``NaN`` (which is invalid JSON) or a NumPy repr.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

_MISSING = object()


def to_jsonable(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]

    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, int):
        return int(value)

    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()[:10] if hasattr(value, "isoformat") else str(value)

    if value is pd.NA or value is pd.NaT:
        return None

    # pandas.isna raises for arrays/containers, which were handled above.
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return value


def clean_float(value: Any) -> float | None:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def iso_date(value: Any) -> str | None:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, str):
        return value
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError):
        return None

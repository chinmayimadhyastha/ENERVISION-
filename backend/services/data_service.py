"""Once-only loading and indexing of the canonical ENERVISION datasets."""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from backend.utils.errors import ArtifactError

TARGET = "DailyGeneration_MU"
WEATHER_FIELDS = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]

REQUIRED_CANONICAL_COLUMNS = [
    "Date",
    "PlantName",
    "State",
    "Owner",
    "Type",
    "Capacity_MW",
    TARGET,
    "District",
    "Latitude",
    "Longitude",
    "CommissionDate",
    *WEATHER_FIELDS,
]

REQUIRED_WEATHER_COLUMNS = [
    "Date",
    "PlantName",
    "Type",
    "Capacity_MW",
    "District",
    TARGET,
    *WEATHER_FIELDS,
    "WeatherSentinelCount",
    "WeatherImputed",
]

REQUIRED_FEATURE_COLUMNS = ["Date", "PlantName", "Type", "Capacity_MW", "District", TARGET, "_split"]


@dataclass(frozen=True)
class PlantRecord:
    plant_id: str
    plant_name: str
    type: str
    district: str | None
    state: str | None
    owner: str | None
    latitude: float | None
    longitude: float | None
    capacity_mw: float
    commission_date: str | None
    first_observed_date: date
    last_observed_date: date
    observations: int
    latest_generation_mu: float
    latest_generation_date: date

    def as_dict(self) -> dict:
        return {
            "plant_id": self.plant_id,
            "plant_name": self.plant_name,
            "type": self.type,
            "district": self.district,
            "state": self.state,
            "owner": self.owner,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "capacity_mw": self.capacity_mw,
            "commission_date": self.commission_date,
            "first_observed_date": self.first_observed_date.isoformat(),
            "last_observed_date": self.last_observed_date.isoformat(),
            "observations": self.observations,
            "latest_generation_mu": self.latest_generation_mu,
            "latest_generation_date": self.latest_generation_date.isoformat(),
            "has_coordinates": self.latitude is not None and self.longitude is not None,
        }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return slug or "plant"


def _read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise ArtifactError(f"Required {label} is missing: {path}")
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise ArtifactError(f"Required {label} could not be read: {path} ({exc})") from exc
    if frame.empty:
        raise ArtifactError(f"Required {label} is empty: {path}")
    if "Date" not in frame.columns:
        raise ArtifactError(f"Required {label} has no Date column: {path}")
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    if frame["Date"].isna().any():
        raise ArtifactError(f"Required {label} contains unparseable dates: {path}")
    return frame


def _require_columns(frame: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ArtifactError(f"{label} is missing required columns: {missing}")


def _last_valid(series: pd.Series):
    valid = series.dropna()
    return valid.iloc[-1] if len(valid) else None


def _optional_text(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


class DataService:
    """Loads the canonical, cleaned-weather and feature datasets exactly once."""

    def __init__(self, config, contracts: dict, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.contracts = contracts
        self.logger = logger or logging.getLogger("enervision.data")
        self.rf_features: list[str] = contracts["rf_features"]
        self.lstm_features: list[str] = contracts["lstm_features"]
        self.lstm_column_map: dict[str, str] = contracts["lstm_column_map"]

        self.canonical: pd.DataFrame
        self.weather: pd.DataFrame
        self.features: pd.DataFrame

        self.frames: dict[str, pd.DataFrame] = {}
        self.feature_frames: dict[str, pd.DataFrame] = {}
        self.plants_by_id: dict[str, PlantRecord] = {}
        self.plants_by_name: dict[str, PlantRecord] = {}
        self.plant_id_by_name: dict[str, str] = {}
        self.plant_name_by_id: dict[str, str] = {}

        self._weather_lookup: dict[tuple[str, date], dict] = {}
        self._latest_metadata: pd.DataFrame
        self.id_collision_count = 0
        self.loaded = False

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        self.canonical = _read_csv(self.config.CANONICAL_DATA_PATH, "canonical dataset")
        self.weather = _read_csv(self.config.WEATHER_DATA_PATH, "cleaned weather dataset")
        self.features = _read_csv(self.config.FEATURE_DATA_PATH, "feature dataset")

        _require_columns(self.canonical, REQUIRED_CANONICAL_COLUMNS, "Canonical dataset")
        _require_columns(self.weather, REQUIRED_WEATHER_COLUMNS, "Cleaned weather dataset")
        _require_columns(
            self.features,
            REQUIRED_FEATURE_COLUMNS + self.rf_features,
            "Feature dataset",
        )

        self._validate_frames()
        self.canonical = self.canonical.sort_values(["PlantName", "Date"]).reset_index(drop=True)
        self.weather = self.weather.sort_values(["PlantName", "Date"]).reset_index(drop=True)
        self.features = self.features.sort_values(["PlantName", "Date"]).reset_index(drop=True)

        self._latest_metadata = (
            self.canonical.groupby("PlantName", sort=True).tail(1).set_index("PlantName")
        )
        self._build_indexes()
        self._build_plants()
        self.loaded = True

        self.logger.info(
            "Loaded data: %s canonical rows, %s plants, %s feature rows, date range %s to %s",
            len(self.canonical),
            len(self.plants_by_id),
            len(self.features),
            self.weather["Date"].min().date().isoformat(),
            self.weather["Date"].max().date().isoformat(),
        )
        if self.id_collision_count:
            self.logger.info(
                "Resolved %s plant-name slug collision(s) deterministically.",
                self.id_collision_count,
            )

    # -------------------------------------------------------------- validation
    def _validate_frames(self) -> None:
        for label, frame in (
            ("Canonical dataset", self.canonical),
            ("Cleaned weather dataset", self.weather),
            ("Feature dataset", self.features),
        ):
            duplicates = int(frame.duplicated(subset=["PlantName", "Date"]).sum())
            if duplicates:
                raise ArtifactError(
                    f"{label} contains {duplicates} duplicate (PlantName, Date) rows; "
                    "lag and rolling features would be ambiguous."
                )

        for label, frame in (
            ("Canonical dataset", self.canonical),
            ("Cleaned weather dataset", self.weather),
            ("Feature dataset", self.features),
        ):
            if frame[TARGET].isna().any():
                raise ArtifactError(f"{label} contains missing {TARGET} values.")

        for field in WEATHER_FIELDS:
            values = pd.to_numeric(self.weather[field], errors="coerce")
            if values.isna().any():
                raise ArtifactError(
                    f"Cleaned weather dataset contains missing {field} values. "
                    "The backend cannot infer with incomplete weather."
                )
            if (values <= -900).any():
                raise ArtifactError(
                    f"Cleaned weather dataset still contains sentinel values in {field}."
                )

        if "Generation_per_MW" in self.features.columns:
            raise ArtifactError(
                "Feature dataset contains Generation_per_MW, which leaks the prediction "
                "target. The backend refuses to start with a leaked feature contract."
            )
        if self.features[self.rf_features].isna().any().any():
            raise ArtifactError("Feature dataset contains missing Random Forest features.")
        lstm_source_columns = [
            self.lstm_column_map.get(feature, feature) for feature in self.lstm_features
        ]
        missing_lstm_columns = [
            column for column in lstm_source_columns if column not in self.features.columns
        ]
        if missing_lstm_columns:
            raise ArtifactError(
                "Feature dataset is missing LSTM source columns: "
                f"{missing_lstm_columns}"
            )
        if self.features[lstm_source_columns].isna().any().any():
            raise ArtifactError("Feature dataset contains missing LSTM features.")
        if "_split" not in self.features.columns:
            raise ArtifactError("Feature dataset is missing the chronological _split column.")

        self._validate_cross_dataset_consistency()

    def _validate_cross_dataset_consistency(self) -> None:
        weather = self.weather[["PlantName", "Date", TARGET, *WEATHER_FIELDS]]
        canonical = self.canonical[["PlantName", "Date", TARGET, *WEATHER_FIELDS]]
        merged = weather.merge(
            canonical,
            on=["PlantName", "Date"],
            how="outer",
            suffixes=("_weather", "_canonical"),
            indicator=True,
        )
        unmatched = int((merged["_merge"] != "both").sum())
        if unmatched:
            raise ArtifactError(
                "Canonical and cleaned-weather datasets do not align on "
                f"(PlantName, Date): {unmatched} unmatched rows."
            )

        target_delta = (
            merged[f"{TARGET}_weather"] - merged[f"{TARGET}_canonical"]
        ).abs().max()
        if pd.notna(target_delta) and float(target_delta) > 1e-9:
            raise ArtifactError(
                "Canonical and cleaned-weather targets disagree for at least one row."
            )

        feature_weather = self.features[
            ["PlantName", "Date", TARGET, *WEATHER_FIELDS]
        ].merge(
            weather,
            on=["PlantName", "Date"],
            how="left",
            suffixes=("_feature", "_weather"),
            indicator=True,
        )
        if (feature_weather["_merge"] != "both").any():
            raise ArtifactError(
                "Feature dataset rows are not all present in the cleaned-weather dataset."
            )
        for field in [TARGET, *WEATHER_FIELDS]:
            delta = (
                feature_weather[f"{field}_feature"] - feature_weather[f"{field}_weather"]
            ).abs().max()
            if pd.notna(delta) and float(delta) > 1e-9:
                raise ArtifactError(
                    f"Feature dataset and cleaned-weather dataset disagree on {field}."
                )

    # ----------------------------------------------------------------- indexes
    def _build_indexes(self) -> None:
        for plant_name, group in self.weather.groupby("PlantName", sort=True):
            self.frames[str(plant_name)] = group.sort_values("Date").reset_index(drop=True)

        for plant_name, group in self.features.groupby("PlantName", sort=True):
            self.feature_frames[str(plant_name)] = group.sort_values("Date").reset_index(drop=True)

        for plant_name, group in self.weather.groupby("PlantName", sort=True):
            for row in group.itertuples(index=False):
                self._weather_lookup[(str(plant_name), row.Date.date())] = {
                    "Temperature": float(row.Temperature),
                    "Humidity": float(row.Humidity),
                    "WindSpeed": float(row.WindSpeed),
                    "GHI": float(row.GHI),
                    "Pressure": float(row.Pressure),
                }

    # ---------------------------------------------------------------- identity
    def _build_plants(self) -> None:
        latest = self._latest_metadata
        names = sorted(str(name) for name in latest.index)
        base_groups: dict[str, list[str]] = defaultdict(list)
        for name in names:
            base_groups[slugify(name)].append(name)

        used: set[str] = set()
        assigned: dict[str, str] = {}

        for base in sorted(base_groups):
            group = base_groups[base]
            if len(group) == 1:
                candidate = base
                if candidate in used:
                    candidate = self._disambiguate(group[0], latest, used)
                assigned[group[0]] = candidate
                used.add(candidate)
                continue

            self.id_collision_count += len(group)
            for name in group:
                candidate = self._disambiguate(name, latest, used)
                assigned[name] = candidate
                used.add(candidate)

        if len(set(assigned.values())) != len(assigned):
            raise ArtifactError("Plant identifier generation produced duplicate IDs.")

        for name in names:
            plant_id = assigned[name]
            weather_group = self.frames.get(name)
            if weather_group is None or weather_group.empty:
                raise ArtifactError(f"No cleaned weather rows exist for plant {name!r}.")

            latest_row = latest.loc[name]
            coordinate_rows = self.canonical[
                (self.canonical["PlantName"] == name)
                & self.canonical["Latitude"].notna()
                & self.canonical["Longitude"].notna()
            ].sort_values("Date")
            latitude = None
            longitude = None
            if not coordinate_rows.empty:
                latitude = _optional_float(coordinate_rows.iloc[-1]["Latitude"])
                longitude = _optional_float(coordinate_rows.iloc[-1]["Longitude"])

            commission_rows = self.canonical[
                (self.canonical["PlantName"] == name)
                & self.canonical["CommissionDate"].notna()
            ].sort_values("Date")
            commission_date = None
            if not commission_rows.empty:
                commission_date = _optional_text(commission_rows.iloc[-1]["CommissionDate"])

            last_row = weather_group.iloc[-1]
            record = PlantRecord(
                plant_id=plant_id,
                plant_name=name,
                type=str(latest_row["Type"]).strip(),
                district=_optional_text(latest_row["District"]),
                state=_optional_text(latest_row["State"]),
                owner=_optional_text(latest_row["Owner"]),
                latitude=latitude,
                longitude=longitude,
                capacity_mw=float(latest_row["Capacity_MW"]),
                commission_date=commission_date,
                first_observed_date=weather_group["Date"].iloc[0].date(),
                last_observed_date=weather_group["Date"].iloc[-1].date(),
                observations=int(len(weather_group)),
                latest_generation_mu=float(last_row[TARGET]),
                latest_generation_date=last_row["Date"].date(),
            )
            self.plants_by_id[plant_id] = record
            self.plants_by_name[name] = record
            self.plant_id_by_name[name] = plant_id
            self.plant_name_by_id[plant_id] = name

    def _disambiguate(self, name: str, latest: pd.DataFrame, used: set[str]) -> str:
        """Deterministically resolve a slug collision using real metadata."""
        row = latest.loc[name]
        capacity = float(row["Capacity_MW"])
        base = slugify(
            f"{name}-{row['Type']}-{row['District']}-{capacity:g}mw"
        )
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    # --------------------------------------------------------------- accessors
    def get_plant(self, plant_id: str) -> PlantRecord | None:
        return self.plants_by_id.get(plant_id.strip().lower())

    def require_plant(self, plant_id: str) -> PlantRecord:
        record = self.get_plant(plant_id)
        if record is None:
            from backend.utils.errors import ApiError

            raise ApiError(
                "PLANT_NOT_FOUND",
                f"Plant '{plant_id}' was not found.",
                404,
                {"plant_id": plant_id},
            )
        return record

    def get_frame(self, plant_name: str) -> pd.DataFrame:
        frame = self.frames.get(plant_name)
        if frame is None:
            raise KeyError(f"No data frame for plant {plant_name!r}")
        return frame

    def all_weather_frame(self) -> pd.DataFrame:
        """A copy of the cleaned plant/weather/generation table for analytics."""
        return self.weather.copy()

    def get_feature_frame(self, plant_name: str) -> pd.DataFrame:
        frame = self.feature_frames.get(plant_name)
        if frame is None:
            raise KeyError(f"No feature frame for plant {plant_name!r}")
        return frame

    def get_weather_row(self, plant_name: str, day: date) -> dict | None:
        row = self._weather_lookup.get((plant_name, day))
        return dict(row) if row is not None else None

    def latest_fleet_date(self) -> date:
        return self.weather["Date"].max().date()

    def fleet_capacity_mw(self) -> float:
        return float(sum(plant.capacity_mw for plant in self.plants_by_id.values()))

    def type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for plant in self.plants_by_id.values():
            counts[plant.type] += 1
        return dict(sorted(counts.items()))

    def list_plants(self) -> list[PlantRecord]:
        return sorted(self.plants_by_id.values(), key=lambda plant: plant.plant_name.lower())

    def generation_matrix(self) -> pd.DataFrame:
        return self.weather[["Date", "PlantName", "Type", "Capacity_MW", TARGET]].copy()

    def dataset_summary(self) -> dict:
        return {
            "rows": int(len(self.canonical)),
            "plants": int(len(self.plants_by_id)),
            "feature_rows": int(len(self.features)),
            "date_range": {
                "start": self.weather["Date"].min().date().isoformat(),
                "end": self.weather["Date"].max().date().isoformat(),
            },
            "type_counts": self.type_counts(),
            "weather_fields": list(WEATHER_FIELDS),
            "cleaned_weather_dataset": Path(self.config.WEATHER_DATA_PATH).name,
        }

"""Build the plant/weather modelling dataset from the canonical merged CSV.

The historical pipeline (commit 760289efaa) built this file from
``generation_combined.csv`` + ``weather_clean.csv`` + ``plant_weather_mapping.csv``.
Those intermediate files are no longer in the repository, so this script derives the
same modelling table from the committed canonical dataset:

    data/final/full_generation_weather_dataset.csv
        -> data/final/plant_weather_training_dataset.csv

The script does not fetch, invent or extrapolate any data.  It only applies the
explicit quality policy described below and records every affected row in
``reports/data_quality_summary.json``.

QUALITY POLICY (explicit, documented, never silent)
---------------------------------------------------
1. Weather sentinels
   NASA POWER uses ``-999`` for missing values.  Any weather value ``<= -900`` in
   Temperature / Humidity / WindSpeed / GHI / Pressure is treated as missing, replaced
   by NaN, and then filled per plant in date order with forward-fill followed by
   backward-fill.  This mirrors the committed LSTM cleaning code
   (``train_lstm_model(ABR).py``) and avoids physically impossible feature values.
   Rows are flagged with ``WeatherSentinelCount`` and ``WeatherImputed``.
2. Negative generation
   Daily generation cannot be negative.  Negative ``DailyGeneration_MU`` values are
   flagged with ``GenerationWasNegative`` and clipped to 0.0 for modelling, matching
   the committed LSTM target policy.  The canonical dataset currently contains zero
   negatives, so this is a no-op today but keeps the policy deterministic.
3. Missing identifiers / target
   Rows without Date, PlantName, Type, Capacity_MW or DailyGeneration_MU cannot be
   modelled and are dropped with a count recorded in the summary.
4. Invalid capacity
   ``Capacity_MW <= 0`` cannot support ``Generation_per_MW`` and is dropped with a
   count recorded in the summary.
5. Duplicate keys
   Duplicate (PlantName, Date, Capacity_MW) rows are removed (first occurrence kept)
   and the count is recorded.
6. Remaining missing weather
   If a plant has no usable weather at all, rows with remaining NaN weather are
   dropped and the count is recorded.
7. Provenance
   ``MappingStatus`` is joined from ``data/metadata/plant_weather_mapping.csv`` when
   possible.  It is metadata only and is not a model feature.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent

CANONICAL = BASE / "data/final/full_generation_weather_dataset.csv"
MAPPING = BASE / "data/metadata/plant_weather_mapping.csv"
OUTPUT = BASE / "data/final/plant_weather_training_dataset.csv"
SUMMARY = BASE / "reports/data_quality_summary.json"

WEATHER_COLS = ["Temperature", "Humidity", "WindSpeed", "GHI", "Pressure"]
OUTPUT_COLS = [
    "Date",
    "PlantName",
    "Type",
    "Capacity_MW",
    "District",
    "DailyGeneration_MU",
    *WEATHER_COLS,
    "MappingStatus",
    "WeatherSentinelCount",
    "WeatherImputed",
    "GenerationWasNegative",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=CANONICAL)
    parser.add_argument("--mapping", type=Path, default=MAPPING)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    return parser.parse_args()


def load_mapping_status(mapping_path: Path) -> pd.DataFrame:
    """Return one MappingStatus value per (PlantName, Type, Capacity_MW)."""
    if not mapping_path.exists():
        return pd.DataFrame(columns=["PlantName", "Type", "Capacity_MW", "MappingStatus"])

    mapping = pd.read_csv(mapping_path)
    key = ["PlantName", "Type", "Capacity_MW"]
    missing = [c for c in key + ["MappingStatus"] if c not in mapping.columns]
    if missing:
        raise ValueError(f"Mapping file is missing required columns: {missing}")

    mapping = mapping[key + ["MappingStatus"]].copy()
    mapping["Capacity_MW"] = pd.to_numeric(mapping["Capacity_MW"], errors="coerce")

    # The committed mapping contains repeated identical plant rows.  Collapse them to
    # one deterministic status per modelling key.  Prefer "Mapped" if it is present.
    mapping["_priority"] = (mapping["MappingStatus"] != "Mapped").astype(int)
    mapping = (
        mapping.sort_values(key + ["_priority", "MappingStatus"])
        .drop_duplicates(subset=key, keep="first")
        .drop(columns="_priority")
    )
    return mapping


def main() -> int:
    args = parse_args()

    if not args.canonical.exists():
        raise FileNotFoundError(f"Canonical dataset not found: {args.canonical}")

    df = pd.read_csv(args.canonical)
    rows_in = len(df)

    required = [
        "Date",
        "PlantName",
        "Type",
        "Capacity_MW",
        "District",
        "DailyGeneration_MU",
        *WEATHER_COLS,
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Canonical dataset is missing required columns: {missing}")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["PlantName"] = df["PlantName"].astype("string").str.strip()
    df["Type"] = df["Type"].astype("string").str.strip()
    df["District"] = df["District"].astype("string").str.strip()
    df["Capacity_MW"] = pd.to_numeric(df["Capacity_MW"], errors="coerce")
    df["DailyGeneration_MU"] = pd.to_numeric(df["DailyGeneration_MU"], errors="coerce")
    for col in WEATHER_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    summary: dict[str, object] = {
        "canonical_dataset": str(args.canonical),
        "rows_in": rows_in,
        "plants_in": int(df["PlantName"].nunique(dropna=True)),
        "policy": {
            "weather_sentinel_rule": "value <= -900 treated as missing (-999 is the NASA POWER sentinel)",
            "weather_imputation": "per plant, chronological forward-fill then backward-fill",
            "negative_generation_rule": "flag and clip DailyGeneration_MU to 0.0 for modelling",
            "missing_identifier_rule": "drop rows without Date, PlantName, Type, Capacity_MW or target",
            "invalid_capacity_rule": "drop rows with Capacity_MW <= 0",
            "duplicate_rule": "drop duplicate (PlantName, Date, Capacity_MW), keep first",
        },
    }

    # 3. Missing identifiers / target.
    id_cols = ["Date", "PlantName", "Type", "Capacity_MW", "DailyGeneration_MU"]
    id_mask = df[id_cols].isna().any(axis=1) | (df["PlantName"] == "") | (df["Type"] == "")
    summary["dropped_missing_identifier_or_target"] = int(id_mask.sum())
    df = df.loc[~id_mask].copy()

    # 4. Invalid capacity.
    bad_capacity = df["Capacity_MW"] <= 0
    summary["dropped_invalid_capacity"] = int(bad_capacity.sum())
    df = df.loc[~bad_capacity].copy()

    # 5. Duplicate modelling keys.
    dup_key = ["PlantName", "Date", "Capacity_MW"]
    duplicate_mask = df.duplicated(subset=dup_key, keep="first")
    summary["dropped_duplicate_keys"] = int(duplicate_mask.sum())
    df = df.loc[~duplicate_mask].copy()

    # 1. Weather sentinels.
    sentinel_counts = {col: int((df[col] <= -900).sum()) for col in WEATHER_COLS}
    sentinel_rows = df[WEATHER_COLS].le(-900).any(axis=1)
    df["WeatherSentinelCount"] = df[WEATHER_COLS].le(-900).sum(axis=1).astype(int)
    df["WeatherImputed"] = (df["WeatherSentinelCount"] > 0).astype(int)

    for col in WEATHER_COLS:
        df.loc[df[col] <= -900, col] = pd.NA

    df = df.sort_values(["PlantName", "Date", "Capacity_MW"]).reset_index(drop=True)
    for col in WEATHER_COLS:
        df[col] = df.groupby("PlantName", group_keys=False)[col].transform(
            lambda series: series.ffill().bfill()
        )

    remaining_weather_missing = df[WEATHER_COLS].isna().any(axis=1)
    summary["weather_sentinel_counts_before"] = sentinel_counts
    summary["weather_sentinel_rows_before"] = int(sentinel_rows.sum())
    summary["weather_values_imputed"] = int(sum(sentinel_counts.values()))
    summary["dropped_unrecoverable_weather"] = int(remaining_weather_missing.sum())
    df = df.loc[~remaining_weather_missing].copy()

    # 2. Negative generation.
    negative_mask = df["DailyGeneration_MU"] < 0
    summary["negative_generation_rows"] = int(negative_mask.sum())
    df["GenerationWasNegative"] = negative_mask.astype(int)
    df.loc[negative_mask, "DailyGeneration_MU"] = 0.0

    # 7. Mapping provenance (metadata only).
    mapping_status = load_mapping_status(args.mapping)
    df = df.merge(
        mapping_status,
        on=["PlantName", "Type", "Capacity_MW"],
        how="left",
    )
    df["MappingStatus"] = df["MappingStatus"].fillna("NotInMapping")
    mapping_counts = df["MappingStatus"].value_counts().to_dict()
    summary["mapping_status_row_counts"] = {str(k): int(v) for k, v in mapping_counts.items()}

    # Deterministic output.
    df = df.sort_values(["PlantName", "Date", "Capacity_MW"]).reset_index(drop=True)
    df = df[OUTPUT_COLS]
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    summary["rows_out"] = int(len(df))
    summary["plants_out"] = int(df["PlantName"].nunique())
    summary["output"] = str(args.output)
    summary["date_range"] = {
        "start": str(df["Date"].min()),
        "end": str(df["Date"].max()),
    }
    summary["type_row_counts"] = {
        str(k): int(v) for k, v in df["Type"].value_counts().to_dict().items()
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("=" * 72)
    print("PLANT / WEATHER TRAINING DATASET BUILT")
    print("=" * 72)
    print(f"Canonical rows in       : {rows_in}")
    print(f"Rows out                : {len(df)}")
    print(f"Plants out              : {df['PlantName'].nunique()}")
    print(f"Weather values imputed  : {sum(sentinel_counts.values())} across {int(sentinel_rows.sum())} rows")
    print(f"Negative generation rows: {int(negative_mask.sum())} (clipped to 0.0 for modelling)")
    print(f"Date range              : {df['Date'].min()} to {df['Date'].max()}")
    print(f"\nSaved dataset : {args.output}")
    print(f"Saved summary : {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

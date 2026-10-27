"""Create the chronological per-plant train/test split.

Rule (deterministic, no shuffling, no random seed):
    For each plant, sort rows by Date.
    Earliest 80% of that plant's rows -> train
    Latest  20% of that plant's rows -> test

The split is written back into ``data/final/plant_features_dataset.csv`` as an
explicit ``_split`` column (``train`` / ``test``) because
``scripts/train_random_forest.py`` filters on it.  The same rows are also written to
``data/final/plant_train.csv`` and ``data/final/plant_test.csv`` for compatibility
with the original pipeline.

The script refuses to continue if any test row is chronologically earlier than a
train row for the same plant.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent

INPUT = BASE / "data/final/plant_features_dataset.csv"
FEATURES = BASE / "data/final/plant_features_dataset.csv"
TRAIN = BASE / "data/final/plant_train.csv"
TEST = BASE / "data/final/plant_test.csv"

TRAIN_RATIO = 0.80


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--features-out", type=Path, default=FEATURES)
    parser.add_argument("--train-out", type=Path, default=TRAIN)
    parser.add_argument("--test-out", type=Path, default=TEST)
    return parser.parse_args()


def assign_split(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["PlantName", "Date", "Capacity_MW"]).reset_index(drop=True)

    duplicate_keys = df.duplicated(subset=["PlantName", "Date"], keep=False)
    if duplicate_keys.any():
        sample = df.loc[duplicate_keys, ["PlantName", "Date", "Capacity_MW"]].head(10)
        raise ValueError(
            "Found duplicate (PlantName, Date) rows; chronological split is ambiguous.\n"
            f"{sample.to_string(index=False)}"
        )

    df["_split"] = pd.Series(index=df.index, dtype="object")

    for plant, group in df.groupby("PlantName", sort=True):
        ordered = group.sort_values(["Date", "Capacity_MW"])
        n_rows = len(ordered)

        if n_rows == 1:
            # A single observation cannot form both partitions.  Keep it in train and
            # report it rather than inventing a test row.
            n_train = 1
        else:
            n_train = int(n_rows * TRAIN_RATIO)
            n_train = min(max(n_train, 1), n_rows - 1)

        train_index = ordered.index[:n_train]
        test_index = ordered.index[n_train:]

        df.loc[train_index, "_split"] = "train"
        df.loc[test_index, "_split"] = "test"

        if len(test_index) > 0:
            latest_train = ordered.loc[train_index, "Date"].max()
            earliest_test = ordered.loc[test_index, "Date"].min()
            if earliest_test < latest_train:
                raise AssertionError(
                    f"Temporal order violation for plant {plant!r}: "
                    f"earliest test {earliest_test} < latest train {latest_train}"
                )

    if df["_split"].isna().any():
        raise AssertionError("Every row must receive a _split value")
    if not set(df["_split"].unique()).issubset({"train", "test"}):
        raise AssertionError(f"Unexpected _split values: {df['_split'].unique()}")

    return df


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(
            f"Feature dataset not found: {args.input}\n"
            "Run scripts/engineer_plant_features.py first."
        )

    df = pd.read_csv(args.input)
    if "_split" in df.columns:
        df = df.drop(columns="_split")

    df = assign_split(df)

    train = df[df["_split"] == "train"].copy()
    test = df[df["_split"] == "test"].copy()

    # Deterministic output order.
    df = df.sort_values(["PlantName", "Date", "Capacity_MW"]).reset_index(drop=True)
    train = train.sort_values(["PlantName", "Date", "Capacity_MW"]).reset_index(drop=True)
    test = test.sort_values(["PlantName", "Date", "Capacity_MW"]).reset_index(drop=True)

    args.features_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.features_out, index=False)
    train.to_csv(args.train_out, index=False)
    test.to_csv(args.test_out, index=False)

    plants = df["PlantName"].nunique()
    plants_with_test = test["PlantName"].nunique()

    print("=" * 72)
    print("CHRONOLOGICAL PER-PLANT TRAIN / TEST SPLIT")
    print("=" * 72)
    print(f"Total rows          : {len(df)}")
    print(f"Train rows          : {len(train)} ({len(train) / len(df):.2%})")
    print(f"Test rows           : {len(test)} ({len(test) / len(df):.2%})")
    print(f"Plants              : {plants}")
    print(f"Plants with test    : {plants_with_test}")
    print(f"Train date range    : {train['Date'].min()} to {train['Date'].max()}")
    print(f"Test date range     : {test['Date'].min()} to {test['Date'].max()}")
    print(f"Train types         : {train['Type'].value_counts().to_dict()}")
    print(f"Test types          : {test['Type'].value_counts().to_dict()}")

    violations = []
    for plant, group in df.groupby("PlantName"):
        plant_train = group[group["_split"] == "train"]["Date"]
        plant_test = group[group["_split"] == "test"]["Date"]
        if len(plant_train) and len(plant_test):
            if plant_test.min() < plant_train.max():
                violations.append(plant)
    print(f"Temporal violations : {len(violations)}")

    print(f"\nSaved features with _split : {args.features_out}")
    print(f"Saved train                : {args.train_out}")
    print(f"Saved test                 : {args.test_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

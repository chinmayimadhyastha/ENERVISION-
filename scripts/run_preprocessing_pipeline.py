"""Run the full reproducible preprocessing chain in the correct order.

Stages:
    1. build_plant_weather_training_dataset.py
    2. engineer_plant_features.py
    3. split_plant_dataset.py

Run from the repository root (or from anywhere; paths are resolved by each script):

    python scripts/run_preprocessing_pipeline.py

Use ``--skip-build`` to reuse an existing
``data/final/plant_weather_training_dataset.csv``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"


def run(stage: str, script: str, extra: list[str] | None = None) -> None:
    command = [sys.executable, str(SCRIPTS / script), *(extra or [])]
    print("\n" + "#" * 72)
    print(f"# {stage}")
    print("#" * 72)
    print("$ " + " ".join(command))
    completed = subprocess.run(command, cwd=BASE)
    if completed.returncode != 0:
        raise SystemExit(f"{stage} failed with exit code {completed.returncode}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=None)
    parser.add_argument("--skip-build", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.skip_build:
        extra = ["--canonical", str(args.canonical)] if args.canonical else []
        run("STAGE 1/3 - build plant/weather training dataset",
            "build_plant_weather_training_dataset.py", extra)
    else:
        print("Skipping stage 1 (--skip-build)")

    run("STAGE 2/3 - engineer plant-wise features", "engineer_plant_features.py")
    run("STAGE 3/3 - chronological per-plant split", "split_plant_dataset.py")

    print("\n" + "=" * 72)
    print("PREPROCESSING PIPELINE COMPLETE")
    print("=" * 72)
    print("Outputs:")
    print("  data/final/plant_weather_training_dataset.csv")
    print("  data/final/plant_features_dataset.csv  (includes _split)")
    print("  data/final/plant_train.csv")
    print("  data/final/plant_test.csv")
    print("  reports/data_quality_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

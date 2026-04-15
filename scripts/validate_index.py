#!/usr/bin/env python3
"""Validate the derived PTB-XL index used by the training pipeline."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = PROJECT_ROOT / "data" / "index_complete.parquet"
DEFAULT_DATA_ROOT = Path(
    os.environ.get("PTBXL_DATA_ROOT", str(PROJECT_ROOT / "ptb-xl" / "1.0.3"))
)

META_FEATURES = [
    "age_z",
    "sex01",
    "height_z",
    "weight_z",
    "bmi_z",
    "miss__height",
    "miss__weight",
    "miss__bmi",
]

MASK_FEATURES = [
    "mask__age",
    "mask__sex",
    "mask__height",
    "mask__weight",
    "mask__bmi",
    "mask__miss_height",
    "mask__miss_weight",
    "mask__miss_bmi",
]

REQUIRED_COLUMNS = [
    "ecg_id",
    "patient_id",
    "scp_codes",
    "strat_fold",
    "filename_lr",
    "filename_hr",
    "hea_path",
    *META_FEATURES,
    *MASK_FEATURES,
    "meta_present_any",
    "meta_present_strict",
]

BINARY_COLUMNS = [
    "sex01",
    "miss__height",
    "miss__weight",
    "miss__bmi",
    *MASK_FEATURES,
    "meta_present_any",
    "meta_present_strict",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the derived PTB-XL index used by EZNX_ATLAS_A."
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX,
        help="Parquet file to validate.",
    )
    parser.add_argument(
        "--data_root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Optional PTB-XL root used to verify header paths.",
    )
    parser.add_argument(
        "--check_path_count",
        type=int,
        default=10,
        help="Number of header paths to verify on disk. Use 0 to disable.",
    )
    return parser.parse_args()


def assert_required_columns(df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def assert_no_nans(df: pd.DataFrame) -> None:
    if df[META_FEATURES].isna().any().any():
        raise ValueError("NaN values detected in META_FEATURES.")
    if df[MASK_FEATURES].isna().any().any():
        raise ValueError("NaN values detected in MASK_FEATURES.")


def assert_binary_columns(df: pd.DataFrame) -> None:
    for column in BINARY_COLUMNS:
        values = set(pd.unique(df[column]))
        if not values.issubset({0, 1}):
            raise ValueError(f"Column {column} contains non-binary values: {sorted(values)}")


def assert_mask_consistency(df: pd.DataFrame) -> None:
    checks = {
        "height": (df["miss__height"] == (1 - df["mask__height"])).all(),
        "weight": (df["miss__weight"] == (1 - df["mask__weight"])).all(),
        "bmi": (df["miss__bmi"] == (1 - df["mask__bmi"])).all(),
        "miss_height_mask": (df["mask__miss_height"] == df["mask__height"]).all(),
        "miss_weight_mask": (df["mask__miss_weight"] == df["mask__weight"]).all(),
        "miss_bmi_mask": (df["mask__miss_bmi"] == df["mask__bmi"]).all(),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"Mask consistency checks failed: {failed}")


def assert_relative_hea_paths(df: pd.DataFrame) -> None:
    absolute = [value for value in df["hea_path"].astype(str) if Path(value).is_absolute()]
    if absolute:
        raise ValueError("hea_path contains absolute paths; expected repository-safe relative paths.")


def assert_path_alignment(df: pd.DataFrame) -> None:
    expected = df["filename_hr"].astype(str) + ".hea"
    if not expected.equals(df["hea_path"].astype(str)):
        raise ValueError("hea_path is not aligned with filename_hr + '.hea'.")


def check_header_files(df: pd.DataFrame, data_root: Path, count: int) -> None:
    if count <= 0:
        return

    total = len(df)
    sample_size = min(count, total)
    sample_indices = np.linspace(0, total - 1, sample_size, dtype=int)
    missing = []

    for index in sample_indices:
        relative_path = Path(str(df.iloc[index]["hea_path"]))
        full_path = data_root / relative_path
        if not full_path.exists():
            missing.append(str(full_path))

    if missing:
        raise FileNotFoundError(f"Missing header files: {missing[:5]}")


def main() -> None:
    args = parse_args()
    if not args.index.exists():
        raise FileNotFoundError(f"Index not found: {args.index}")

    df = pd.read_parquet(args.index)

    assert_required_columns(df)
    assert_no_nans(df)
    assert_binary_columns(df)
    assert_mask_consistency(df)
    assert_relative_hea_paths(df)
    assert_path_alignment(df)
    check_header_files(df, args.data_root, args.check_path_count)

    print(f"Index: {args.index}")
    print(f"Rows: {len(df)}")
    print("Validation checks: OK")
    print(
        "Split counts:",
        df["strat_fold"].value_counts().sort_index().to_dict(),
    )
    print(
        "Mask means:",
        df[["mask__age", "mask__sex", "mask__height", "mask__weight", "mask__bmi"]]
        .mean()
        .round(4)
        .to_dict(),
    )


if __name__ == "__main__":
    main()

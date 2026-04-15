"""Audit split integrity and potential data leakage in the derived PTB-XL index."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = PROJECT_ROOT / "data" / "index_complete.parquet"
DEFAULT_DATA_ROOT = Path(
    os.environ.get("PTBXL_DATA_ROOT", str(PROJECT_ROOT / "ptb-xl" / "1.0.3"))
)

REQUIRED_COLUMNS = [
    "ecg_id",
    "patient_id",
    "strat_fold",
    "filename_lr",
    "filename_hr",
]

OFFICIAL_COMPARE_COLUMNS = [
    "patient_id",
    "strat_fold",
    "filename_lr",
    "filename_hr",
]

PARTITIONS = {
    "train": list(range(1, 9)),
    "validation": [9],
    "test": [10],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit patient-level and record-level leakage in the derived PTB-XL index."
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX,
        help="Parquet index to audit.",
    )
    parser.add_argument(
        "--data_root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Optional PTB-XL root used to compare against the official metadata table.",
    )
    parser.add_argument(
        "--skip_official_check",
        action="store_true",
        help="Skip the comparison against ptbxl_database.csv.",
    )
    parser.add_argument(
        "--output_json",
        type=Path,
        default=None,
        help="Optional path for a machine-readable JSON audit report.",
    )
    parser.add_argument(
        "--output_markdown",
        type=Path,
        default=None,
        help="Optional path for a Markdown audit report.",
    )
    parser.add_argument(
        "--fail_on_issues",
        action="store_true",
        help="Exit with a non-zero status if any leakage or integrity issue is detected.",
    )
    return parser.parse_args()


def ensure_required_columns(df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for leakage audit: {missing}")


def split_frame(df: pd.DataFrame, folds: list[int]) -> pd.DataFrame:
    return df[df["strat_fold"].isin(folds)].copy()


def overlaps(left: pd.Series, right: pd.Series) -> Dict[str, Any]:
    left_set = set(left.dropna().tolist())
    right_set = set(right.dropna().tolist())
    common = sorted(left_set & right_set)
    return {
        "count": len(common),
        "examples": common[:10],
    }


def find_patients_across_multiple_folds(df: pd.DataFrame) -> Dict[str, Any]:
    grouped = (
        df.groupby("patient_id", dropna=True)["strat_fold"]
        .agg(lambda values: sorted({int(value) for value in values}))
    )
    leaking = grouped[grouped.map(len) > 1]
    examples = [
        {"patient_id": float(patient_id), "folds": folds}
        for patient_id, folds in leaking.head(10).items()
    ]
    return {"count": int(len(leaking)), "examples": examples}


def duplicate_count(df: pd.DataFrame, subset: list[str]) -> int:
    return int(df.duplicated(subset=subset).sum())


def partition_summary(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    summary: Dict[str, Dict[str, int]] = {}
    for name, folds in PARTITIONS.items():
        part = split_frame(df, folds)
        summary[name] = {
            "rows": int(len(part)),
            "unique_patients": int(part["patient_id"].nunique(dropna=True)),
            "unique_ecg_ids": int(part["ecg_id"].nunique()),
        }
    return summary


def fold_summary(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    grouped = (
        df.groupby("strat_fold")
        .agg(
            rows=("ecg_id", "size"),
            unique_patients=("patient_id", lambda series: series.nunique(dropna=True)),
        )
        .sort_index()
    )
    return {
        str(int(fold)): {
            "rows": int(values["rows"]),
            "unique_patients": int(values["unique_patients"]),
        }
        for fold, values in grouped.to_dict(orient="index").items()
    }


def compare_with_official(index_df: pd.DataFrame, data_root: Path) -> Dict[str, Any]:
    db_path = data_root / "ptbxl_database.csv"
    if not db_path.exists():
        return {
            "checked": False,
            "db_path": str(db_path),
            "reason": "ptbxl_database.csv not found",
        }

    official_df = pd.read_csv(
        db_path,
        usecols=["ecg_id", *OFFICIAL_COMPARE_COLUMNS],
    )
    merged = index_df[["ecg_id", *OFFICIAL_COMPARE_COLUMNS]].merge(
        official_df,
        on="ecg_id",
        how="outer",
        suffixes=("_index", "_official"),
        indicator=True,
    )

    report: Dict[str, Any] = {
        "checked": True,
        "db_path": str(db_path),
        "missing_in_index": int((merged["_merge"] == "right_only").sum()),
        "missing_in_official": int((merged["_merge"] == "left_only").sum()),
        "column_mismatches": {},
    }

    both = merged[merged["_merge"] == "both"].copy()
    for column in OFFICIAL_COMPARE_COLUMNS:
        left = both[f"{column}_index"]
        right = both[f"{column}_official"]
        mismatch_mask = ~(left.eq(right) | (left.isna() & right.isna()))
        mismatches = both.loc[mismatch_mask, ["ecg_id", f"{column}_index", f"{column}_official"]]
        report["column_mismatches"][column] = {
            "count": int(len(mismatches)),
            "examples": mismatches.head(5).to_dict(orient="records"),
        }

    return report


def build_report(index_df: pd.DataFrame, data_root: Path, skip_official_check: bool) -> Dict[str, Any]:
    ensure_required_columns(index_df)

    train = split_frame(index_df, PARTITIONS["train"])
    validation = split_frame(index_df, PARTITIONS["validation"])
    test = split_frame(index_df, PARTITIONS["test"])

    report: Dict[str, Any] = {
        "index_path": None,
        "dataset": {
            "rows": int(len(index_df)),
            "unique_ecg_ids": int(index_df["ecg_id"].nunique()),
            "unique_filename_hr": int(index_df["filename_hr"].nunique()),
            "unique_filename_lr": int(index_df["filename_lr"].nunique()),
            "unique_patients": int(index_df["patient_id"].nunique(dropna=True)),
            "missing_patient_id": int(index_df["patient_id"].isna().sum()),
        },
        "duplicates": {
            "ecg_id": duplicate_count(index_df, ["ecg_id"]),
            "filename_hr": duplicate_count(index_df, ["filename_hr"]),
            "filename_lr": duplicate_count(index_df, ["filename_lr"]),
        },
        "patients_across_multiple_folds": find_patients_across_multiple_folds(index_df),
        "partition_summary": partition_summary(index_df),
        "fold_summary": fold_summary(index_df),
        "overlaps": {
            "patient_id": {
                "train_vs_validation": overlaps(train["patient_id"], validation["patient_id"]),
                "train_vs_test": overlaps(train["patient_id"], test["patient_id"]),
                "validation_vs_test": overlaps(validation["patient_id"], test["patient_id"]),
            },
            "ecg_id": {
                "train_vs_validation": overlaps(train["ecg_id"], validation["ecg_id"]),
                "train_vs_test": overlaps(train["ecg_id"], test["ecg_id"]),
                "validation_vs_test": overlaps(validation["ecg_id"], test["ecg_id"]),
            },
            "filename_hr": {
                "train_vs_validation": overlaps(train["filename_hr"], validation["filename_hr"]),
                "train_vs_test": overlaps(train["filename_hr"], test["filename_hr"]),
                "validation_vs_test": overlaps(validation["filename_hr"], test["filename_hr"]),
            },
        },
        "records_per_patient": {
            "max": int(index_df.groupby("patient_id", dropna=True).size().max()),
            "mean": float(index_df.groupby("patient_id", dropna=True).size().mean()),
        },
    }

    if skip_official_check:
        report["official_consistency"] = {
            "checked": False,
            "reason": "skipped by user",
        }
    else:
        report["official_consistency"] = compare_with_official(index_df, data_root)

    issues = collect_issues(report)
    report["issues"] = issues
    report["status"] = "PASS" if not issues else "FAIL"
    return report


def collect_issues(report: Dict[str, Any]) -> list[str]:
    issues: list[str] = []

    if report["dataset"]["missing_patient_id"] > 0:
        issues.append("Missing patient_id values detected.")

    for field, count in report["duplicates"].items():
        if count > 0:
            issues.append(f"Duplicate values detected for {field}: {count}.")

    if report["patients_across_multiple_folds"]["count"] > 0:
        issues.append("Some patients appear in more than one stratified fold.")

    for group_name, metrics in report["overlaps"].items():
        for pair_name, overlap_report in metrics.items():
            if overlap_report["count"] > 0:
                issues.append(
                    f"Overlap detected for {group_name} between {pair_name}: {overlap_report['count']}."
                )

    official = report["official_consistency"]
    if official.get("checked"):
        if official["missing_in_index"] > 0:
            issues.append("Official PTB-XL rows are missing from the audited index.")
        if official["missing_in_official"] > 0:
            issues.append("Audited index contains ecg_id values missing from official PTB-XL metadata.")
        for column, mismatch_report in official["column_mismatches"].items():
            if mismatch_report["count"] > 0:
                issues.append(f"Mismatch against official PTB-XL column {column}: {mismatch_report['count']}.")

    return issues


def report_to_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Data leakage audit",
        "",
        f"Status: **{report['status']}**",
        "",
        "## Dataset summary",
        "",
        f"- Rows: {report['dataset']['rows']}",
        f"- Unique ECG IDs: {report['dataset']['unique_ecg_ids']}",
        f"- Unique patients: {report['dataset']['unique_patients']}",
        f"- Missing patient IDs: {report['dataset']['missing_patient_id']}",
        "",
        "## Duplicate checks",
        "",
        f"- Duplicate `ecg_id`: {report['duplicates']['ecg_id']}",
        f"- Duplicate `filename_hr`: {report['duplicates']['filename_hr']}",
        f"- Duplicate `filename_lr`: {report['duplicates']['filename_lr']}",
        "",
        "## Partition summary",
        "",
        "| Partition | Rows | Unique patients | Unique ECG IDs |",
        "|-----------|------|-----------------|----------------|",
    ]

    for partition, values in report["partition_summary"].items():
        lines.append(
            f"| {partition} | {values['rows']} | {values['unique_patients']} | {values['unique_ecg_ids']} |"
        )

    lines.extend(
        [
            "",
            "## Patient-level leakage checks",
            "",
            f"- Patients appearing in more than one fold: {report['patients_across_multiple_folds']['count']}",
            f"- Train vs validation patient overlap: {report['overlaps']['patient_id']['train_vs_validation']['count']}",
            f"- Train vs test patient overlap: {report['overlaps']['patient_id']['train_vs_test']['count']}",
            f"- Validation vs test patient overlap: {report['overlaps']['patient_id']['validation_vs_test']['count']}",
            "",
            "## Record-level leakage checks",
            "",
            f"- Train vs validation ECG ID overlap: {report['overlaps']['ecg_id']['train_vs_validation']['count']}",
            f"- Train vs test ECG ID overlap: {report['overlaps']['ecg_id']['train_vs_test']['count']}",
            f"- Validation vs test ECG ID overlap: {report['overlaps']['ecg_id']['validation_vs_test']['count']}",
            f"- Train vs validation `filename_hr` overlap: {report['overlaps']['filename_hr']['train_vs_validation']['count']}",
            f"- Train vs test `filename_hr` overlap: {report['overlaps']['filename_hr']['train_vs_test']['count']}",
            f"- Validation vs test `filename_hr` overlap: {report['overlaps']['filename_hr']['validation_vs_test']['count']}",
            "",
            "## Official PTB-XL consistency",
            "",
        ]
    )

    official = report["official_consistency"]
    if official.get("checked"):
        lines.extend(
            [
                f"- Missing in index: {official['missing_in_index']}",
                f"- Missing in official metadata: {official['missing_in_official']}",
            ]
        )
        for column, mismatch_report in official["column_mismatches"].items():
            lines.append(f"- Column mismatch `{column}`: {mismatch_report['count']}")
    else:
        lines.append(f"- Official comparison skipped: {official.get('reason', 'unknown reason')}")

    lines.extend(["", "## Issues", ""])
    if report["issues"]:
        for issue in report["issues"]:
            lines.append(f"- {issue}")
    else:
        lines.append("- No leakage or split-integrity issue detected.")

    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not args.index.exists():
        raise FileNotFoundError(f"Index not found: {args.index}")

    index_df = pd.read_parquet(args.index)
    report = build_report(index_df, args.data_root, args.skip_official_check)
    report["index_path"] = str(args.index)

    markdown = report_to_markdown(report)

    print("=" * 80)
    print("DATA LEAKAGE AUDIT")
    print("=" * 80)
    print(f"Index:   {args.index}")
    print(f"Status:  {report['status']}")
    print(f"Rows:    {report['dataset']['rows']}")
    print(f"Patients spanning multiple folds: {report['patients_across_multiple_folds']['count']}")
    print(f"Train/validation patient overlap: {report['overlaps']['patient_id']['train_vs_validation']['count']}")
    print(f"Train/test patient overlap:       {report['overlaps']['patient_id']['train_vs_test']['count']}")
    print(f"Validation/test patient overlap:  {report['overlaps']['patient_id']['validation_vs_test']['count']}")
    print(f"Duplicate ecg_id rows:            {report['duplicates']['ecg_id']}")
    print(f"Duplicate filename_hr rows:       {report['duplicates']['filename_hr']}")
    if report["official_consistency"].get("checked"):
        print("Official PTB-XL consistency:      checked")
    else:
        print(f"Official PTB-XL consistency:      skipped ({report['official_consistency'].get('reason', 'n/a')})")

    if args.output_json is not None:
        write_json(args.output_json, report)
        print(f"JSON report: {args.output_json}")

    if args.output_markdown is not None:
        write_markdown(args.output_markdown, markdown)
        print(f"Markdown report: {args.output_markdown}")

    if report["issues"]:
        print("\nIssues:")
        for issue in report["issues"]:
            print(f"- {issue}")
    else:
        print("\nNo leakage or split-integrity issue detected.")

    if args.fail_on_issues and report["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

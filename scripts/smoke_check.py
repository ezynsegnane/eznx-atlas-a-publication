#!/usr/bin/env python3
"""Repository-level smoke checks for a public release."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

COMPILE_TARGETS = [
    "atlas_a_v5_multiseed.py",
    "atlas_a_v5_optimized.py",
    "run_multiseed_experiments.py",
    "analyze_multiseed_results.py",
    "eznx_loader_v2.py",
    "eznx_model_v5.py",
    "scripts/build_index.py",
    "scripts/validate_index.py",
    "scripts/audit_data_leakage.py",
]

HELP_TARGETS = [
    ["atlas_a_v5_multiseed.py", "--help"],
    ["atlas_a_v5_optimized.py", "--help"],
    ["run_multiseed_experiments.py", "--help"],
    ["analyze_multiseed_results.py", "--help"],
    ["scripts/build_index.py", "--help"],
    ["scripts/validate_index.py", "--help"],
    ["scripts/audit_data_leakage.py", "--help"],
]


def run_command(command: list[str]) -> None:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def main() -> int:
    print("[1/3] Compiling Python entry points...")
    compile_cmd = [sys.executable, "-m", "py_compile"]
    compile_cmd.extend(str(REPO_ROOT / rel_path) for rel_path in COMPILE_TARGETS)
    run_command(compile_cmd)
    print("[OK] Compilation passed.")

    print("[2/3] Checking command-line interfaces...")
    for help_target in HELP_TARGETS:
        run_command([sys.executable, *help_target])
    print("[OK] Command-line interfaces passed.")

    print("[3/3] Running a dry-run orchestrator smoke test...")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        dry_run_cmd = [
            sys.executable,
            "run_multiseed_experiments.py",
            "--data_root",
            str(REPO_ROOT / "ptb-xl" / "1.0.3"),
            "--index_path",
            str(REPO_ROOT / "data" / "index_complete.parquet"),
            "--runs_dir",
            str(temp_path / "runs"),
            "--variants",
            "none",
            "--seeds",
            "2024",
            "--dry-run",
        ]
        run_command(dry_run_cmd)
    print("[OK] Dry-run smoke test passed.")

    print("[DONE] Repository smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

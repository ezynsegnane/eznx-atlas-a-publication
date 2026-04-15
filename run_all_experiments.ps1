param(
    [ValidateSet("all", "quick", "resume", "analyze", "single")]
    [string]$Mode = "quick",
    [string]$DataRoot = $env:PTBXL_DATA_ROOT,
    [string]$IndexPath = (Join-Path $PSScriptRoot "data\\index_complete.parquet"),
    [string]$RunsDir = (Join-Path $PSScriptRoot "runs"),
    [string]$Variant = "demo+anthro",
    [int]$Seed = 2026,
    [string]$Python = "python"
)

if (-not $DataRoot) {
    throw "Set PTBXL_DATA_ROOT or pass -DataRoot with the PTB-XL waveform directory."
}

if (-not (Test-Path $DataRoot)) {
    throw "DataRoot not found: $DataRoot"
}

if (-not (Test-Path $IndexPath)) {
    throw "IndexPath not found: $IndexPath"
}

New-Item -ItemType Directory -Force -Path $RunsDir | Out-Null

switch ($Mode) {
    "all" {
        & $Python "run_multiseed_experiments.py" --data_root $DataRoot --index_path $IndexPath --runs_dir $RunsDir
    }
    "quick" {
        & $Python "run_multiseed_experiments.py" --data_root $DataRoot --index_path $IndexPath --runs_dir $RunsDir --seeds 2024 2025 2026
    }
    "resume" {
        & $Python "run_multiseed_experiments.py" --data_root $DataRoot --index_path $IndexPath --runs_dir $RunsDir --resume
    }
    "analyze" {
        & $Python "analyze_multiseed_results.py" --runs_dir $RunsDir --output_dir (Join-Path $RunsDir "analysis")
    }
    "single" {
        & $Python "atlas_a_v5_multiseed.py" --variant $Variant --seed $Seed --data_root $DataRoot --index_path $IndexPath --runs_dir $RunsDir
    }
}

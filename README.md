# EZNX_ATLAS_A

This repository contains the training, ablation, and statistical validation pipeline used for multi-label ECG classification experiments on PTB-XL with structured metadata.

The `v5` suffix retained in some script filenames is an internal development identifier used to preserve exact experiment provenance. It does not indicate previously published repository or article versions.

## Author

- Ezyn SEGNANE
- FST, Universite de Nouakchott, Nouakchott, Mauritanie
- Correspondence: ezynsegnane@gmail.com

The publication workflow is centered on three scripts:

- `atlas_a_v5_multiseed.py` runs one seed-aware experiment and exports per-run JSON outputs.
- `run_multiseed_experiments.py` launches the full ablation x seed campaign.
- `analyze_multiseed_results.py` aggregates runs, computes confidence intervals and Wilcoxon tests, and exports Markdown, LaTeX, and JSON reports.

The repository also ships a clean, reproducible index-construction pipeline for regenerating the derived metadata parquet files from raw PTB-XL.

## Repository layout

- `atlas_a_v5_multiseed.py`: main paper-grade training and evaluation script.
- `atlas_a_v5_optimized.py`: single-seed optimized configuration kept for reference.
- `run_multiseed_experiments.py`: batch launcher for the complete study.
- `analyze_multiseed_results.py`: statistical post-processing of completed runs.
- `run_all_experiments.ps1`: Windows helper for common execution modes.
- `eznx_model_v5.py`: multimodal model definition.
- `eznx_loader_v2.py`: PTB-XL loader and metadata ablation logic.
- `scripts/build_index.py`: canonical builder for `index_complete.parquet`.
- `scripts/validate_index.py`: integrity checks for generated index files.
- `scripts/audit_data_leakage.py`: patient-level and record-level leakage audit.
- `data/index_complete.parquet`: derived index used by the experiments.
- `docs/reproducibility.md`: exact split, seed, and execution notes.
- `docs/index_construction.md`: metadata preprocessing and index-generation details.
- `docs/data_leakage_audit.md`: split-integrity audit and leakage-check protocol.
- `docs/publishing_checklist.md`: final manual steps before public release.

## Data requirements

This repository does not redistribute PTB-XL waveform files. Researchers must obtain PTB-XL separately and point the code to a local waveform directory through either:

- the `PTBXL_DATA_ROOT` environment variable, or
- the `--data_root` command-line argument.

The code expects access to the WFDB records and `scp_statements.csv`.

## Accessing PTB-XL

PTB-XL is available from the official PhysioNet project page:

- PhysioNet dataset page: https://physionet.org/content/ptb-xl/1.0.3/
- Version-specific DOI used by this repository: https://doi.org/10.13026/kfzx-aw45

Download the dataset from PhysioNet, then point this repository to the local directory that contains:

- `ptbxl_database.csv`
- `scp_statements.csv`
- `records100/`
- `records500/`

This repository was prepared against PTB-XL version `1.0.3`.

## Citing PTB-XL

If you use this repository, please also cite the PTB-XL dataset itself. The official PhysioNet page asks users to cite:

- Wagner P, Strodthoff N, Bousseljot RD, Samek W, Schaeffter T. PTB-XL, a large publicly available electrocardiography dataset. PhysioNet, version 1.0.3, 2022. DOI: `10.13026/kfzx-aw45`
- Wagner P, Strodthoff N, Bousseljot RD, Kreiseler D, Lunze FI, Samek W, Schaeffter T. PTB-XL: A Large Publicly Available ECG Dataset. Scientific Data, 2020. DOI: `10.1038/s41597-020-0495-6`

PTB-XL is distributed by PhysioNet under CC BY 4.0. Users of this repository remain responsible for complying with the upstream PTB-XL and PhysioNet attribution requirements.

## Rebuilding the derived index

The versioned `data/index_complete.parquet` can be regenerated from raw PTB-XL metadata with:

```bash
python scripts/build_index.py \
  --data_root /path/to/ptb-xl/1.0.3 \
  --output data/index_complete.parquet
```

If you also want the intermediate metadata core file used during development:

```bash
python scripts/build_index.py \
  --data_root /path/to/ptb-xl/1.0.3 \
  --output data/index_complete.parquet \
  --core_output data/index_mm_core.parquet
```

Validate a built index with:

```bash
python scripts/validate_index.py \
  --index data/index_complete.parquet \
  --data_root /path/to/ptb-xl/1.0.3
```

## Auditing data leakage

The repository includes a dedicated audit for patient-level and record-level leakage:

```bash
python scripts/audit_data_leakage.py \
  --index data/index_complete.parquet \
  --data_root /path/to/ptb-xl/1.0.3 \
  --fail_on_issues
```

Optional machine-readable and Markdown reports:

```bash
python scripts/audit_data_leakage.py \
  --index data/index_complete.parquet \
  --data_root /path/to/ptb-xl/1.0.3 \
  --output_json runs/analysis/data_leakage_audit.json \
  --output_markdown runs/analysis/data_leakage_audit.md
```

## Environment setup

`requirements.txt` captures the Python packages used in the local environment where this repository was prepared. An equivalent Conda environment is also provided in `environment.yml`.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Or with Conda:

```bash
conda env create -f environment.yml
conda activate eznx-atlas-a
```

## Quality control

This repository includes a local and CI-compatible smoke check:

```bash
python scripts/smoke_check.py
```

The smoke check compiles the main Python entry points, verifies their command-line interfaces, and runs a dry-run of the multi-seed orchestrator without launching a full experiment.

## Reproducing a single run

```bash
python atlas_a_v5_multiseed.py \
  --variant demo+anthro \
  --seed 2026 \
  --data_root /path/to/ptb-xl/1.0.3 \
  --index_path data/index_complete.parquet \
  --runs_dir runs
```

## Reproducing the full multi-seed study

```bash
python run_multiseed_experiments.py \
  --data_root /path/to/ptb-xl/1.0.3 \
  --index_path data/index_complete.parquet \
  --runs_dir runs \
  --resume
```

By default the launcher evaluates the three metadata variants (`none`, `demo`, `demo+anthro`) over the ten seeds:

`2024 2025 2026 2027 2028 2029 2030 2031 2032 2033`

Windows users can also use the PowerShell helper:

```powershell
$env:PTBXL_DATA_ROOT = "C:\path\to\ptb-xl\1.0.3"
.\run_all_experiments.ps1 -Mode quick
```

## Statistical analysis

```bash
python analyze_multiseed_results.py \
  --runs_dir runs \
  --output_dir runs/analysis \
  --n_bootstrap 10000 \
  --bootstrap_seed 2026
```

The analysis exports:

- `statistical_analysis_report.md`
- `table_results_latex.tex`
- `statistical_analysis_full.json`

## Reproducibility notes

- Data split: folds 1-8 for training, fold 9 for validation, fold 10 for test.
- Seed control is enforced for Python, NumPy, and PyTorch.
- The statistical bootstrap is deterministic by default through `--bootstrap_seed`.
- The derived index can be rebuilt from raw PTB-XL with `scripts/build_index.py`.
- The split-integrity audit can be rerun from the published index with `scripts/audit_data_leakage.py`.
- Experiment outputs are written to `runs/` and intentionally excluded from version control.

## Citation and licensing

- The code in this repository is released under the MIT License. See `LICENSE`.
- Citation metadata is provided in `CITATION.cff`.
- `data/index_complete.parquet` is a derived artifact based on PTB-XL metadata; users must also comply with PTB-XL attribution and reuse conditions described in `data/README.md`.

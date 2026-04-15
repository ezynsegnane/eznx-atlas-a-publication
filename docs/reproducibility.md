# Reproducibility

## Experimental split

- Training folds: 1-8
- Validation fold: 9
- Test fold: 10

## Metadata ablations

- `none`: ECG only
- `demo`: ECG plus demographic features
- `demo+anthro`: ECG plus all structured metadata used in the paper

## Default seed panel

The full multi-seed study uses:

`2024 2025 2026 2027 2028 2029 2030 2031 2032 2033`

## Determinism

The training scripts explicitly seed:

- Python `random`
- NumPy
- PyTorch CPU
- PyTorch CUDA, when available

They also enable deterministic CuDNN mode and disable benchmarking.

The statistical analysis script uses a deterministic bootstrap seed by default (`--bootstrap_seed 2026`) so that confidence intervals can be regenerated exactly.

## Index derivation

The repository includes a canonical `scripts/build_index.py` script that regenerates `data/index_complete.parquet` from raw PTB-XL metadata.

The builder uses:

- conservative cleaning thresholds for age, height, weight, and BMI,
- train-only median imputation on folds 1-8,
- train-only z-score normalization on folds 1-8,
- relative `hea_path` values instead of machine-local absolute paths.

## Leakage audit

The repository includes a dedicated `scripts/audit_data_leakage.py` script to document split integrity from the published index.

The audit checks:

- no patient overlap between training, validation, and test,
- no duplicated ECG or waveform identifiers,
- no patient spanning multiple folds,
- optional consistency against the official PTB-XL metadata table.

## Expected outputs

Each run produces:

- one checkpoint file: `best_model_v5_<variant>_seed<seed>.pt`
- one JSON report: `results_<variant>_seed<seed>.json`

The aggregate analysis produces:

- one Markdown report
- one LaTeX table
- one full JSON summary





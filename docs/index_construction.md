# Index construction

## Purpose

`data/index_complete.parquet` is a derived artifact built from the official PTB-XL metadata table plus the metadata preprocessing used in the experiments.

The repository includes a canonical builder:

```bash
python scripts/build_index.py --data_root /path/to/ptb-xl/1.0.3 --output data/index_complete.parquet
```

An optional intermediate file can also be written:

```bash
python scripts/build_index.py \
  --data_root /path/to/ptb-xl/1.0.3 \
  --output data/index_complete.parquet \
  --core_output data/index_mm_core.parquet
```

## Source columns

The builder reads the following columns from `ptbxl_database.csv`:

- `ecg_id`
- `patient_id`
- `strat_fold`
- `scp_codes`
- `filename_lr`
- `filename_hr`
- `age`
- `sex`
- `height`
- `weight`

## Preprocessing steps

1. Restrict age, height, and weight to conservative physiological ranges:
   - age: `[0, 120]`
   - height: `[120, 210]` cm
   - weight: `[30, 250]` kg
2. Compute raw BMI from height and weight.
3. Restrict BMI to `[10, 60]`.
4. Build binary presence masks from the cleaned values.
5. Build missingness indicators for anthropometric variables.
6. Fit imputations and z-score normalization on training folds 1-8 only.

## Derived metadata

The final metadata vector used by the model is:

- `age_z`
- `sex01`
- `height_z`
- `weight_z`
- `bmi_z`
- `miss__height`
- `miss__weight`
- `miss__bmi`

The corresponding mask vector is:

- `mask__age`
- `mask__sex`
- `mask__height`
- `mask__weight`
- `mask__bmi`
- `mask__miss_height`
- `mask__miss_weight`
- `mask__miss_bmi`

## Outputs

`index_complete.parquet` contains the metadata features above together with:

- `ecg_id`
- `patient_id`
- `scp_codes`
- `strat_fold`
- `filename_lr`
- `filename_hr`
- `hea_path`

`hea_path` is stored as a repository-safe relative path (`filename_hr + ".hea"`), not as a machine-local absolute path.

`patient_id` is kept intentionally so that downstream users can audit patient-level leakage from the published index.

## Validation

Use the validator before publishing or retraining:

```bash
python scripts/validate_index.py --index data/index_complete.parquet --data_root /path/to/ptb-xl/1.0.3
```

The validator checks:

- required columns
- absence of NaNs in metadata tensors
- binary-mask integrity
- consistency between `miss__*` and `mask__*`
- relative path storage in `hea_path`
- alignment between `filename_hr` and `hea_path`

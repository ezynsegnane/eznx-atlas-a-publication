# Data leakage audit

## Purpose

The repository includes a canonical split-integrity audit for the derived PTB-XL index:

```bash
python scripts/audit_data_leakage.py --index data/index_complete.parquet --data_root /path/to/ptb-xl/1.0.3
```

This audit is designed to document and verify that:

- patients do not cross training, validation, and test partitions,
- ECG identifiers are unique,
- waveform file identifiers are unique,
- the retained `patient_id`, `strat_fold`, and waveform file columns remain consistent with the official PTB-XL metadata table.

## What is checked

The script audits:

1. Required columns for leakage analysis:
   - `ecg_id`
   - `patient_id`
   - `strat_fold`
   - `filename_lr`
   - `filename_hr`
2. Duplicate records by:
   - `ecg_id`
   - `filename_lr`
   - `filename_hr`
3. Patient leakage across:
   - training (folds 1-8)
   - validation (fold 9)
   - test (fold 10)
4. Patients assigned to more than one fold.
5. Optional consistency against the official `ptbxl_database.csv` for:
   - `patient_id`
   - `strat_fold`
   - `filename_lr`
   - `filename_hr`

## Outputs

By default the script prints a terminal summary.

Optional reports:

```bash
python scripts/audit_data_leakage.py \
  --index data/index_complete.parquet \
  --data_root /path/to/ptb-xl/1.0.3 \
  --output_json runs/analysis/data_leakage_audit.json \
  --output_markdown runs/analysis/data_leakage_audit.md
```

Use `--fail_on_issues` to make the script exit non-zero if any leakage or split-integrity issue is detected.

## Why `patient_id` is kept in the published index

`patient_id` is retained intentionally because it enables independent verification that no patient spans training, validation, and test partitions.

Without `patient_id`, downstream users could rerun the model but would not be able to audit patient-level leakage from the published index alone.

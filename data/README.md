# Data notes

`index_complete.parquet` is included because it is a compact derived index required by the training and analysis scripts.

The published copy of the parquet stores relative record paths only. No machine-local absolute paths are kept in `hea_path`.

The repository code is released under the MIT License. The derived parquet remains based on PTB-XL metadata, so downstream users must also follow the PTB-XL and PhysioNet attribution and reuse conditions that apply to the source dataset.

The same file can be regenerated with:

```bash
python scripts/build_index.py --data_root /path/to/ptb-xl/1.0.3 --output data/index_complete.parquet
```

Validate it with:

```bash
python scripts/validate_index.py --index data/index_complete.parquet --data_root /path/to/ptb-xl/1.0.3
```

Raw PTB-XL waveform files are not included in this repository. Place them in a local directory and pass that location through `PTBXL_DATA_ROOT` or `--data_root`.

Suggested local layout:

```text
eznx-atlas-a-publication/
  data/
    index_complete.parquet
  ptb-xl/
    1.0.3/
      records100/
      records500/
      scp_statements.csv
```

If the waveform files live elsewhere, keep `data/index_complete.parquet` in the repository and pass the external waveform path on the command line.

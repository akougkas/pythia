---
case: case_003_data_pipeline
framework: claude_code
model: claude-sonnet-4-6
provider: anthropic
session_id: 5a47a4c9-1b22-4a2d-9320-bc3cbbbc1386
duration_ms: 113320
duration_wall_s: 116.6
cost_usd: 0.1739964
num_turns: 5
timestamp: 2026-03-19T14:10:29.932499+00:00
error: None
---

# Plan

# Plan: CSV Data Pipeline (Case 003)

## Context

The working directory is empty, so sample files must be created from scratch. The goal is a production-quality, configurable CSV data pipeline using `pandas` and YAML-defined transforms. The pipeline reads all CSVs from an input directory, chains configurable transforms (filter, rename, derived columns), and writes results to an output directory. Dry-run mode and configurable logging are required.

**Assumption:** Sample CSVs use a sales/transactions domain (date, customer_id, product, quantity, unit_price, region, status) — a realistic, self-explanatory dataset for demonstrating all three transform types.

---

## Files to Create

All files go in `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/`.

```
WorkingDir/
├── input/
│   ├── sales_jan.csv
│   └── sales_feb.csv
├── output/               (created at runtime)
├── pipeline.py
├── transforms.py
├── pipeline.yaml
└── test_pipeline.py
```

---

## Step 1 — Sample CSV Files

### `input/sales_jan.csv` and `input/sales_feb.csv`

Columns: `date, customer_id, product, quantity, unit_price, region, status`

Include a mix of `status` values (`completed`, `pending`, `cancelled`) and varied regions/products so filters are meaningful. ~10 rows per file.

---

## Step 2 — `transforms.py`

Define one function per transform type. Each function accepts a `pd.DataFrame` plus keyword config args, and returns a `pd.DataFrame`.

### Functions

| Function | Signature | Description |
|---|---|---|
| `filter_rows` | `(df, column, operator, value)` | Keep rows where `column <op> value`. Operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not_in`. |
| `rename_columns` | `(df, mapping: dict)` | Rename columns using the provided old→new mapping. |
| `add_column` | `(df, name, expression)` | Evaluate a pandas `eval()`-compatible expression string and assign the result to a new column `name`. |

### Registry

Expose a `TRANSFORMS: dict[str, Callable]` mapping name strings to functions — used by the pipeline orchestrator for dynamic dispatch.

```python
TRANSFORMS = {
    "filter_rows": filter_rows,
    "rename_columns": rename_columns,
    "add_column": add_column,
}
```

### Error Handling

- `filter_rows`: raise `ValueError` for unknown operators; raise `KeyError` if column not found.
- `rename_columns`: warn (log) if a source column is missing, skip it gracefully.
- `add_column`: wrap `eval()` in try/except, re-raise with descriptive message.

---

## Step 3 — `pipeline.yaml`

Demonstrate all three transforms chained:

```yaml
pipeline:
  input_dir: input
  output_dir: output
  log_level: INFO        # DEBUG | INFO | WARNING

  steps:
    - name: filter_rows
      params:
        column: status
        operator: "=="
        value: "completed"

    - name: rename_columns
      params:
        mapping:
          customer_id: cust_id
          unit_price: price_usd

    - name: add_column
      params:
        name: revenue
        expression: "quantity * price_usd"
```

---

## Step 4 — `pipeline.py`

### Structure

```
main()
  └── parse CLI args (argparse)
        --config   path to pipeline.yaml  (default: pipeline.yaml)
        --dry-run  flag
        --log-level  override yaml log_level
  └── setup_logging(level)
  └── run_pipeline(config, dry_run)
        └── discover_csv_files(input_dir) -> list[Path]
        └── for each file:
              └── load_csv(path) -> DataFrame
              └── apply_transforms(df, steps) -> DataFrame
                    └── for each step: TRANSFORMS[name](df, **params)
              └── if not dry_run: save_csv(df, output_dir, filename)
              └── log summary (rows in/out, columns, path)
```

### Key Implementation Details

- **Config loading:** `yaml.safe_load()` — no external YAML library needed beyond PyYAML.
- **Logging:** `logging.basicConfig` with level from config (overridable via CLI `--log-level`). Log each file processed, each step applied, row counts before/after each step.
- **Dry-run:** All steps run normally (transforms applied, row counts computed), but `save_csv` is skipped. Log `[DRY RUN] Would write: <path>` instead.
- **Output directory:** Created with `output_dir.mkdir(parents=True, exist_ok=True)` if not in dry-run mode.
- **Input discovery:** `sorted(Path(input_dir).glob("*.csv"))` — alphabetical, reproducible.
- **CLI entry point:** `if __name__ == "__main__": main()`

### CLI Usage Examples

```bash
python pipeline.py                          # uses pipeline.yaml, writes output/
python pipeline.py --dry-run                # no files written
python pipeline.py --log-level DEBUG        # verbose per-row logging
python pipeline.py --config custom.yaml     # alternate config
```

---

## Step 5 — `test_pipeline.py`

Use `pytest` + `pandas` only (no mocking library needed for core tests).

### Test Cases

| Test | What it covers |
|---|---|
| `test_filter_rows_equals` | `status == 'completed'` keeps only matching rows |
| `test_filter_rows_greater_than` | numeric `>` operator |
| `test_filter_rows_in` | `in` operator with list value |
| `test_filter_rows_unknown_operator` | raises `ValueError` |
| `test_rename_columns` | columns renamed correctly, others unchanged |
| `test_rename_columns_missing_key` | missing source column skipped gracefully |
| `test_add_column` | `revenue = quantity * price_usd` computed correctly |
| `test_add_column_bad_expression` | raises error with descriptive message |
| `test_apply_transforms_chain` | filter → rename → add_column end-to-end |
| `test_pipeline_dry_run` | output dir not created / no files written |
| `test_pipeline_writes_output` | output CSV exists with correct columns after run |

Use `tmp_path` pytest fixture for file I/O tests. Create minimal in-memory DataFrames for transform unit tests.

---

## Critical Files

| File | Role |
|---|---|
| `WorkingDir/transforms.py` | All transform logic + TRANSFORMS registry |
| `WorkingDir/pipeline.py` | Orchestrator, CLI, logging |
| `WorkingDir/pipeline.yaml` | Example config (also used in integration tests) |
| `WorkingDir/test_pipeline.py` | Unit + integration tests |
| `WorkingDir/input/sales_jan.csv` | Sample data |
| `WorkingDir/input/sales_feb.csv` | Sample data |

---

## Verification

```bash
cd WorkingDir

# 1. Dry run — no output/ dir created
python pipeline.py --dry-run --log-level DEBUG

# 2. Full run — output/ created with 2 processed CSVs
python pipeline.py

# 3. Inspect output
ls output/
python -c "import pandas as pd; print(pd.read_csv('output/sales_jan.csv').head())"

# 4. Run tests
pytest test_pipeline.py -v
```

Expected test result: all 11 tests pass.


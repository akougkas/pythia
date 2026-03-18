---
case: case_003_data_pipeline
framework: claude_code
model: claude-opus-4-6
provider: anthropic
session_id: 7f60e2b8-0e1b-4105-962b-f6865def604a
duration_ms: 164600
duration_wall_s: 173.3
cost_usd: 0.45217229999999997
num_turns: 9
timestamp: 2026-03-18T00:51:11.251114+00:00
error: None
---

# Plan

# Case 003: CSV Data Pipeline — Implementation Plan

## Context

Build a configurable CSV data pipeline from scratch. The `WorkingDir/` is empty — all files are greenfield. The pipeline reads CSVs from an input directory, applies a YAML-defined chain of transforms using pandas, and writes results to an output directory, with dry-run and logging support.

## File Structure

```
WorkingDir/
  pipeline.py          # Main orchestrator + CLI
  transforms.py        # Transform registry and functions
  pipeline.yaml        # Example pipeline config
  test_pipeline.py     # pytest test suite
  input/
    sales.csv          # Sample data (10 rows)
  output/              # Created at runtime
```

## Implementation Order

### Step 1: `input/sales.csv` — Sample Data

10-row CSV with columns: `date, product, region, quantity, unit_price`. Provides test data for manual runs and the example config.

### Step 2: `transforms.py` — Transform Registry + Functions

- **Registry**: Module-level `_REGISTRY` dict populated by `@register("name")` decorator
- **API**: `get_transform(name)` → callable, `list_transforms()` → list of names
- **Uniform signature**: `(df: pd.DataFrame, params: dict) -> pd.DataFrame`
- **Five transforms**:
  | Transform | Key Params | Notes |
  |---|---|---|
  | `filter_rows` | `column`, `operator`, `value` | Operators: `==, !=, >, <, >=, <=, in, not_in`. Uses `operator` module for comparison ops. |
  | `rename_columns` | `mapping` (dict) | Validates all keys exist before renaming. |
  | `compute_column` | `new_column`, `expression` | Uses `df.eval()` (safer than raw `eval`). |
  | `drop_columns` | `columns` (list) | Validates all columns exist. |
  | `sort_rows` | `by` (list), `ascending` (bool, default True) | Resets index after sort. |
- **Error handling**: `KeyError` for missing columns, `ValueError` for bad operators/expressions.
- All filtering/sorting calls `reset_index(drop=True)`.

### Step 3: `pipeline.yaml` — Example Config

```yaml
pipeline:
  input_dir: "input"
  output_dir: "output"
  steps:
    - type: filter_rows
      params: { column: "quantity", operator: ">", value: 2 }
    - type: rename_columns
      params: { mapping: { unit_price: "price_usd" } }
    - type: compute_column
      params: { new_column: "total", expression: "quantity * price_usd" }
    - type: drop_columns
      params: { columns: ["region"] }
    - type: sort_rows
      params: { by: ["total"], ascending: false }
```

### Step 4: `pipeline.py` — Orchestrator + CLI

**Functions:**

| Function | Purpose |
|---|---|
| `load_config(path)` | Parse YAML, validate required keys (`input_dir`, `output_dir`, `steps`), return `pipeline` dict |
| `discover_csvs(input_dir)` | Return sorted list of `.csv` paths; raise `FileNotFoundError` if dir missing |
| `apply_steps(df, steps, source_name, dry_run)` | Chain transforms, log row counts before/after each step. Dry-run still executes transforms (for accurate counts) but skips file I/O. |
| `run_pipeline(config, dry_run)` | For each CSV: read → apply_steps → write (or log in dry-run). Creates output dir if needed. |
| `build_cli()` | argparse: `--config` (default `pipeline.yaml`), `--dry-run`, `-v`/`--verbose` (repeatable) |
| `main()` | Parse args, configure logging, call `run_pipeline` |

**Logging:**
- Default (`WARNING`): only errors/warnings
- `-v` (`INFO`): file names, step names, row counts
- `-vv` (`DEBUG`): params, column lists
- Format: `%(asctime)s [%(levelname)s] %(message)s`

**Dry-run behavior:** Transforms execute in-memory (accurate row counts reported), but no output dir created and no files written. Uses `logger.warning("DRY-RUN: would write ...")`.

### Step 5: `test_pipeline.py` — Tests (~20 cases)

**Fixtures:** `sample_df` (5-col DataFrame), `sample_config` (uses `tmp_path` for isolated I/O).

| Test Class | Coverage |
|---|---|
| `TestFilterRows` | All 8 operators, missing column error, bad operator error |
| `TestRenameColumns` | Basic rename, missing column error |
| `TestComputeColumn` | Valid expression, bad expression error |
| `TestDropColumns` | Single/multiple drop, missing column error |
| `TestSortRows` | Ascending, descending, multi-column |
| `TestConfigLoading` | Valid config, missing file, missing keys |
| `TestPipelineEndToEnd` | Full run (verify output), dry-run (no files written), missing input dir, unknown transform |

## Verification

```bash
cd WorkingDir

# Run tests
pytest test_pipeline.py -v

# Manual run
python pipeline.py --config pipeline.yaml -vv

# Dry-run
python pipeline.py --config pipeline.yaml --dry-run -v

# Check output
cat output/sales.csv
```


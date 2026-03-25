---
case: case_003_data_pipeline
framework: claude_code
model: claude-opus-4-6
provider: anthropic
session_id: cc29a119-6b4c-49ee-b145-2d94b8b9564f
duration_ms: 56329
duration_wall_s: 58.8
cost_usd: 0.1405615
num_turns: 8
timestamp: 2026-03-19T14:12:24.350717+00:00
error: None
---

# Plan

# Plan: CSV Data Pipeline

## Context

Build a configurable CSV data pipeline that reads CSVs from an input directory, applies YAML-defined transformations (filter, rename, compute), and writes results to an output directory. The working directory is empty — all files (including sample CSVs) will be created from scratch.

## Assumptions

- Python 3.8+, pandas, PyYAML as dependencies
- All deliverables placed in `WorkingDir/`
- Sample CSVs created in `WorkingDir/input/` for testing
- Output written to `WorkingDir/output/`
- Tests use pytest

## Files to Create

All under `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/`:

### 1. `pipeline.yaml` — Example pipeline config

```yaml
input_dir: input
output_dir: output
log_level: INFO  # DEBUG, INFO, WARNING, ERROR

transforms:
  - type: filter_rows
    column: age
    operator: ">="
    value: 18

  - type: rename_columns
    mapping:
      name: full_name
      age: years

  - type: compute_column
    new_column: age_group
    expression: "pd.cut(df['years'], bins=[0,30,60,100], labels=['young','middle','senior'])"
```

### 2. `transforms.py` — Transform functions

Each transform is a function `(df, **params) -> df`. A registry dict maps type names to functions.

- `filter_rows(df, column, operator, value)` — filter using operator (`==`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `not_in`)
- `rename_columns(df, mapping)` — `df.rename(columns=mapping)`
- `compute_column(df, new_column, expression)` — eval expression with `df` and `pd` in scope
- `drop_columns(df, columns)` — drop listed columns
- `sort_rows(df, by, ascending=True)` — sort by column(s)
- `fill_missing(df, column, value)` — fillna

Registry pattern:
```python
TRANSFORMS = {
    "filter_rows": filter_rows,
    "rename_columns": rename_columns,
    "compute_column": compute_column,
    "drop_columns": drop_columns,
    "sort_rows": sort_rows,
    "fill_missing": fill_missing,
}
```

Each function includes a `describe()`-style summary for dry-run mode, implemented via a helper that returns a human-readable string describing what the transform would do.

### 3. `pipeline.py` — Main orchestrator

Key components:

- **`load_config(path)`** — read and parse `pipeline.yaml`
- **`setup_logging(level)`** — configure Python logging with the verbosity from config
- **`run_pipeline(config_path, dry_run=False)`** — main entry point:
  1. Load config
  2. Setup logging
  3. Glob `input_dir/*.csv`
  4. For each CSV:
     a. `pd.read_csv(file)`
     b. For each transform in config `transforms` list:
        - Look up function in `TRANSFORMS` registry
        - If dry_run: log what would happen (transform type + params), skip execution
        - Else: apply transform, log row count before/after
     c. If not dry_run: write result to `output_dir/` with same filename
  5. Log summary (files processed, total rows in/out)
- **CLI via `argparse`**:
  - `--config` (default: `pipeline.yaml`)
  - `--dry-run` flag
  - `--log-level` override (overrides config value)

### 4. `test_pipeline.py` — Unit tests (pytest)

Tests organized into sections:

**Transform tests:**
- `test_filter_rows_gte` — filter age >= 18, verify correct rows remain
- `test_filter_rows_eq` — filter with `==`
- `test_filter_rows_in` — filter with `in` operator
- `test_rename_columns` — rename and verify column names
- `test_compute_column` — add derived column, verify values
- `test_drop_columns` — verify columns removed
- `test_sort_rows` — verify sort order
- `test_fill_missing` — verify NaN replaced

**Pipeline integration tests (using tmp_path):**
- `test_full_pipeline` — write sample CSV + config to tmp dir, run pipeline, verify output CSV
- `test_dry_run` — run with dry_run=True, verify no output files created
- `test_chaining` — apply multiple transforms in sequence, verify final result
- `test_missing_input_dir` — verify graceful error handling
- `test_unknown_transform` — verify error on bad transform type

### 5. Sample data files in `input/`

Create `input/employees.csv`:
```
name,age,department,salary
Alice,32,Engineering,95000
Bob,17,Intern,30000
Carol,45,Marketing,78000
Dave,28,Engineering,88000
Eve,16,Intern,28000
```

## Implementation Order

1. Create `input/` directory and sample CSV
2. Create `pipeline.yaml`
3. Create `transforms.py` (standalone, testable)
4. Create `pipeline.py` (imports from transforms)
5. Create `test_pipeline.py`
6. Run tests to verify

## Verification

```bash
cd WorkingDir
# Run unit tests
python -m pytest test_pipeline.py -v

# Run pipeline for real
python pipeline.py --config pipeline.yaml

# Verify output
ls output/
cat output/employees.csv

# Test dry-run
python pipeline.py --config pipeline.yaml --dry-run

# Test verbose logging
python pipeline.py --config pipeline.yaml --log-level DEBUG
```


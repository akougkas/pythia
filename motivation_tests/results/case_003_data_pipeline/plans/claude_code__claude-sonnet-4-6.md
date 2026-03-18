---
case: case_003_data_pipeline
framework: claude_code
model: claude-sonnet-4-6
provider: anthropic
session_id: 7edb8d6d-b7c0-491f-b1ec-53ee2b15dc43
duration_ms: 65009
duration_wall_s: 69.3
cost_usd: 0.2022083
num_turns: 6
timestamp: 2026-03-18T00:50:05.007682+00:00
error: None
---

# Plan

# Plan: Case 003 — CSV Data Pipeline

## Context

The goal is to build a configurable CSV data pipeline using `pandas`. A `pipeline.yaml`
file defines the input/output directories and an ordered list of transform steps. The
orchestrator (`pipeline.py`) discovers all CSVs in the input directory, applies each
transform in sequence, and writes results to the output directory. A dry-run flag
previews what would happen without writing files. The working directory is empty, so all
files must be created from scratch.

---

## Files to Create

All files go in:
`/home/jye/publications/pythia/motivation_tests/cases/case_003_data_pipeline/WorkingDir/`

| File | Role |
|---|---|
| `pipeline.yaml` | Example pipeline config |
| `transforms.py` | Transform function registry |
| `pipeline.py` | Main orchestrator / CLI |
| `test_pipeline.py` | Unit tests |
| `input/employees.csv` | Sample CSV for demo |
| `input/contractors.csv` | Second sample CSV |

---

## 1. `pipeline.yaml` — Example Config

```yaml
pipeline:
  input_dir: input/
  output_dir: output/
  log_level: INFO        # DEBUG | INFO | WARNING

  steps:
    - transform: filter_rows
      column: age
      operator: ">="
      value: 18

    - transform: rename_columns
      mapping:
        fname: first_name
        lname: last_name

    - transform: compute_derived
      column: full_name
      expression: "first_name + ' ' + last_name"
```

---

## 2. `transforms.py` — Transform Functions

### Design

- Each transform is a pure function: `fn(df: pd.DataFrame, **params) -> pd.DataFrame`
- A `TRANSFORM_REGISTRY` dict maps YAML `transform:` names → functions
- Each function validates its own params and raises `ValueError` on bad input

### Functions

#### `filter_rows(df, column, operator, value)`
- Supported operators: `>`, `>=`, `<`, `<=`, `==`, `!=`, `contains`
- For numeric comparisons, coerce `value` to the column dtype
- For `contains`, does case-insensitive substring match on string columns
- Returns filtered DataFrame (copy)

#### `rename_columns(df, mapping)`
- `mapping`: dict of `{old_name: new_name}`
- Raises `ValueError` if any old name not in `df.columns`
- Uses `df.rename(columns=mapping)`

#### `compute_derived(df, column, expression)`
- Evaluates `expression` via `df.eval(expression)` and assigns to `column`
- Supports pandas `eval` syntax (arithmetic, string concat with `+`)
- Raises `ValueError` if expression fails

#### `TRANSFORM_REGISTRY`
```python
TRANSFORM_REGISTRY = {
    "filter_rows": filter_rows,
    "rename_columns": rename_columns,
    "compute_derived": compute_derived,
}
```

---

## 3. `pipeline.py` — Orchestrator

### Design

- CLI via `argparse`
- Reads `pipeline.yaml` (path configurable via `--config`)
- Discovers all `*.csv` in `input_dir`
- For each CSV: load → apply transforms in order → write to `output_dir`
- `--dry-run` flag: logs what would be written, skips actual file write
- `--log-level` flag overrides `pipeline.yaml` log_level

### Key Functions

```python
def load_config(path: str) -> dict
    # Reads YAML, validates required keys: pipeline.input_dir, pipeline.output_dir, pipeline.steps

def apply_transforms(df: pd.DataFrame, steps: list[dict], logger) -> pd.DataFrame
    # Iterates steps; looks up fn in TRANSFORM_REGISTRY; calls fn(df, **step_params)
    # Logs step name, input shape, output shape at DEBUG level

def process_file(csv_path: Path, output_dir: Path, steps: list, dry_run: bool, logger)
    # Loads CSV → apply_transforms → write (or skip if dry_run)
    # Logs INFO: "Processing <file>" and "Would write / Wrote <output>"

def run_pipeline(config: dict, dry_run: bool, logger)
    # Resolves input/output dirs; creates output_dir if needed (unless dry_run)
    # Calls process_file for each CSV found

def main()
    # argparse: --config (default pipeline.yaml), --dry-run, --log-level
    # Sets up logging with %(levelname)s %(message)s format
    # Calls run_pipeline
```

### CLI Usage
```
python pipeline.py                         # run with pipeline.yaml
python pipeline.py --config my.yaml        # custom config
python pipeline.py --dry-run               # preview only
python pipeline.py --log-level DEBUG       # verbose
```

---

## 4. `test_pipeline.py` — Unit Tests

Uses `pytest` + `pandas` + `tempfile`.

### Test Groups

#### `test_transforms.py` section (in same file)
- `test_filter_rows_gte` — filter numeric column, correct rows kept
- `test_filter_rows_contains` — string substring filter
- `test_filter_rows_bad_operator` — raises `ValueError`
- `test_rename_columns` — columns renamed correctly
- `test_rename_columns_missing` — raises `ValueError`
- `test_compute_derived_arithmetic` — new numeric column computed
- `test_compute_derived_string_concat` — new string column from expression

#### `test_pipeline.py` section
- `test_load_config_valid` — parses YAML, returns dict with expected keys
- `test_load_config_missing_key` — raises on bad YAML structure
- `test_apply_transforms_chain` — chains rename → filter → compute in sequence
- `test_process_file_writes_output` — uses tmp_path, verifies output CSV created
- `test_process_file_dry_run` — verifies no file written in dry-run mode
- `test_run_pipeline_multiple_csvs` — two CSVs in input dir → two in output dir

---

## 5. Sample Input CSVs

### `input/employees.csv`
```
id,fname,lname,age,department,salary
1,Alice,Smith,32,Engineering,95000
2,Bob,Jones,17,Intern,12000
3,Carol,White,28,Marketing,72000
4,Dan,Brown,45,Engineering,110000
5,Eve,Davis,16,Intern,11000
```

### `input/contractors.csv`
```
id,fname,lname,age,department,salary
101,Frank,Miller,38,Design,85000
102,Grace,Wilson,22,Engineering,90000
103,Hank,Moore,15,Intern,10000
```

---

## Execution Flow (End-to-End)

With the example `pipeline.yaml`:
1. Load both CSVs from `input/`
2. **filter_rows** — keep rows where `age >= 18` (removes minors)
3. **rename_columns** — `fname→first_name`, `lname→last_name`
4. **compute_derived** — new column `full_name = first_name + ' ' + last_name`
5. Write results to `output/employees.csv` and `output/contractors.csv`

---

## Verification

```bash
cd WorkingDir/

# Run tests
pytest test_pipeline.py -v

# Dry run (no files written)
python pipeline.py --dry-run --log-level DEBUG

# Full run
python pipeline.py

# Inspect output
python -c "import pandas as pd; print(pd.read_csv('output/employees.csv'))"
```

Expected output CSV for `employees.csv`:
```
id,first_name,last_name,age,department,salary,full_name
1,Alice,Smith,32,Engineering,95000,Alice Smith
3,Carol,White,28,Marketing,72000,Carol White
4,Dan,Brown,45,Engineering,110000,Dan Brown
```


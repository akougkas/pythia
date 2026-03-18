---
case: case_003_data_pipeline
framework: claude_code
model: qwen/qwen3.5-9b
provider: lm_studio
session_id: 2757ea0d-9484-4be7-a205-ce98ac2e5dc6
duration_ms: 930281
duration_wall_s: 988.4
cost_usd: 5.919243400000003
num_turns: 16
timestamp: 2026-03-18T15:28:19.472070+00:00
error: None
---

# Plan

# CSV Data Pipeline Implementation Plan

## Context

Creating a modular, configurable CSV data pipeline from scratch for `/home/jye/publications/pythia/motivation_tests/cases/case_003_data_pipeline/WorkingDir`. The pipeline will use pandas for data manipulation and support declarative configuration via YAML. No existing code patterns found in the project - this is a greenfield implementation using standard Python/pandas conventions.

## Design Approach

### Architecture Overview
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Input CSV(s)   │ →  │  Pipeline Steps  │ →  │ Output CSV(s)   │
│ (input_dir/)    │    │  (pipeline.yaml) │    │ (output_dir/)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                         ├────┴────┤
                         │         │
              ┌─────────▼───┐ ┌────▼────┐
              │  Logger     │ │Config   │
              │ (verbose)   │ │ Loader  │
              └─────────────┘ └─────────┘
```

---

## Files to Create

### 1. `pipeline.py` - Main Orchestrator (~120 lines)

**Purpose**: Coordinates the entire pipeline execution flow, config loading, and mode switching.

**Key Functions**:
- `load_config(path)` - Load and validate `pipeline.yaml` configuration
- `create_reader(config, input_path, logger)` - Return file reader with error handling
- `create_transformer(steps, reader, logger)` - Chain transform functions dynamically
- `run_pipeline(config, dry_run=False, output_dir=None)` - Main entry point
- `_execute_step(step_name, step_config, data)` - Execute individual pipeline steps

**Core Workflow**:
1. Load config from YAML file with validation (required: input_dir, transforms)
2. Initialize logger at configured verbosity level
3. Find all CSV files in input directory (recursive if `recursive=True`)
4. Read first CSV to get initial schema
5. Build transform chain from configuration
6. Execute each transform step
7. In dry-run mode: print summary, predicted output
8. Otherwise: write result CSV(s) with configurable options

**Dry-Run Mode Behavior**:
- Simulates entire pipeline without writing files
- Prints progress at each step (rows filtered, columns added)
- Outputs final schema prediction including all derived columns
- Returns `dry_run_result` dict with summary stats

**Logging Interface**:
```python
logger.info("Pipeline started", input_path=input_dir)
logger.debug("Processing row: {row}", row=sample_row)
logger.warning("Step produced no output rows")
logger.error("Failed to read CSV: {error}", error=e)
```

### 2. `transforms.py` - Transform Functions (~80 lines)

**Purpose**: Provide modular, reusable transform functions that can be chained.

**Transform Types**:
1. **FilterRows** - Row filtering with SQL-like expressions or boolean column
2. **RenameColumns** - Column renaming with validation (warn on duplicates)
3. **DeriveColumn** - Create new columns from existing ones (supports lambdas, simple formulas)
4. **DropColumns** - Remove specified columns

**Function Signatures**:
```python
def filter_rows(data: pd.DataFrame, condition: str | bool): ...
def rename_columns(data: pd.DataFrame, mapping: dict[str, str]): ...
def derive_column(data: pd.DataFrame, name: str, expression: callable | str): ...
def drop_columns(data: pd.DataFrame, columns: list[str]): ...
```

**Implementation Details**:
- Each transform validates input DataFrame type (raises TypeError)
- `filter_rows`: Accepts SQL string ("age > 30") or boolean column name; logs row counts before/after
- `rename_columns`: Supports dict-based mapping; warns on duplicate target names via logger
- `derive_column`: Supports lambda expressions (`lambda x: x['a'] + x['b']`) and formula strings
- All transforms are pure functions (stateless, return new DataFrame)

**Step Configuration Format**:
```yaml
transforms:
  - name: filter_rows_gt_30
    action: filter_rows
    condition: "age > 30"

  - name: rename_status_column
    action: rename_columns
    mapping:
      "old_status": "status_value"

  - name: compute_age_group
    action: derive_column
    target: age_group
    expression: lambda x: pd.cut(x['age'], bins=[0, 30, 50, 100], labels=['Young', 'Middle', 'Senior'])
```

### 3. `pipeline.yaml` - Example Configuration (~40 lines)

**Purpose**: Demonstrate YAML schema and provide working example.

**Required Fields**:
- `input_dir`: Path to input CSV files (can be relative or absolute)
- `output_dir`: Path for output CSV(s) (optional, None for single output)
- `recursive`: Recursively find CSV files in subdirectories (default: false)
- `dry_run`: Enable dry-run mode (default: false)
- `log_level`: Verbosity level: INFO, DEBUG, WARNING (default: INFO)

**Optional Fields**:
- `format_options`: CSV write options (sep, index, encoding)
- `encoding`: File encoding for reading/writing (default: "utf-8")
- `filters`: Pre-transform filters applied to file list
- `transforms`: Ordered list of transform steps

**Example Configuration**:
```yaml
# pipeline.yaml - Example data pipeline configuration

input_dir: "/data/raw/customer_orders"
output_dir: "/data/processed/orders_cleaned"
recursive: false
dry_run: true  # Set to true for preview mode

log_level: INFO

format_options:
  sep: ","
  index: false
  encoding: utf-8

transforms:
  # Step 1: Filter incomplete orders
  - name: filter_completed_orders
    action: filter_rows
    condition: "order_status == 'completed'"

  # Step 2: Rename inconsistent column names
  - name: standardize_column_names
    action: rename_columns
    mapping:
      "cust_id": "customer_id"
      "amt": "amount_paid"

  # Step 3: Derive total amount with tax
  - name: add_tax_column
    action: derive_column
    target: tax_amount
    expression: lambda x: x['amount_paid'] * 0.15

  # Step 4: Drop temporary columns
  - name: remove_temp_cols
    action: drop_columns
    columns: ["temp_flag", "internal_id"]

  # Step 5: Derive order year-month for grouping
  - name: add_period_column
    action: derive_column
    target: order_period
    expression: lambda x: x['order_date'].dt.to_period('M')
```

### 4. `test_pipeline.py` - Unit Tests (~80 lines)

**Purpose**: Comprehensive unit tests using pytest conventions.

**Test Modules**:
1. `test_config_loading` - Test YAML config parsing and validation
2. `test_filter_rows` - Filter with SQL expressions, boolean columns, edge cases
3. `test_rename_columns` - Column mapping, duplicate handling, missing keys
4. `test_derive_column` - Lambda expressions, string formulas, type coercion
5. `test_drop_columns` - Multiple columns, non-existent columns
6. `test_full_pipeline_dry_run` - End-to-end dry-run simulation
7. `test_pipeline_with_data` - Integration test with sample data

**Test Structure**:
```python
import pandas as pd
import tempfile
import yaml
from pathlib import Path

# Test setup helpers
@pytest.fixture
def sample_csv_file(tmp_path):
    """Create a CSV file with known schema for testing"""
    csv_content = """name,age,salary,dept,city
Alice,30,75000,Engineering,New York
Bob,25,65000,Sales,Boston
Charlie,45,90000,Engineering,Chicago
David,35,80000,Marketing,Seattle"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(csv_content)
    return csv_file

# Example test
def test_filter_rows_sql_expression(sample_csv_file):
    data = pd.read_csv(sample_csv_file)

    result = filter_rows(data, "age > 30")

    assert len(result) == 2  # Alice and Charlie
    assert "Alice" in result["name"]
    assert "Bob" not in result["name"]

# Dry-run test
def test_full_pipeline_dry_run():
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = {
            "input_dir": os.path.join(tmp_dir, "input"),
            "output_dir": None,  # dry run mode
            "dry_run": True,
            "log_level": "DEBUG",
            "transforms": [...]
        }
        result = run_pipeline(config)

    assert result["mode"] == "dry_run"
    assert len(result["steps_executed"]) > 0
```

---

## Implementation Details

### Error Handling Strategy
- **File errors**: `FileNotFoundError` when input dir doesn't exist (exit with clear message)
- **CSV parse errors**: Catch `ParserError`, log, continue to next file
- **Transform errors**: Each step has try/except, logs error and continues pipeline
- **Config validation**: Validate required fields upfront, exit early with usage hints

### Type Hints
All functions use full type hints with `typing` module:
```python
from typing import Callable, Dict, List, Optional

def filter_rows(
    data: pd.DataFrame,
    condition: str | bool
) -> pd.DataFrame: ...
```

### Logger Setup
Standard logging configuration in pipeline.py:
```python
import logging
import sys

def setup_logger(log_level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("csv_pipeline")
    logger.setLevel(getattr(logging, log_level.upper()))

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)
    return logger
```

### Output CSV Writing Options
Default write options (configurable via `format_options`):
- `sep=','`: Comma-separated
- `index=False`: Don't write DataFrame index as column
- `encoding='utf-8'`: Standard UTF-8 encoding
- `date_format=None`: No automatic date formatting

---

## Verification & Testing Strategy

### Quick Validation Checklist
- [ ] `python pipeline.py -h` (if CLI args added) or basic import test
- [ ] `python -c "from transforms import filter_rows; print('OK')"`
- [ ] `python test_pipeline.py -v` (verbose pytest output)
- [ ] Dry-run with provided config shows no write operations

### Sample Test Command Sequence
```bash
# Run tests in verbose mode
pytest test_pipeline.py -v --tb=short

# Run dry-run pipeline
python pipeline.py pipeline.yaml

# Run actual pipeline (with sample data if available)
python pipeline.py pipeline.yaml
```

### Expected Outputs on Success

**Dry-run output**:
```
2026-03-18 10:30:45 - csv_pipeline - INFO - Pipeline started, input_dir=/data/raw/orders
2026-03-18 10:30:46 - csv_pipeline - DEBUG - Reading file: orders_001.csv
2026-03-18 10:30:46 - csv_pipeline - INFO - Step 'filter_completed_orders' executed, rows before=150, rows after=120
2026-03-18 10:30:47 - csv_pipeline - DEBUG - Applying rename: old_status -> status_value
...
```

**Dry-run summary**:
```
=== DRY RUN COMPLETE ===
Files processed: 2
Steps executed: 5
Predicted output schema:
   customer_id,order_date,amount_taxed,... <- all columns listed
Predicted row count: ~90 (after transforms)
Mode: dry_run (no files written)
```

---

## Next Steps

1. **Implement `transforms.py`** first (dependency for pipeline.py)
2. **Implement `pipeline.py`** with config loading and orchestrator logic
3. **Create `pipeline.yaml`** example configuration in WorkingDir
4. **Write `test_pipeline.py`** comprehensive test suite
5. **Run tests** to validate all components work together

All implementations will follow PEP 8 style guidelines and include docstrings for each function.


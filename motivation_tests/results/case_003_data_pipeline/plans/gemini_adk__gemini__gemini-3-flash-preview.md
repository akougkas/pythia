---
case: case_003_data_pipeline
framework: gemini_adk
model: gemini-3-flash-preview
provider: gemini
session_id: None
duration_ms: 6066
duration_wall_s: 6.1
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T02:04:45.327865+00:00
error: None
---

# Plan

# Implementation Plan: CSV Data Pipeline

This plan outlines the development of a modular, configuration-driven data pipeline using `pandas`. The system will read CSV files, apply transformations defined in a YAML file, and output the results.

## 1. Assumptions & Design Decisions
- **Input/Output**: The pipeline will process all `.csv` files in the specified input directory or a single specified file.
- **Transform Logic**: Transformations will be applied sequentially in the order defined in `pipeline.yaml`.
- **Error Handling**: If a transformation fails for a specific file, the error will be logged, and the pipeline will proceed to the next file (unless a critical configuration error occurs).
- **Dry-run**: In dry-run mode, the script will log the transformations that *would* have been applied and display a preview (head) of the resulting dataframe instead of saving to disk.
- **Logging**: Standard Python `logging` module will be used, with levels (INFO, DEBUG) controlled via command-line arguments.

## 2. File Structure
- `pipeline.py`: Entry point, CLI argument parsing, and orchestration logic.
- `transforms.py`: Library of transformation functions (filter, rename, compute).
- `pipeline.yaml`: Configuration file defining the source, destination, and steps.
- `test_pipeline.py`: Unit tests for individual transforms and the orchestrator.

## 3. Step-by-Step Implementation

### Step 1: Define `transforms.py`
Create a library of functions that take a `pandas.DataFrame` and configuration parameters as input and return a modified `DataFrame`.
- `filter_rows(df, condition)`: Uses `df.query()` to filter data.
- `rename_columns(df, mapping)`: Uses `df.rename(columns=...)`.
- `compute_column(df, column_name, expression)`: Uses `df.eval()` or lambda functions to create new columns based on existing ones.

### Step 2: Create `pipeline.yaml`
Define a sample configuration to guide development.
```yaml
pipeline:
  input_dir: "./input"
  output_dir: "./output"
  log_level: "INFO"
  steps:
    - transform: "rename_columns"
      params:
        mapping: {"old_name": "new_name"}
    - transform: "filter_rows"
      params:
        condition: "new_name > 10"
    - transform: "compute_column"
      params:
        column_name: "total"
        expression: "new_name * 1.2"
```

### Step 3: Develop `pipeline.py` (Orchestrator)
- **Config Loader**: Load `pipeline.yaml` using `PyYAML`.
- **CLI Setup**: Use `argparse` to support `--config`, `--dry-run`, and `--verbose`.
- **Registry Pattern**: Map string names from the YAML (e.g., "filter_rows") to the actual functions in `transforms.py`.
- **Execution Loop**:
    1. Identify target CSV files.
    2. For each file:
        - Load into Pandas.
        - Iterate through `steps` in the config.
        - Dynamically call the corresponding function from `transforms.py`.
        - If `dry-run`, print `df.head()` and skip save.
        - If not `dry-run`, save to `output_dir`.

### Step 4: Logging and Verbosity
- Initialize `logging` based on the YAML `log_level` or CLI override.
- Log the start of each file process, each transformation step, and the final save location.

### Step 5: Unit Testing (`test_pipeline.py`)
- Use `pytest`.
- Test each transform function in `transforms.py` with mock DataFrames.
- Test the orchestrator's ability to parse the YAML and chain two transforms together.
- Test that `dry-run` mode does not create files.

## 4. Execution Command Example
```bash
# Standard run
python pipeline.py --config pipeline.yaml

# Dry run with debug logging
python pipeline.py --config pipeline.yaml --dry-run --verbose
```

## 5. Verification Plan
1. **Functional Check**: Run the pipeline on the sample CSVs in `WorkingDir/`. Verify the output CSVs have the correct columns and filtered rows.
2. **Constraint Check**: Ensure `pandas` is the primary engine and `pipeline.yaml` drives the logic.
3. **Robustness**: Pass a malformed expression to `compute_column` and ensure the pipeline logs the error gracefully without crashing the entire batch.

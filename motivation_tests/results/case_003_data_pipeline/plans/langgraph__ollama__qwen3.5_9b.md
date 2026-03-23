---
case: case_003_data_pipeline
framework: langgraph
model: qwen3.5:9b
provider: ollama
session_id: None
duration_ms: 30328
duration_wall_s: 30.3
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T22:53:06.228273+00:00
error: None
---

# Plan

# Implementation Plan: CSV Data Pipeline (Case 003)

## 1. Project Overview & Assumptions
This plan outlines the design and implementation of a modular, configurable CSV data pipeline using Python and `pandas`. The pipeline will read from an input directory, apply a sequence of transformations defined in a YAML configuration, and write results to an output directory.

### Explicit Assumptions
1.  **Working Directory Structure:** Since I cannot physically inspect the local filesystem, I assume the `WorkingDir` (`/home/jye/publications/cases/case_003_data_pipeline/WorkingDir`) contains:
    *   `input/`: Directory containing source CSV files.
    *   `output/`: Directory for processed results.
    *   `pipeline.yaml`: The configuration file.
    *   `sample_data.csv`: A reference CSV file for testing.
2.  **Transform Logic:** Transformations will be stateless functions that accept a `pandas.DataFrame` and return a modified `DataFrame`.
3.  **Error Handling:** If an input file is missing, the pipeline will raise a specific `FileNotFoundError` with a descriptive message. If a transform fails, the pipeline will log the error and stop, preserving the last valid state if possible (or failing fast based on config).
4.  **Logging:** Python's standard `logging` module will be used. Verbosity will be controlled via a `LOG_LEVEL` environment variable or CLI argument.
5.  **Dry-Run:** In dry-run mode, the pipeline will execute all logic up to the point of writing files but will not call `df.to_csv()`.

---

## 2. Project Architecture

### Directory Structure
We will create the following structure within the project root:
```text
case_003_data_pipeline/
├── src/
│   ├── __init__.py
│   ├── pipeline.py          # Main orchestrator
│   └── transforms.py        # Transform definitions
├── config/
│   └── pipeline.yaml        # Pipeline configuration
├── tests/
│   ├── __init__.py
│   ├── test_pipeline.py     # Unit and integration tests
│   └── conftest.py          # Shared fixtures (optional)
├── data/
│   ├── input/
│   └── output/
├── logs/
├── requirements.txt
└── README.md
```

### Dependencies (`requirements.txt`)
*   `pandas>=2.0.0`
*   `pyyaml>=6.0`
*   `pytest>=7.0`
*   `python-dotenv` (optional, for env vars)

---

## 3. File-by-File Implementation Plan

### 3.1. `src/transforms.py` (Transform Logic)
**Goal:** Encapsulate data manipulation logic.

**Step 1: Define Base Class**
*   Create an abstract base class `BaseTransform`.
*   Method `apply(df) -> DataFrame`: Returns the transformed dataframe.
*   Method `name`: Returns a string identifier for the step.

**Step 2: Implement Specific Transforms**
*   **`FilterRows`**:
    *   *Input:* DataFrame, `condition` (dict or lambda).
    *   *Logic:* `df.query(condition)` or `df[df[condition]]`.
    *   *Config:* `type: filter`, `condition: "age > 18"`.
*   **`RenameColumns`**:
    *   *Input:* DataFrame, `mapping` (dict).
    *   *Logic:* `df.rename(columns=mapping)`.
    *   *Config:* `type: rename`, `mapping: {old: new}`.
*   **`ComputeDerived`**:
    *   *Input:* DataFrame, `expressions` (dict of column_name: expression).
    *   *Logic:* `df['new_col'] = df['col1'] * df['col2']`.
    *   *Config:* `type: compute`, `expressions: {total: "price * quantity"}`.
*   **`SortData`**:
    *   *Input:* DataFrame, `by`, `ascending`.
    *   *Logic:* `df.sort_values(by=by, ascending=ascending)`.

**Step 3: Factory Function**
*   Create a function `create_transform(transform_type, **kwargs)` that instantiates the correct class/function based on the YAML config string.

### 3.2. `src/pipeline.py` (Orchestrator)
**Goal:** Load config, chain transforms, handle I/O, manage logging.

**Step 1: Configuration Loading**
*   Import `yaml`.
*   Function `load_config(path)`: Reads `pipeline.yaml`.
*   Validate that `input_dir`, `output_dir`, and `steps` exist in the config.

**Step 2: Logging Setup**
*   Function `setup_logging(level)`: Configures `logging.basicConfig`.
*   Ensure `level` defaults to `INFO` but can be overridden by CLI args.

**Step 3: Pipeline Execution Engine**
*   Function `run_pipeline(config_path, dry_run=False)`:
    1.  Load config.
    2.  Set up logging.
    3.  Iterate through `config['steps']`.
    4.  For each step:
        *   Instantiate transform via factory.
        *   Load input CSV (handle multiple files or single file logic).
        *   Apply transform.
        *   Log progress (`INFO` or `DEBUG` depending on verbosity).
    5.  **Dry-Run Check:** If `dry_run=True`, log "Would write to..." and skip `to_csv`.
    6.  **Write Output:** If not dry-run, write final DataFrame to `output_dir`.
    7.  Handle exceptions: Catch `ValueError`, `KeyError`, `FileNotFoundError`. Log errors as `ERROR`.

**Step 4: CLI Interface**
*   Use `argparse` to allow running via command line:
    *   `--config`: Path to yaml.
    *   `--dry-run`: Boolean flag.
    *   `--verbose`: Set log level.

### 3.3. `config/pipeline.yaml` (Configuration Schema)
**Goal:** Define the pipeline steps declaratively.

**Structure:**
```yaml
input_dir: "data/input"
output_dir: "data/output"
log_level: "INFO"
dry_run: false

steps:
  - name: "filter_adults"
    type: "filter"
    condition: "age >= 18"
  - name: "standardize_names"
    type: "rename"
    mapping:
      "first_name": "fname"
      "last_name": "lname"
  - name: "calculate_total"
    type: "compute"
    expressions:
      "total": "price * quantity"
```

### 3.4. `tests/test_pipeline.py` (Testing Strategy)
**Goal:** Ensure robustness and correctness.

**Step 1: Fixtures**
*   Create a fixture `sample_csv_data` that generates a small, deterministic DataFrame (e.g., 5 rows) to avoid dependency on external files during unit tests.

**Step 2: Unit Tests for Transforms**
*   Test `FilterRows`: Verify rows are removed correctly.
*   Test `RenameColumns`: Verify column names match mapping.
*   Test `ComputeDerived`: Verify arithmetic is correct.
*   Test `SortData`: Verify order is correct.

**Step 3: Integration Tests**
*   Test `run_pipeline` with a valid config.
*   Test `run_pipeline` with `dry_run=True` (assert no files created).
*   Test `run_pipeline` with invalid config (assert error raised).
*   Test `run_pipeline` with missing input file (assert error raised).

**Step 4: Logging Tests**
*   Verify that logs are written to the correct level (e.g., assert `DEBUG` logs appear when verbose is set).

---

## 4. Implementation Sequence

1.  **Setup Environment:**
    *   Create the directory structure.
    *   Initialize `requirements.txt`.
    *   Create `src/__init__.py`.

2.  **Develop Transforms (`src/transforms.py`):**
    *   Implement `BaseTransform`.
    *   Implement specific classes/functions.
    *   Implement the factory function.

3.  **Develop Orchestrator (`src/pipeline.py`):**
    *   Implement config loader.
    *   Implement logging setup.
    *   Implement the main execution loop.
    *   Add CLI argument parsing.

4.  **Develop Config (`config/pipeline.yaml`):**
    *   Create the example YAML file based on the schema defined above.

5.  **Develop Tests (`tests/test_pipeline.py`):**
    *   Write unit tests for transforms.
    *   Write integration tests for the pipeline.
    *   Run tests with `pytest` to ensure pass rate is 100%.

6.  **Documentation:**
    *   Add docstrings to all functions.
    *   Create a `README.md` explaining how to run the pipeline (`python src/pipeline.py --config config/pipeline.yaml`).

---

## 5. Risk Management & Edge Cases

| Risk | Mitigation |
| :--- | :--- |
| **Memory Overflow** | If input CSV is too large for RAM, add a note in `README` to use chunking (though `pandas` default is in-memory). For this scope, assume fit-in-memory. |
| **Schema Mismatch** | If a column referenced in `compute` doesn't exist, catch `KeyError` and log specific column name. |
| **Dry-Run Logic** | Ensure `dry_run` flag is passed to the write function explicitly to prevent accidental writes. |
| **YAML Syntax Errors** | Wrap config loading in `try-except` to catch `yaml.YAMLError` and provide a helpful message. |

---

## 6. Final Review Checklist
- [ ] Does `pipeline.py` use `pandas`? **Yes.**
- [ ] Is `pipeline.yaml` used for configuration? **Yes.**
- [ ] Can transforms be chained? **Yes (via loop in pipeline.py).**
- [ ] Is dry-run supported? **Yes (flag in pipeline.py).**
- [ ] Is logging configurable? **Yes (level in config/args).**
- [ ] Are all deliverables present? **Yes (pipeline.py, transforms.py, pipeline.yaml, test_pipeline.py).**

This plan ensures a clean separation of concerns, adheres to the constraints, and provides a robust foundation for the CSV data pipeline.

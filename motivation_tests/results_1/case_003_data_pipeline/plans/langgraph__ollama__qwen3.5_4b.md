---
case: case_003_data_pipeline
framework: langgraph
model: qwen3.5:4b
provider: ollama
session_id: None
duration_ms: 28201
duration_wall_s: 28.2
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T22:53:57.505160+00:00
error: None
---

# Plan

# Implementation Plan: Case 003 CSV Data Pipeline

## 1. Context & Key Assumptions

Since I cannot physically access the local file system at `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir`, I will proceed with the following explicit assumptions to ensure the plan is actionable:

*   **Assumption 1 (Directory Structure):** The project will reside in `/home/jye/publications/cases/case_003_data_pipeline/`. The source code will be placed in a `src/` subdirectory, while data will reside in `WorkingDir/`.
*   **Assumption 2 (Input Data):** Input CSV files will have standard headers (e.g., `id`, `name`, `value`). Some rows may contain missing values, which the pipeline should handle gracefully (e.g., via `dropna` or fill strategies).
*   **Assumption 3 (Transform Logic):**
    *   **Filter:** Accepts a column name and a condition (e.g., `> 50`).
    *   **Rename:** Accepts a dictionary mapping old column names to new ones.
    *   **Compute:** Accepts a function or expression to create a new column based on existing ones.
*   **Assumption 4 (Dependencies):** The environment will have `pandas`, `pyyaml`, and `pytest` installed.
*   **Assumption 5 (Logging):** Python's standard `logging` module will be used. Verbosity levels will be `DEBUG`, `INFO`, `WARNING`, `ERROR`.

## 2. Project File Structure

The following structure will be created within the project root:

```text
/home/jye/publications/cases/case_003_data_pipeline/
├── src/
│   ├── __init__.py
│   ├── pipeline.py      # Main orchestrator
│   └── transforms.py    # Transform functions
├── tests/
│   └── test_pipeline.py # Unit & Integration tests
├── WorkingDir/
│   ├── input_data.csv  # Sample input
│   └── pipeline.yaml   # Pipeline config (reference)
├── requirements.txt
└── README.md
```

## 3. Implementation Steps

### Step 1: Initialize Environment & Dependencies

1.  **Create `requirements.txt`:**
    *   Add `pandas>=2.0.0`.
    *   Add `pyyaml>=6.0`.
    *   Add `pytest>=7.0`.
2.  **Create `src/__init__.py`:**
    *   Ensure the package is importable.
3.  **Create `src/pipeline.py`:**
    *   Initialize the main class `CSVPipeline`.
    *   Import `logging` and `yaml`.
    *   Define the `__init__` method to accept `input_dir`, `output_dir`, `config_path`, `dry_run`, and `verbosity`.
    *   Implement `_load_config()` to read `pipeline.yaml`.
    *   Implement `_setup_logger()` to configure logging based on verbosity.
    *   Implement `run()` method to execute the pipeline steps.
    *   Implement `dry_run()` method (alias to `run()` with a flag to skip file writing).

### Step 2: Define Transform Functions (`transforms.py`)

1.  **Create `src/transforms.py`:**
2.  **Define Base Class:**
    *   Create class `BaseTransform`.
    *   Attributes: `name` (string), `params` (dict).
    *   Method `__call__(self, df)`: Returns a `pd.DataFrame`.
    *   Method `serialize()` and `deserialize()` for YAML compatibility.
3.  **Implement `FilterTransform`:**
    *   Accepts `column` and `condition` (string or callable).
    *   Logic: `df = df[df[column].apply(condition)]`.
4.  **Implement `RenameTransform`:**
    *   Accepts `mapping` (dict).
    *   Logic: `df = df.rename(columns=mapping)`.
5.  **Implement `ComputeTransform`:**
    *   Accepts `expression` (string or callable).
    *   Logic: `df = pd.concat([df, pd.DataFrame({new_col: expression})], axis=1)`.
6.  **Add Error Handling:**
    *   Catch `KeyError` if column doesn't exist.
    *   Catch `TypeError` if input is not a DataFrame.

### Step 3: Define Pipeline Configuration (`pipeline.yaml`)

1.  **Create `WorkingDir/pipeline.yaml`:**
2.  **Structure:**
    *   `input_dir`: Path to input CSVs.
    *   `output_dir`: Path to output CSVs.
    *   `verbosity`: Integer (0-30).
    *   `dry_run`: Boolean.
    *   `steps`: List of dictionaries.
3.  **Example Step Definition:**
    *   `{"name": "filter_high_values", "type": "filter", "params": {"column": "value", "condition": "> 100"}}`
    *   `{"name": "add_total", "type": "compute", "params": {"expression": "col_a + col_b"}}`
4.  **Validation:**
    *   Ensure `yaml.safe_load` is used to prevent arbitrary code execution.
    *   Ensure paths are relative to the project root or absolute paths are resolved.

### Step 4: Build Pipeline Orchestrator (`pipeline.py`)

1.  **Implement Step Execution:**
    *   Iterate through `config['steps']`.
    *   Instantiate the transform class based on `type`.
    *   Apply the transform to the current DataFrame.
    *   Log the step progress (e.g., "Applying filter on 1000 rows").
2.  **Handle Chaining:**
    *   Maintain a single `DataFrame` object across all steps.
    *   Ensure data types are preserved (e.g., `float` vs `int`).
3.  **Handle Output:**
    *   If `dry_run` is False:
        *   Write the final DataFrame to `output_dir/final_output.csv`.
        *   Log success message.
    *   If `dry_run` is True:
        *   Log the expected output schema and row count.
        *   Do not write to disk.
4.  **Error Handling:**
    *   Wrap the execution loop in `try/except`.
    *   Log specific errors for each step.
    *   Raise `PipelineError` if a step fails.

### Step 5: Write Unit Tests (`test_pipeline.py`)

1.  **Create `tests/test_pipeline.py`:**
2.  **Test Data Generation:**
    *   Create a helper function `create_sample_data()` to generate a `pd.DataFrame`.
3.  **Test Transform Functions:**
    *   Test `FilterTransform` with various conditions.
    *   Test `RenameTransform` with empty and non-empty mappings.
    *   Test `ComputeTransform` with arithmetic expressions.
4.  **Test Pipeline Orchestration:**
    *   Mock `yaml.safe_load` to return a static config.
    *   Mock `pd.read_csv` to return sample data.
    *   Test `run()` with `dry_run=False` (verify file creation).
    *   Test `run()` with `dry_run=True` (verify no file creation, logs present).
5.  **Test Logging:**
    *   Verify `logging` level matches `verbosity` setting.
6.  **Run Tests:**
    *   Use `pytest` to execute the test suite.

## 4. Validation & Testing Strategy

1.  **Code Review Checklist:**
    *   [ ] All transforms return `pd.DataFrame`.
    *   [ ] `pipeline.yaml` is valid YAML.
    *   [ ] `dry_run` flag prevents file I/O.
    *   [ ] Logging is configured correctly.
2.  **Execution Plan:**
    *   Run `pytest` to ensure all unit tests pass.
    *   Run `python src/pipeline.py` with `dry_run=True` to verify logic flow.
    *   Run `python src/pipeline.py` with `dry_run=False` to verify output generation.
3.  **Edge Cases to Verify:**
    *   Empty input CSV.
    *   CSV with no matching filter conditions.
    *   Missing columns in `ComputeTransform`.

## 5. Deliverables Summary

Upon completion of the plan, the following artifacts will exist:

1.  **`src/pipeline.py`**: Contains the `CSVPipeline` class handling orchestration, config loading, and execution logic.
2.  **`src/transforms.py`**: Contains `BaseTransform`, `FilterTransform`, `RenameTransform`, and `ComputeTransform`.
3.  **`WorkingDir/pipeline.yaml`**: Contains the configuration for the pipeline steps, paths, and verbosity.
4.  **`tests/test_pipeline.py`**: Contains comprehensive tests for transforms and the pipeline flow.
5.  **`requirements.txt`**: Lists necessary Python dependencies.

## 6. Next Actions

1.  Create the directory structure.
2.  Write `transforms.py` first to ensure the building blocks are solid.
3.  Write `pipeline.yaml` to define the expected behavior.
4.  Implement `pipeline.py` to glue the components together.
5.  Implement `test_pipeline.py` to validate the implementation.
6.  Execute the plan to verify functionality.

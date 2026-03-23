---
case: case_003_data_pipeline
framework: aider
model: qwen3.5:4b
provider: ollama
session_id: None
duration_ms: 24355
duration_wall_s: 24.4
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T22:54:11.214780+00:00
error: None
---

# Plan

### Implementation Plan: Case 003 CSV Data Pipeline

**Assumptions:**
1.  **Directory Structure:** The `WorkingDir` contains `input/` and `output/` subdirectories. The project root is `/home/jye/publications/cases/case_003_data_pipeline/`.
2.  **CSV Format:** All input CSV files are UTF-8 encoded and contain headers.
3.  **Dependencies:** `pandas` and `PyYAML` are available.
4.  **Logging:** Standard Python `logging` module is used with a configurable level (INFO/WARN/ERROR).
5.  **Transforms:** Transforms are stateless functions that accept a `pd.DataFrame` and return a `pd.DataFrame`.
6.  **Pipeline Config:** `pipeline.yaml` defines a list of steps, where each step specifies the transform type and parameters.

---

### Step-by-Step Implementation Plan

#### 1. Project Structure Setup
*   **Action:** Create the directory structure.
*   **Details:** Ensure `input/` and `output/` directories exist in `WorkingDir`. Create `case_003_data_pipeline/` root folder containing `pipeline.py`, `transforms.py`, `pipeline.yaml`, and `test_pipeline.py`.

#### 2. Implement `transforms.py`
*   **Action:** Create a module containing individual transform functions.
*   **Details:**
    *   Define a base class `BaseTransform` (optional, but recommended for consistency) or use standalone functions.
    *   Implement `filter_rows(df, condition)`: Filters rows based on a boolean condition (e.g., `df[df['col'] > 0]`).
    *   Implement `rename_columns(df, mapping)`: Renames columns based on a dictionary.
    *   Implement `compute_derived(df, new_col, func)`: Creates a new column using a function (e.g., `df['total'] = df['col1'] + df['col2']`).
    *   Add type hints for clarity.
    *   Add docstrings describing input/output and parameters.

#### 3. Implement `pipeline.py`
*   **Action:** Create the main orchestrator script.
*   **Details:**
    *   **Imports:** Import `pandas`, `logging`, `yaml`, and `transforms`.
    *   **Logging Config:** Initialize a logger with a configurable level (default INFO).
    *   **Load Config:** Function to read `pipeline.yaml` and validate the structure.
    *   **Load Data:** Function to read all CSV files from `input/` directory into a list of DataFrames.
    *   **Apply Transforms:** Iterate through the steps defined in the YAML config.
        *   For each step, call the corresponding transform function from `transforms.py`.
        *   Chain the DataFrames (concatenate results if multiple files, or process sequentially).
    *   **Dry-Run Mode:**
        *   Add a `--dry-run` flag (or config option).
        *   If `True`, log what would be done (file names, transforms applied) but do not write to `output/`.
    *   **Write Output:** If not dry-run, write the final DataFrame(s) to `output/` as CSV.
    *   **Error Handling:** Wrap file I/O and processing in try-except blocks to log errors gracefully.

#### 4. Define `pipeline.yaml`
*   **Action:** Create the configuration file.
*   **Details:**
    *   Define a top-level key `steps`.
    *   Each step should have: `name`, `transform_type` (e.g., `filter`, `rename`, `compute`), and `params`.
    *   Example structure:
        ```yaml
        steps:
          - name: step_1
            transform_type: filter
            params:
              condition: "age > 18"
          - name: step_2
            transform_type: rename
            params:
              mapping: { "col_a": "new_name" }
        ```
    *   Add a `dry_run` boolean at the root level.

#### 5. Implement `test_pipeline.py`
*   **Action:** Create unit tests for the pipeline components.
*   **Details:**
    *   **Mock Data:** Create sample DataFrames for testing transforms.
    *   **Test Transforms:** Verify `filter_rows`, `rename_columns`, and `compute_derived` return correct DataFrames.
    *   **Test Pipeline:**
        *   Test with `dry_run=True` (assert no files written).
        *   Test with `dry_run=False` (assert files written to `output/`).
        *   Test error handling (e.g., missing column in rename).
    *   **Logging Tests:** Verify log messages are generated correctly.

#### 6. Logging Configuration
*   **Action:** Ensure logging is configured in `pipeline.py`.
*   **Details:**
    *   Set up `logging.basicConfig` with a handler.
    *   Ensure log levels match the verbosity requirement (e.g., DEBUG for dry-run details, INFO for progress).

---

### Next Steps for Editor Engineer
1.  Initialize the directory structure.
2.  Write `transforms.py` first to ensure transform logic is reusable.
3.  Write `pipeline.py` to orchestrate the flow using `transforms.py`.
4.  Create `pipeline.yaml` to define the configuration schema.
5.  Write `test_pipeline.py` to validate the implementation.
6.  Run tests to ensure dry-run and write modes work as expected.

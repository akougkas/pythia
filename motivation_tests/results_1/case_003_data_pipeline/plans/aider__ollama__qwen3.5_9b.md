---
case: case_003_data_pipeline
framework: aider
model: qwen3.5:9b
provider: ollama
session_id: None
duration_ms: 44439
duration_wall_s: 44.4
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T22:53:13.890527+00:00
error: None
---

# Plan

### Implementation Plan: Case 003 CSV Data Pipeline

**To:** Editor Engineer
**From:** Architect Engineer
**Subject:** Implementation Plan for Case 003 Data Pipeline

**Assumptions:**
1.  **Directory Structure:** The project root contains `input/`, `output/`, and the Python files (`pipeline.py`, `transforms.py`, `test_pipeline.py`). `pipeline.yaml` resides in the root.
2.  **Data Format:** Input CSVs are standard UTF-8 encoded. Output CSVs will overwrite or append based on config (default: overwrite).
3.  **Config Schema:** `pipeline.yaml` will define `input_dir`, `output_dir`, `dry_run` (bool), `log_level`, and a list of `transforms`.
4.  **Transform Interface:** All transforms will accept a `pandas.DataFrame` and return a `pandas.DataFrame`.
5.  **Logging:** Use Python's `logging` module. Log to console and a file (`pipeline.log`).
6.  **Error Handling:** Pipeline halts on critical errors (e.g., file not found, transform failure) but logs warnings for non-critical issues.

---

### Step 1: Configuration (`pipeline.yaml`)
**Action:** Create `pipeline.yaml` in the project root.
**Content:** Define the schema for the pipeline configuration.
```yaml
input_dir: "input"
output_dir: "output"
dry_run: false
log_level: "INFO"
transforms:
  - name: filter_rows
    config:
      condition: "age > 18"
  - name: rename_columns
    config:
      mapping:
        "full_name": "name"
        "city_code": "city"
  - name: compute_derived
    config:
      expression: "age * 365"
      new_column: "days_lived"
```
**Instruction:** Ensure the `transforms` list supports arbitrary chaining. Each transform must specify a `name` and a `config` dict.

### Step 2: Transform Library (`transforms.py`)
**Action:** Create `transforms.py`.
**Content:** Implement individual transform functions.
**Logic:**
1.  Import `pandas` and `logging`.
2.  Define functions: `filter_rows(df, condition)`, `rename_columns(df, mapping)`, `compute_derived(df, expression, new_column)`.
3.  Each function must:
    *   Accept a DataFrame and config parameters.
    *   Perform the operation.
    *   Return the modified DataFrame.
    *   Log a message upon completion (e.g., "Applied filter: ...").
4.  **Assumption:** Use `eval()` or `pandas.eval()` for expressions with caution (sanitize input if possible, or assume trusted config). For this plan, assume trusted config for simplicity.

### Step 3: Orchestrator (`pipeline.py`)
**Action:** Create `pipeline.py`.
**Content:** Main execution logic.
**Logic:**
1.  **Imports:** `pandas`, `yaml`, `logging`, `os`, `glob`.
2.  **Logging Setup:** Configure `logging` at startup based on `log_level` from config.
3.  **Function `load_config(path)`:** Load and validate `pipeline.yaml`.
4.  **Function `apply_transform(df, transform_spec)`:**
    *   Extract `name` and `config` from `transform_spec`.
    *   Import/Call the corresponding function from `transforms.py`.
    *   Execute transform.
    *   Log result.
5.  **Function `run_pipeline(config)`:**
    *   Iterate over all CSV files in `input_dir`.
    *   For each file:
        *   Load CSV into DataFrame.
        *   Apply each transform in sequence.
        *   If `dry_run` is True: Print summary of changes, do not write.
        *   If `dry_run` is False: Write to `output_dir` with original filename (or new name if specified).
6.  **Main Entry:** `if __name__ == "__main__":` block to call `run_pipeline`.

### Step 4: Testing (`test_pipeline.py`)
**Action:** Create `test_pipeline.py`.
**Content:** Unit tests for the pipeline.
**Logic:**
1.  **Imports:** `unittest` or `pytest` (assume `pytest` for brevity).
2.  **Mock Data:** Create a small in-memory DataFrame for testing.
3.  **Test Cases:**
    *   `test_filter_rows`: Verify rows are removed correctly.
    *   `test_rename_columns`: Verify column names match mapping.
    *   `test_compute_derived`: Verify new column exists and values are correct.
    *   `test_dry_run`: Verify `pipeline.py` does not write files when `dry_run=True`.
    *   `test_error_handling`: Verify pipeline logs error and stops on invalid transform.
4.  **Instruction:** Run tests via `pytest`.

### Step 5: Logging Strategy
**Action:** Integrate logging into `pipeline.py` and `transforms.py`.
**Logic:**
1.  Use `logging.basicConfig` in `pipeline.py` to set level.
2.  Use `logger.info()` for standard flow.
3.  Use `logger.error()` for critical failures.
4.  Ensure log messages include the filename being processed.

### Execution Flow
1.  Run `python pipeline.py` to execute the pipeline.
2.  Run `pytest test_pipeline.py` to verify functionality.
3.  Verify `output/` directory contains processed CSVs (unless `dry_run`).
4.  Verify `pipeline.log` contains execution logs.

**Immediate Next Step:** Begin implementation of `pipeline.yaml` and `transforms.py`.

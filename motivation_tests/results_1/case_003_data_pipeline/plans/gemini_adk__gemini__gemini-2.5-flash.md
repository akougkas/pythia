---
case: case_003_data_pipeline
framework: gemini_adk
model: gemini-2.5-flash
provider: gemini
session_id: None
duration_ms: 17739
duration_wall_s: 17.7
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T01:52:54.750238+00:00
error: None
---

# Plan

## Plan for CSV Data Pipeline

The objective is to design a data pipeline that reads CSV files, applies configurable transformations, and writes the results. This plan will detail the implementation of `pipeline.py`, `transforms.py`, an example `pipeline.yaml`, and `test_pipeline.py`, adhering to the specified constraints.

**Assumptions:**

1.  The `pipeline.yaml` will define `input_dir`, `output_dir`, and a list of `transforms`.
2.  Each transform in `pipeline.yaml` will have a `type` (e.g., `filter`, `rename`, `derive`) and a `params` dictionary specific to that transform.
3.  CSV files in the input directory will be processed one by one, and their transformed versions will be written to the output directory with the same filename.
4.  The `compute_derived_column` transform will accept a `formula` string that can be evaluated using `pandas.eval` for flexibility, operating on DataFrame columns.
5.  Logging verbosity will be controlled by a command-line argument for `pipeline.py`.

---

### Phase 1: Project Setup and Core Utilities

1.  **Project Structure:**
    *   Create the following files and directories:
        *   `pipeline.py`
        *   `transforms.py`
        *   `pipeline.yaml` (example)
        *   `test_pipeline.py`
        *   `WorkingDir/input/` (for sample CSVs)
        *   `WorkingDir/output/` (for transformed CSVs)

2.  **Logging Configuration (`pipeline.py`)**:
    *   Implement a function `setup_logging(verbose: bool)` that configures the standard `logging` module.
    *   Set the log level to `logging.DEBUG` if `verbose` is `True`, otherwise `logging.INFO`.
    *   Configure a formatter to include timestamp, log level, and message.
    *   Add a `StreamHandler` to output logs to the console.

3.  **YAML Configuration Loading (`pipeline.py`)**:
    *   Implement a function `load_pipeline_config(config_path: str) -> dict` that reads and parses the `pipeline.yaml` file using `pyyaml`.
    *   Include basic validation to ensure `input_dir`, `output_dir`, and `transforms` keys are present in the loaded configuration.
    *   Raise a `ValueError` if the configuration is invalid.

---

### Phase 2: Transformation Functions (`transforms.py`)

This file will contain individual functions, each accepting a `pandas.DataFrame` and transform-specific parameters, returning a transformed `pandas.DataFrame`.

1.  **`filter_rows(df: pd.DataFrame, column: str, operator: str, value: Any) -> pd.DataFrame`**:
    *   **Description**: Filters rows based on a condition applied to a specified column.
    *   **Parameters**:
        *   `df`: Input DataFrame.
        *   `column`: Name of the column to filter on.
        *   `operator`: String representing the comparison operator (e.g., `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not in`).
        *   `value`: The value to compare against. For `in`/`not in`, this should be a list.
    *   **Implementation**: Use `df.query()` or boolean indexing based on the operator.

2.  **`rename_columns(df: pd.DataFrame, column_mapping: dict) -> pd.DataFrame`**:
    *   **Description**: Renames columns in the DataFrame.
    *   **Parameters**:
        *   `df`: Input DataFrame.
        *   `column_mapping`: A dictionary where keys are old column names and values are new column names.
    *   **Implementation**: Use `df.rename(columns=column_mapping)`.

3.  **`compute_derived_column(df: pd.DataFrame, new_column: str, formula: str) -> pd.DataFrame`**:
    *   **Description**: Creates a new column based on a formula involving existing columns.
    *   **Parameters**:
        *   `df`: Input DataFrame.
        *   `new_column`: Name of the new column to create.
        *   `formula`: A string representing the computation (e.g., `"col_A + col_B"`, `"col_C * 2"`, `"col_D.str.upper()"`, `"np.log(col_E)"`).
    *   **Implementation**: Use `df.eval(formula)` or `df.apply()` with a lambda function. For `df.eval`, ensure `numexpr` is available if complex expressions are expected. For string methods, direct access like `df['col_D'].str.upper()` is preferred. A safer approach might be to parse the formula into specific operations, but `df.eval` offers good flexibility. I will assume `df.eval` is acceptable, and `formula` can reference `df` columns directly.

---

### Phase 3: Main Orchestrator (`pipeline.py`)

This file will contain the main logic for executing the pipeline.

1.  **`apply_transform(df: pd.DataFrame, transform_config: dict) -> pd.DataFrame`**:
    *   **Description**: A dispatcher function that calls the appropriate transform function from `transforms.py` based on the `transform_config['type']`.
    *   **Parameters**:
        *   `df`: The DataFrame to transform.
        *   `transform_config`: A dictionary containing `type` and `params` for a single transform.
    *   **Implementation**: Use an `if/elif/else` structure or a dictionary mapping transform types to functions. Log the application of each transform.
    *   Handle potential `KeyError` or `TypeError` if transform parameters are missing or incorrect.

2.  **`run_pipeline(config_path: str, dry_run: bool = False, verbose: bool = False)`**:
    *   **Description**: The main function to orchestrate the entire pipeline.
    *   **Parameters**:
        *   `config_path`: Path to the `pipeline.yaml` file.
        *   `dry_run`: If `True`, show what would happen without writing files.
        *   `verbose`: If `True`, enable verbose logging.
    *   **Implementation**:
        *   Call `setup_logging(verbose)`.
        *   Call `load_pipeline_config(config_path)`.
        *   Get `input_dir`, `output_dir`, and `transforms` from the config.
        *   Create `output_dir` if it doesn't exist and `dry_run` is `False`.
        *   Iterate through all `.csv` files in `input_dir`:
            *   Log the current file being processed.
            *   Read the CSV into a `pandas.DataFrame`.
            *   For each `transform` in `config['transforms']`:
                *   Log the transform being applied.
                *   Call `apply_transform()` with the current DataFrame and transform config.
                *   Update the DataFrame with the result.
            *   If `dry_run` is `True`:
                *   Log that the file *would have been written* to `output_dir`.
                *   Log the first few rows of the *transformed* DataFrame.
            *   If `dry_run` is `False`:
                *   Write the final transformed DataFrame to `output_dir` with the original filename.
                *   Log the successful writing of the file.
        *   Handle exceptions (e.g., file not found, pandas errors) gracefully with logging.

3.  **Command-Line Interface (`pipeline.py`)**:
    *   Use `argparse` to handle command-line arguments:
        *   `--config`: Path to `pipeline.yaml` (required).
        *   `--dry-run`: Flag for dry-run mode (optional).
        *   `--verbose`: Flag for verbose logging (optional).
    *   Call `run_pipeline()` with the parsed arguments.

---

### Phase 4: Example Pipeline Configuration (`pipeline.yaml`)

Create a sample `pipeline.yaml` to demonstrate the pipeline's capabilities.

```yaml
input_dir: WorkingDir/input
output_dir: WorkingDir/output

transforms:
  - type: filter
    params:
      column: 'Value'
      operator: '>'
      value: 100

  - type: rename
    params:
      column_mapping:
        'Date': 'TransactionDate'
        'Value': 'Amount'

  - type: derive
    params:
      new_column: 'IsHighValue'
      formula: 'Amount > 500' # Example: boolean flag

  - type: derive
    params:
      new_column: 'AmountUSD'
      formula: 'Amount * 1.25' # Example: simple arithmetic
```

---

### Phase 5: Unit Tests (`test_pipeline.py`)

Use `pytest` for testing.

1.  **Setup/Teardown**:
    *   Create temporary input/output directories and sample CSV files for each test case.
    *   Clean up these directories after tests.

2.  **Test `transforms.py` functions**:
    *   **`test_filter_rows`**:
        *   Test with various operators (`==`, `>`, `in`).
        *   Test edge cases (no rows match, all rows match).
    *   **`test_rename_columns`**:
        *   Test renaming multiple columns.
        *   Test renaming a single column.
        *   Test with non-existent columns (should not raise error, pandas handles this).
    *   **`test_compute_derived_column`**:
        *   Test simple arithmetic (`+`, `*`).
        *   Test boolean logic.
        *   Test string operations (e.g., `.str.upper()`).
        *   Test with `numpy` functions (e.g., `np.log`).

3.  **Test `pipeline.py` core logic**:
    *   **`test_load_pipeline_config`**:
        *   Test loading a valid config.
        *   Test loading an invalid config (missing keys).
    *   **`test_run_pipeline_end_to_end`**:
        *   Run the pipeline with a sample config and input CSVs.
        *   Verify that output files are created in the correct directory.
        *   Load the output CSVs and assert their content matches expected transformed data.
    *   **`test_run_pipeline_dry_run`**:
        *   Run the pipeline in dry-run mode.
        *   Assert that no output files are created.
        *   Verify that appropriate dry-run log messages are generated (e.g., by capturing logs).
    *   **`test_logging_verbosity`**:
        *   Run the pipeline with and without `--verbose`.
        *   Capture logs and assert the presence/absence of DEBUG level messages.
    *   **`test_error_handling`**:
        *   Test with a non-existent input directory.
        *   Test with a malformed CSV file.
        *   Test with a transform referencing a non-existent column.

---

This plan covers all requirements and constraints, providing a structured approach to building the CSV data pipeline.

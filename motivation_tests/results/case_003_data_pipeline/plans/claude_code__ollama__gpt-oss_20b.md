---
case: case_003_data_pipeline
framework: claude_code
model: gpt-oss:20b
provider: ollama
session_id: 7ba1bd5a-5c4c-4861-aee9-2a418fbe4505
duration_ms: 43477
duration_wall_s: 45.9
cost_usd: 1.2136600000000002
num_turns: 7
timestamp: 2026-03-19T14:14:57.875026+00:00
error: None
---

# Plan

# Data Pipeline Design Plan

## Context
The objective is to build a reusable, configurable CSV data‑processing pipeline. Existing sample CSV files and a reference pipeline configuration are (assumed to be) present under `WorkingDir`. The pipeline should be:

* Read all CSVs from a user‑supplied input directory.
* Apply a series of transformations defined in `pipeline.yaml`.
* Write the resulting DataFrames to an output directory.
* Support a *dry‑run* mode that prints what would be done without touching the filesystem.
* Provide configurable logging verbosity.

The implementation will consist of four key components:

1. **`pipeline.py`** – Orchestrator that parses arguments, loads configuration, iterates through CSV files, and manages the execution flow.
2. **`transforms.py`** – A collection of pure functions that perform individual Pandas transformations (filtering, column renaming, derived‑column calculation, etc.).
3. **`pipeline.yaml`** – Example configuration that demonstrates how to chain arbitrary transforms.
4. **`test_pipeline.py`** – Unit tests exercising the orchestrator and transforms with fixture CSV data.

All code will be written in Python 3.11+ and will depend only on the standard library and **pandas**.

## High‑Level Architecture

```
+----------------------+          +---------------------------+
|  pipeline.py (orchestrator)  |  <--  |  transforms.py (transform fn)
+----------------------+          +---------------------------+
            |                                    |
            |  (pandas DataFrame)                 |
            v                                    v
   +----------------+          +----------------------------+
   |  CSV Reader   |  -->  |  Apply transforms (series) |
   +----------------+          +----------------------------+
            |                                    |
            v                                    v
   +----------------+          +----------------------------+
   |  CSV Writer   |  <--  |  Logging & Dry‑run handling |
   +----------------+          +----------------------------+
```

### Execution Flow
1. **Argument parsing** – `pipeline.py` accepts:
   * `--input-dir` (required)
   * `--output-dir` (required)
   * `--config` (required, path to `pipeline.yaml`)
   * `--dry-run` (flag)
   * `--verbosity` (`debug`, `info`, `warning`, `error`, `critical`)

2. **Load config** – The YAML file contains a list of steps, each step specifying:
   * `name` – human readable name
   * `type` – one of the supported transform keys
   * `params` – dict of parameters passed to the transform function

   Example:
   ```yaml
   steps:
     - name: filter_by_age
       type: filter_rows
       params:
         column: age
         min: 18
     - name: rename_columns
       type: rename_columns
       params:
         mapping:
           first_name: fname
           last_name: lname
     - name: compute_income_tax
       type: add_column
       params:
         new_column: income_tax
         formula: "income * 0.2"
   ```

3. **Processing loop** – For each CSV file in the input directory:
   * Load into a Pandas DataFrame.
   * Sequentially apply each transform defined in the config. Each transform function receives the DataFrame and the `params` dict.
   * If `--dry-run` is set, skip writing and instead log the filename, the list of applied steps, and a preview (first 5 rows) of the transformed DataFrame.
   * Otherwise, write the final DataFrame to the output directory, preserving the original filename.

4. **Logging** – The orchestrator configures the root logger based on the `--verbosity` flag. Dry‑run logs will include `DEBUG` level details.

## Detailed Component Specification

### 1. `transforms.py`
Define the following public functions (all accept a `pandas.DataFrame` and a `params` dict, return a transformed DataFrame):

| Function | Purpose | Example `params` | Notes |
|----------|---------|-----------------|-------|
| `filter_rows(df, params)` | Keep rows where a column satisfies a condition. Supports `min`, `max`, `in` lists. | `{ "column": "age", "min": 18 }` | Uses `df[condition]`.
| `rename_columns(df, params)` | Rename columns using a mapping dict. | `{ "mapping": { "first_name": "fname" } }` | `df.rename(columns=...)`.
| `add_column(df, params)` | Add a new column computed from existing columns. Supports simple arithmetic or `formula` as a Python `eval` string. | `{ "new_column": "income_tax", "formula": "income * 0.2" }` | Use `pd.eval` or `df.eval` for safety.
| `drop_columns(df, params)` | Drop columns by list. | `{ "columns": ["temp", "debug"] }` | `df.drop(columns=...)`.
| `convert_dtypes(df, params)` | Convert column types. | `{ "types": { "date": "datetime64[ns]" } }` | `df.astype`.
| `apply_custom(df, params)` | Apply a user‑supplied lambda string. | `{ "function": "lambda df: df.assign(total=df["a"]+df["b"])" }` | Use `eval` safely.

Each function should validate that required keys exist in `params` and raise `ValueError` with a helpful message if not.

### 2. `pipeline.py`
Key modules/functions:

* `load_config(path: str) -> dict`
* `get_transform(name: str, params: dict) -> Callable[[pd.DataFrame], pd.DataFrame]`
* `process_file(input_path: Path, output_path: Path, steps: list, dry_run: bool, logger: Logger) -> None`
* `main()` – parses args, sets up logging, loops over CSVs.

Use `argparse` for CLI parsing. For YAML parsing, use `yaml.safe_load` from PyYAML.

### 3. `pipeline.yaml`
Provide an example config that demonstrates all supported transform types. The file should be placed in the repo root (or in `WorkingDir` for reference). Include comments explaining each section.

### 4. `test_pipeline.py`
Write pytest tests:

* `test_transforms()` – test each transform function in isolation with a small DataFrame fixture.
* `test_pipeline_dry_run()` – run `pipeline.py` with `--dry-run` and assert that the expected logs are produced and no files are written.
* `test_pipeline_write()` – run full pipeline with a temporary input directory and assert that output files exist and match expected content.

Use `tmp_path` fixture to create isolated directories.

## Verification Plan
1. **Unit tests** – Run `pytest test_pipeline.py` to ensure all transform functions work and the pipeline orchestrator behaves correctly in dry‑run and real‑run modes.
2. **End‑to‑end** – Manually run `python pipeline.py --input-dir WorkingDir/csv --output-dir WorkingDir/out --config WorkingDir/pipeline.yaml` and inspect output files.
3. **Logging** – Execute with `--verbosity debug` and confirm detailed logs. Verify that dry‑run mode logs the preview of the transformed DataFrame.
4. **Error handling** – Provide malformed config and confirm the program exits with a meaningful error message.

## Next Steps
* Implement `transforms.py` with the specified functions.
* Implement `pipeline.py` orchestrator.
* Create example `pipeline.yaml`.
* Write unit tests in `test_pipeline.py`.
* Run tests to confirm correctness.

---

*Assumptions:* Sample CSV files and reference `pipeline.yaml` exist under `WorkingDir`. The repository contains a `requirements.txt` with `pandas` and `pyyaml` as dependencies.


---
case: case_003_data_pipeline
framework: agents_sdk
model: gpt-oss:20b
provider: ollama
session_id: None
duration_ms: 13588
duration_wall_s: 13.6
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T23:09:04.935181+00:00
error: None
---

# Plan

## Implementation Plan – CSV Data Pipeline (Case 003)

### 1. Project Layout
```
/home/jye/publications/cases/case_003_data_pipeline/
├── pipeline.py            # Main orchestrator
├── transforms.py          # Stand‑alone transform functions
├── pipeline.yaml          # Example pipeline definition
├── test_pipeline.py       # pytest test‑suite
├── WorkingDir/            # Sample CSV files + reference pipeline config
├── requirements.txt
└── README.md
```

> **Assumption** – The working directory contains a set of CSV files we will use for testing.  
> All code is intended for a *Python 3.10+* environment.

---

### 2. Dependencies (`requirements.txt`)

```
pandas>=2.0
pyyaml>=6.0
pytest>=7.0
```

(If you want nicer YAML round‑trips you can swap **pyyaml** for **ruamel.yaml** – the plan uses **pyyaml** for simplicity.)

---

### 3. Design Overview

| Concern | Responsibility | Key Files |
|---------|----------------|-----------|
| Orchestrator | Argument parsing, logging, config loading, file iteration, dry‑run handling, error handling | `pipeline.py` |
| Transformation logic | Small, reusable, pure functions that accept a `DataFrame` and return a new `DataFrame` | `transforms.py` |
| Configuration | Human‑readable list of transforms with parameters | `pipeline.yaml` |
| Testing | Unit‑tests for both individual transforms and the end‑to‑end pipeline | `test_pipeline.py` |
| Sample data / usage | Provide reproducible input | `WorkingDir/` |

---

### 4. Detailed Module Specifications

#### 4.1 `transforms.py`

*Expose a registry of transform functions; each function should have the signature*

```python
def transform_name(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    ...
```

| Function | Purpose | Parameters (`params`) | Notes |
|----------|---------|-----------------------|-------|
| `filter_rows` | Keeps rows that satisfy a condition | `{'column': str, 'min_value': value|None, 'max_value': value|None, 'condition': str|None}` | If `condition` is supplied it overrides the min/max logic. Use `df.query()` for string expression. |
| `rename_columns` | Renames columns | `{'mapping': dict[str, str]}` | Dictionary: old → new. |
| `add_derived_column` | Adds a new column calculated from existing ones | `{'column': str, 'formula': str}` | `formula` is a valid pandas Expression that may reference `df` or not; we use `df.eval(formula)` for safety. |
| `drop_columns` | Removes unwanted columns | `{'columns': list[str]}` | Simple wrapper around `df.drop(columns=...)`. |
| `handle_missing` | Impute or drop missing values | `{'strategy': 'drop'|'fill', 'method': 'mean'|'median'|'most_frequent'|value}` | Not required by spec, but useful for robustness. |
| `cast_types` | Cast column dtype | `{'columns': dict[str, str]}` | e.g. `{'age': 'Int64', 'salary': 'float'}` |

*Registry implementation:*

```python
TRANSFORMS = {
    'filter_rows': filter_rows,
    'rename_columns': rename_columns,
    'add_derived_column': add_derived_column,
    'drop_columns': drop_columns,
    'handle_missing': handle_missing,
    'cast_types': cast_types,
}
```

*Helper to apply a transform by name:*

```python
def apply_transform(df: pd.DataFrame, name: str, params: dict):
    func = TRANSFORMS.get(name)
    if func is None:
        raise ValueError(f"Unknown transform: {name}")
    return func(df, params)
```

#### 4.2 `pipeline.py`

1. **Argument Parser (`argparse`)**
   * `--input-dir` (default: current working dir)
   * `--output-dir` (default: `output/` inside work dir)
   * `--config` (`pipeline.yaml` by default)
   * `--dry-run` (store_true)
   * `--log-level` (choices: `DEBUG`, `INFO`, `WARNING`, `ERROR`; default `INFO`)

2. **Logging Setup**
   * Use `logging.basicConfig(level=log_level, format=…)`
   * Add file handler if desired; for simplicity we log to console only.

3. **Configuration Loading**
   * Load YAML into a dictionary.
   * Validate that top‑level key `transforms` exists and is a list.
   * Optional validation: each item has `name` and `params` dict.

4. **File Discovery**
   * Recursively walk `input_dir` and collect all `.csv` files.
   * Keep relative paths to mirror structure in `output_dir`.

5. **Processing Loop**

```python
for file_path in csv_files:
    logger.info("Processing %s", file_path)
    df = pd.read_csv(file_path)

    for step in config["transforms"]:
        name = step["name"]
        params = step.get("params", {})
        logger.debug("Applying %s with %s", name, params)
        df = apply_transform(df, name, params)

    if dry_run:
        logger.info("[Dry‑run] Would write to %s", output_path)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info("Wrote to %s", output_path)
```

6. **Error Handling**
   * Wrap transform application in `try/except` to log failures and optionally skip file.
   * Provide a global catch for unexpected errors; exit with non‑zero status.

7. **Entry Point**
   ```python
   if __name__ == "__main__":
       main()
   ```

---

#### 4.3 `pipeline.yaml` (example)

```yaml
transforms:
  - name: filter_rows
    params:
      column: age
      min_value: 18

  - name: rename_columns
    params:
      mapping:
        dob: date_of_birth
        emp_id: employee_id

  - name: add_derived_column
    params:
      column: age_group
      # Use pandas eval – it implicitly accesses columns by name
      formula: "np.where(df['age'] >= 60, 'Senior', np.where(df['age'] >= 18, 'Adult', 'Minor'))"

  - name: drop_columns
    params:
      columns:
        - password
        - ssn
```

> **Assumption** – The `formula` string may reference `df` or just column names; we use `df.eval(formula)` which understands both.

---

#### 4.4 `test_pipeline.py`

Using `pytest` and `tempfile` for isolation.

1. **Fixtures**
   * `tmp_input_dir` – create temp dir and write sample CSV(s).
   * `tmp_output_dir` – another temp dir.
   * `sample_config_yaml` – write the example pipeline.

2. **Unit Tests for Transforms**
   * `test_filter_rows()`
   * `test_rename_columns()`
   * `test_add_derived_column()`
   * Use small DataFrames, assert equality.

3. **Pipeline Integration Tests**
   * `test_pipeline_runs_and_writes(tmp_input_dir, tmp_output_dir, sample_config_yaml)`
     * Invoke `pipeline.main()` programmatically using `argparse.Namespace` or by invoking `subprocess` with `--dry-run` off.
     * Verify that output CSV exists and contents match expected DataFrame.

   * `test_pipeline_dry_run(tmp_input_dir, tmp_output_dir, sample_config_yaml, caplog)`
     * Run with `--dry-run`.
     * Assert that no files are created in `output_dir`.
     * Check that caplog captured the expected “would write” messages.

4. **Edge Case Tests**
   * `test_unknown_transform_raises()`
   * `test_missing_params_raises()`

5. **Test Logging Verbosity**
   * `test_log_level_setting()` – ensures that the chosen log level actually affects output stream.

> **Assumption** – The test harness can import `pipeline` and `transforms`; we will expose `apply_transform` for isolated tests.

---

### 5. Execution Flow Summary

1. User runs:
   ```bash
   python pipeline.py --input-dir WorkingDir/data \
                      --output-dir WorkingDir/output \
                      --config pipeline.yaml \
                      --dry-run # optional
   ```
2. `pipeline.py`:
   * Parses arguments.
   * Loads config.
   * Discovers CSVs.
   * For each file:
     * Reads into a `DataFrame`.
     * Iteratively applies transform functions via registry.
     * In dry‑run mode: logs intended write target, else writes CSV.
3. Logging provides step‑by‑step detail; verbosity controlled by `--log-level`.
4. Unit tests ensure correctness of individual transforms, end‑to‑end pipeline, dry‑run mode, and error handling.

---

### 6. Additional Recommendations (Optional Enhancements)

- **Configuration Validation** – Use `pydantic` or `cerberus` to strictly validate the YAML schema.
- **Parallel Processing** – For large inputs, process files in a `ThreadPoolExecutor`.
- **Custom Transform Registration** – Allow users to add new transforms by editing `TRANSFORMS` registry.
- **Progress Bar** – Integrate `tqdm` for visual feedback on file processing.

---

### 7. Deliverables Overview

| File | Content |
|------|---------|
| `pipeline.py` | Orchestrator, CLI, config loader, main loop |
| `transforms.py` | Pure transform functions + registry |
| `pipeline.yaml` | Sample pipeline config illustrating transform chaining |
| `test_pipeline.py` | Full test suite covering unit and integration tests |
| `requirements.txt` | Package list |
| `README.md` | Quick start guide (optional) |

All components are self‑contained, rely only on the standard library and the listed third‑party packages, and satisfy the constraints:

* Uses `pandas` for manipulation.
* Steps defined in `pipeline.yaml`.
* Arbitrary chaining via the registry.
* Dry‑run capability.
* Configurable logging verbosity.

---

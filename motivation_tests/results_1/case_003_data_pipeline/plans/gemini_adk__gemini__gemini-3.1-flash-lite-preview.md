---
case: case_003_data_pipeline
framework: gemini_adk
model: gemini-3.1-flash-lite-preview
provider: gemini
session_id: None
duration_ms: 11228
duration_wall_s: 11.2
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T02:04:58.403014+00:00
error: None
---

# Plan

This implementation plan outlines the development of a modular, configuration-driven CSV data pipeline.

### Assumptions
1. **Configuration Schema:** The `pipeline.yaml` will follow a structure where a `steps` list defines the sequence of operations, each containing a `type` (the function name) and `params` (a dictionary of arguments).
2. **Transform Signature:** All functions in `transforms.py` will accept a `pandas.DataFrame` as the first argument and return a modified `pandas.DataFrame`.
3. **Environment:** The system has `pandas` and `pyyaml` installed.
4. **File Handling:** The pipeline will process all `.csv` files found in the input directory and output them to the output directory with the same filenames.

---

### Phase 1: Configuration Design (`pipeline.yaml`)
*   Define the YAML structure to support chaining.
*   Example structure:
    ```yaml
    steps:
      - type: "filter_rows"
        params: { "column": "status", "value": "active" }
      - type: "rename_columns"
        params: { "mapping": { "old_name": "new_name" } }
      - type: "compute_derived"
        params: { "new_col": "total", "formula": "price * quantity" }
    ```

### Phase 2: Transform Library (`transforms.py`)
*   Implement a registry pattern to map string identifiers from the YAML to actual Python functions.
*   **Functions to implement:**
    *   `filter_rows(df, column, value)`: Filters rows based on equality.
    *   `rename_columns(df, mapping)`: Renames columns using a dictionary.
    *   `compute_derived(df, new_col, formula)`: Uses `df.eval()` or standard pandas operations to create new columns.
*   Include error handling for missing columns or invalid operations.

### Phase 3: Pipeline Orchestrator (`pipeline.py`)
*   **Argument Parsing:** Use `argparse` to handle `--input`, `--output`, `--config`, `--dry-run`, and `--log-level`.
*   **Logging:** Configure the `logging` module based on the verbosity flag.
*   **Execution Logic:**
    1. Load `pipeline.yaml`.
    2. Iterate through files in the input directory.
    3. Read CSV into a `pandas.DataFrame`.
    4. Loop through the `steps` defined in the config, calling the corresponding function from `transforms.py`.
    5. **Dry-run check:** If enabled, log the transformation steps and print the dataframe head instead of writing to disk.
    6. If not dry-run, write the resulting DataFrame to the output directory.

### Phase 4: Unit Testing (`test_pipeline.py`)
*   Use `pytest` to verify the pipeline.
*   **Test Cases:**
    *   Verify each transform function returns the expected DataFrame shape and values.
    *   Verify the pipeline correctly chains multiple transforms.
    *   Verify the dry-run mode does not create output files.
    *   Verify error handling when a CSV file is malformed or a transform parameter is missing.

### Phase 5: Final Review
*   Ensure all deliverables are present in the root directory.
*   Verify that the code adheres to PEP 8 standards.
*   Confirm that the `WorkingDir` sample files can be processed successfully by the pipeline.

---

### Implementation Schedule
1. **Day 1:** Setup project structure and implement `transforms.py` with unit tests.
2. **Day 2:** Develop `pipeline.py` orchestrator, including YAML parsing and file I/O logic.
3. **Day 3:** Implement dry-run functionality, logging, and final integration testing against `WorkingDir` samples.

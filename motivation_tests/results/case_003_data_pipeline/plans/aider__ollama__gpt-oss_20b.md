---
case: case_003_data_pipeline
framework: aider
model: gpt-oss:20b
provider: ollama
session_id: None
duration_ms: 14515
duration_wall_s: 14.5
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T22:53:56.698935+00:00
error: None
---

# Plan

**Implementation Plan – Case 003: CSV Data Pipeline**

---

### 1. Project Structure
```
case_003_data_pipeline/
├── pipeline.py          # Orchestrator
├── transforms.py        # Individual transform functions
├── pipeline.yaml        # Example configuration
├── tests/
│   └── test_pipeline.py # Unit tests
├── WorkingDir/          # Sample CSVs & reference config
└── requirements.txt     # pandas, pyyaml, pytest, etc.
```

---

### 2. Configuration (`pipeline.yaml`)

1. **Top‑level keys**  
   - `input_dir`: path to CSV files to read.  
   - `output_dir`: path where processed files will be written.  
   - `dry_run`: boolean flag.  
   - `log_level`: e.g., `DEBUG`, `INFO`, `WARNING`.  
   - `steps`: ordered list of transformation steps.

2. **Step schema**  
   Each step is a mapping with:
   - `name`: unique identifier (used for logging).  
   - `type`: one of `filter_rows`, `rename_columns`, `add_column`.  
   - `params`: dictionary of parameters specific to the type.

3. **Example**  
   ```yaml
   input_dir: "./WorkingDir/input"
   output_dir: "./WorkingDir/output"
   dry_run: false
   log_level: INFO
   steps:
     - name: filter_age
       type: filter_rows
       params:
         column: age
         operator: ">"
         value: 30
     - name: rename
       type: rename_columns
       params:
         mapping:
           first_name: fname
           last_name: lname
     - name: compute_fullname
       type: add_column
       params:
         new_column: full_name
         expression: "df['fname'] + ' ' + df['lname']"
   ```

---

### 3. Logging Setup

- Use Python’s built‑in `logging` module.  
- In `pipeline.py`, create a logger named `pipeline`.  
- Configure level from config (`log_level`).  
- Add a console handler with a simple formatter.  
- In dry‑run mode, set logger to `DEBUG` to show detailed actions.

---

### 4. Transform Functions (`transforms.py`)

Define a **base interface**:

```python
def transform(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    ...
```

Implement the following functions:

| Function | Purpose | Key Parameters |
|----------|---------|----------------|
| `filter_rows` | Keep rows where a column satisfies a condition | `column`, `operator`, `value` |
| `rename_columns` | Rename columns according to a mapping | `mapping` (dict) |
| `add_column` | Add a new column computed from an expression | `new_column`, `expression` |

*Implementation notes*  
- Use `operator` mapping (`==`, `!=`, `<`, `>`, `<=`, `>=`) to build a boolean mask.  
- For `add_column`, evaluate the expression with `eval` in a safe namespace: `{'df': df, 'np': np}`.  
- Each function should log its action and return the modified DataFrame.

---

### 5. Orchestrator (`pipeline.py`)

1. **Argument Parsing**  
   - Accept optional `--config` path (default `pipeline.yaml`).  
   - Optional `--dry-run` flag to override config.

2. **Load Configuration**  
   - Use `yaml.safe_load`.  
   - Validate required keys; raise informative errors.

3. **Setup Logging**  
   - Call helper to configure logger.

4. **Discover Input Files**  
   - List all `.csv` files in `input_dir`.  
   - Log the count.

5. **Process Each File**  
   For each file:
   - Read with `pd.read_csv`.  
   - Log file name and initial shape.  
   - Iterate over `steps` in order:
     - Retrieve the corresponding function from `transforms.py` via a mapping (`{'filter_rows': filter_rows, ...}`).  
     - Call it with current DataFrame and `params`.  
     - Log intermediate shape after each step.  
   - After all steps, if not `dry_run`:
     - Ensure `output_dir` exists (`os.makedirs(..., exist_ok=True)`).  
     - Write DataFrame to CSV with same base name in `output_dir`.  
     - Log success.  
   - If `dry_run`, log what would be written (file name, final shape).

6. **Summary**  
   - At end, log total files processed, total rows processed, time taken.

---

### 6. Unit Tests (`tests/test_pipeline.py`)

1. **Setup**  
   - Use `pytest` fixtures to create temporary directories and sample CSVs.  
   - Write a minimal `pipeline.yaml` for tests.

2. **Test Cases**  
   - **Test 1 – Filter Rows**  
     - Verify that rows not satisfying condition are removed.  
   - **Test 2 – Rename Columns**  
     - Verify columns are renamed correctly.  
   - **Test 3 – Add Column**  
     - Verify new column is computed as expected.  
   - **Test 4 – Full Pipeline**  
     - Run orchestrator on sample CSV, check output file exists and matches expected DataFrame.  
   - **Test 5 – Dry‑Run**  
     - Run with `dry_run=True`, assert that no output files are created.  
   - **Test 6 – Logging**  
     - Capture logs and assert that key messages appear.

3. **Utilities**  
   - Helper to compare DataFrames (`pd.testing.assert_frame_equal`).  
   - Use `tmp_path` fixture for isolation.

---

### 7. Dependencies (`requirements.txt`)

```
pandas>=2.0
pyyaml>=6.0
pytest>=7.0
```

---

### 8. Build & Run Instructions

- Install dependencies: `pip install -r requirements.txt`.  
- Run pipeline: `python pipeline.py --config pipeline.yaml`.  
- Dry‑run: `python pipeline.py --config pipeline.yaml --dry-run`.  
- Run tests: `pytest tests/`.

---

### 9. Assumptions & Edge Cases

- **Assumption**: All CSVs have a header row.  
- **Assumption**: `expression` in `add_column` uses only `df` and standard Python functions; no external libraries.  
- **Edge Case**: If a step references a non‑existent column, raise a clear `KeyError` with step name.  
- **Edge Case**: If `output_dir` is same as `input_dir`, warn that files may be overwritten.  

---

### 10. Deliverables Checklist

- [ ] `pipeline.py` – orchestrator with logging, config parsing, dry‑run support.  
- [ ] `transforms.py` – three transform functions with proper logging.  
- [ ] `pipeline.yaml` – example config matching the schema.  
- [ ] `tests/test_pipeline.py` – comprehensive unit tests covering all functionality.  
- [ ] `requirements.txt` – list of required packages.  

---

---
case: case_003_data_pipeline
framework: agents_sdk
model: qwen3.5:9b
provider: ollama
session_id: None
duration_ms: 26282
duration_wall_s: 26.3
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T23:08:38.640860+00:00
error: None
---

# Plan

# Case 003: CSV Data Pipeline - Implementation Plan

## Document Information
- **Prepared By**: System Planner
- **Target Directory**: `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir`
- **Date**: Current session
- **Status**: Plan Ready (Not Executed)
- **Estimation Time**: ~2-4 hours development estimated

---

## 1. Assumptions & Constraints Clarification

Because the WorkingDir materials are not accessible in this planning session, the following assumptions are made:

| Item | Assumption |
|------|------------|
| Sample CSV files | Assume standard CSV with headers, potentially including datetime columns, numeric columns, and text columns |
| Transform complexity | Assume transforms are composable and each transform can depend on previous transforms |
| Pipeline configuration | Assume Yaml supports nested dictionaries and list of steps |
| Logging verbosity | Assume log levels: DEBUG, INFO, WARNING, ERROR |
| Output format | Assume CSV output with same column count as after final transform |

---

## 2. Project Structure

```
WorkingDir/
├── pipeline.py              # Main orchestrator
├── transforms.py            # Transform function implementations
├── pipeline.yaml            # Configuration file (example)
├── test_pipeline.py         # Unit tests
├── logs/                    # Directory for log files
├── input/                   # Input CSV directory (example)
│   └── data_sample.csv
├── output/                  # Output CSV directory
├── transforms/              # Optional package for organized transforms
│   ├── filters.py
│   ├── renames.py
│   └── computed.py
├── logs/
│   └── pipeline.log
└── config.py
```

---

## 3. Configuration Schema (`pipeline.yaml`)

### Expected Key Fields:

```yaml
name: sample_pipeline
dry_run: false
log_level: INFO

# Input/output directories
input_dir: "/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/input"
output_dir: "/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/output"

# List of steps (transforms)
steps:
  - name: drop_empty_rows
    action: drop_empty_rows
    conditions:
      - null_check: true
      - empty_column: true

  - name: drop_invalid_dates
    action: drop_invalid_dates
    date_column: "event_date"
    date_format: "%Y-%m-%d"
    missing_date_behavior: "drop"

  - name: filter_low_salaries
    action: filter_rows
    condition_type: "greater_than"
    column: "salary"
    value: 30000

  - name: rename_column
    action: rename_column
    from: "old_name"
    to: "new_name"

  - name: add_department
    action: add_column
    column: "department"
    value: "Engineering"
    fill_mode: "constant"
```

---

## 4. Component Implementation Plan

### 4.1 `config.py` - Configuration Loader

**Purpose:** Load and validate pipeline configuration from YAML file.

**Implementation Details:**
| Function Signature | Description |
|-------------------|-------------|
| `load_config(path: str)` | Parse YAML and convert to config dict object |
| `validate_config(config)` | Check required fields and transform actions exist |
| `get_step(step_name)` | Retrieve step by name from steps list |
| `get_steps()` | Return list of step dicts |

**Assumptions:**
- YAML validation errors will be logged as warnings if dry_run mode
- Missing input directory will be handled with FileNotFoundError

---

### 4.2 `transforms.py` - Transform Library

**Purpose:** Implement individual transform functions.

**Transform Functions List:**

| Function Name | Input | Output | Description |
|---------------|-------|--------|-------------|
| `drop_empty_rows(df)` | DataFrame | DataFrame | Remove rows with all-null or many-null values |
| `rename_columns(df, rename_dict)` | DataFrame, dict | DataFrame | Rename columns using mapping |
| `filter_rows(df, condition_func)` | DataFrame, callable | DataFrame | Apply custom filter function |
| `add_column(df, col_name, value)` | DataFrame, str, any | DataFrame | Add constant or derived column |
| `convert_dtypes(df, dtype_mapping)` | DataFrame, dict | DataFrame | Convert columns to specified types |
| `drop_columns(df, columns)` | DataFrame, list | DataFrame | Remove specified columns |
| `sort_columns(df, by_columns, ascending=True)` | DataFrame, list, bool | DataFrame | Sort by specified columns |

**Assumptions:**
- All transforms return the same DataFrame type (pandas DataFrame)
- All transforms accept df as first positional argument
- Invalid input will raise ValueError with descriptive message
- Transforms log their actions at appropriate log levels

---

### 4.3 `pipeline.py` - Main Orchestrator

**Purpose:** Orchestrate the pipeline, handle dry-run mode and logging.

**Primary Functions:**

| Function Signature | Description |
|-------------------|-------------|
| `run_pipeline(config_path, output_dir, dry_run)` | Orchestrates full pipeline execution |
| `apply_transform(df, step)` | Applies one transform step to DataFrame |
| `process_file(input_path)` | Processes a single input file through all steps |
| `process_directory(input_dir, config)` | Processes all CSV files in directory |
| `validate_transports(available_transports)` | Validate that all referenced transforms exist |

**Dry-Run Implementation:**
- In dry_run mode, output directory path will be logged as output
- No files will actually be created
- A list of hypothetical operations is returned for review

**Logging Implementation:**
- Use `logging` module with `logging.config.fileConfig`
- Default log file: `logs/pipeline.log`
- Console handler at configured level
- File handler at DEBUG level

---

### 4.4 `test_pipeline.py` - Testing Suite

**Purpose:** Unit tests for each component.

**Test Modules Organized:**
| Test Class | Files to test | Description |
|------------|---------------|-------------|
| `TestConfigLoad` | `config.py` | Test loading and validation of config |
| `TestDropEmptyRows` | `transforms.py` | Test drop_empty_rows function |
| `TestRenameColumns` | `transforms.py` | Test rename_columns function |
| `TestFilterRows` | `transforms.py` | Test filter_rows function |
| `TestAddColumn` | `transforms.py` | Test add_column function |
| `TestPipelineRun` | `pipeline.py` | Test running full pipeline |
| `TestDryRunPipeline` | `pipeline.py` | Test dry_run mode |

**Test Cases for Dry-Run:**
- Verify output file is not created
- Verify log message says "DRY RUN MODE"
- Verify final result is a dict describing the operations

**Test Coverage Targets:**
| Coverage Type | Percentage Target |
|---------------|-------------------|
| Line Coverage | 90% |
| Function Coverage | 100% |
| Branch Coverage | 80% |

**Assumptions:**
- Use `pytest` framework
- Use `pandas.testing` for DataFrame comparison
- Create test subdirectory for fixtures and data: `tests/`

---

## 5. Error Handling Strategy

| Exception Type | Condition | Behavior |
|--------------|----------------|-------------------|
| `FileNotFoundError` | Input/output dir missing | Log error, raise exception if not dry_run |
| `ValueError` | Invalid column name, invalid transform config | Log error, stop execution on final transform |
| `TypeError` | Invalid DataFrame passed to transform | Log error, stop execution |
| `PipelineError` | Custom exception for pipeline failures | Include all affected step errors in message |

**Assumptions:**
- Errors in one step should stop pipeline unless marked optional
- Optional steps will be marked with `required: false` in config
- Default behavior is to fail fast unless specified otherwise

---

## 6. Execution Flow Plan

### Phase 1: Setup (Pre-Execution)

```
1. Read pipeline.yaml (config.py.load_config())
2. Validate configuration (config.py.validate_config())
3. Create output directory if not exists
4. Set up logging to console and file
5. Validate input directory exists
6. Scan input directory for CSV files
```

### Phase 2: Execution (Normal Mode)

```
7. For each CSV file in input_dir:
   a. Read file (pandas.read_csv())
   b. For each step in steps list:
      - Log step execution (INFO level)
      - Apply transform to DataFrame
      - If error: log error, mark step as failed, raise exception
   c. Write processed file to output_dir
   d. Log success with row count info
8. Log summary of all files processed
```

### Phase 3: Execution (Dry-Run Mode)

```
7. For each CSV file in input_dir:
   a. Read file (pandas.read_csv()) for validation
   b. For each step in steps list:
      - Log step execution
      - Describe hypothetical transform result
      - Do not apply to DataFrame
   c. Collect hypothetical changes
8. Return summary of hypothetical operations
9. Exit without creating output files
```

### Phase 4: Completion

```
10. Generate summary log (total rows read/written)
11. Generate summary report (if --report flag)
12. Exit with appropriate return code (0 for success, 1 for failure)
```

---

## 7. Logging Design

### Log Formats:

```python
# Console format
format = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

# File format (more detailed)
log_format = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
log_date_format = "%Y-%m-%d %H:%M:%S"
```

### Log Levels to Use:
- `DEBUG`: Detailed operational info (column counts, memory usage)
- `INFO`: Normal pipeline progress
- `WARNING`: Non-critical issues (optional transforms skipped)
- `ERROR`: Errors in specific transforms
- `CRITICAL`: Pipeline halting errors

### Log Location:
- `logs/pipeline.log` for file logs
- Console output (no file)
- Log rotation: Max 5 files, 10MB each (optional, can be implemented)

---

## 8. Deliverable Checklist

| Deliverable | Status | Notes |
|-------------|--------|-------|
| `pipeline.py` | Plan Ready | Main orchestrator |
| `transforms.py` | Plan Ready | Transform functions |
| `pipeline.yaml` | Plan Ready | Configuration example |
| `test_pipeline.py` | Plan Ready | Test suite |
| Documentation | Plan Ready | README.md |
| Error handling | Plan Ready | Exception handling |
| Logging setup | Plan Ready | File and console |

---

## 9. Development Order

### Step 1: Infrastructure (Days 1-2)
- Create directory structure
- Implement `config.py`
- Implement basic logging setup

### Step 2: Transform Library (Days 3-5)
- Implement basic transform functions
- Implement common transforms first (filter, rename, add)
- Test each transform individually

### Step 3: Orchestrator (Days 6-7)
- Implement `run_pipeline()` function
- Implement `apply_transform()` function
- Implement dry-run logic
- Implement error handling

### Step 4: Configuration & Examples (Day 8)
- Create sample `pipeline.yaml`
- Create sample input test data
- Verify with example pipeline

### Step 5: Testing (Days 9-11)
- Implement unit tests for each transform
- Implement pipeline tests
- Test dry-run functionality
- Performance testing with large data

### Step 6: Documentation & Cleanup (Day 12)
- Write README.md
- Add docstrings to all functions
- Create usage examples
- Review and update code comments

---

## 10. Acceptance Criteria

| Criteria | Implementation |
|----------|----------------|
| Reads CSV from input dir | Yes |
| Applies transforms from config | Yes |
| Supports chaining | Yes |
| Dry-run mode works | Yes |
| Logging works | Yes |
| Uses pandas | Yes |

---

## 11. Notes for Review

1. **Transform Function Signatures**: All transforms will follow `transform(df, **kwargs)` pattern for extensibility.

2. **Config Field Names**: Follow snake_case for Python compatibility (e.g., `input_dir` not `inputDir`).

3. **Error Behavior**: By default, pipeline is not idempotent - will not reprocess if output exists. Add `overwrite: true/false` flag.

4. **Performance**: For large files, consider `dtype_mapping` to control memory usage upfront in config.

---

## 12. Next Steps (After Planning Complete)

1. Begin implementing `config.py` first as the foundation
2. Implement simple transforms first for testing
3. Test pipeline with sample data before moving to complex transforms
4. Write comprehensive error handling before moving on
5. Ensure dry-run mode is implemented before final tests
6. Review and refine after initial implementation

---

*Plan complete. Ready for execution upon approval.*

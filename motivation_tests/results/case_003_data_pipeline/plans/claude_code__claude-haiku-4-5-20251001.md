---
case: case_003_data_pipeline
framework: claude_code
model: claude-haiku-4-5-20251001
provider: anthropic
session_id: b91ebcd4-3b33-47ba-b5ad-6c330c4dd169
duration_ms: 66143
duration_wall_s: 70.8
cost_usd: 0.09601205000000002
num_turns: 8
timestamp: 2026-03-18T00:53:56.837695+00:00
error: None
---

# Plan

# CSV Data Pipeline Implementation Plan

## Context

We need to design a configurable data processing pipeline that reads CSV files, applies a series of transformations defined in a YAML configuration, and writes results to an output directory. The system should support:
- Multiple chained transformations (filter, rename, derive)
- Dry-run mode for previewing changes without writing
- Configurable logging with multiple verbosity levels
- pandas-based data manipulation

## Architecture Overview

The pipeline uses a **YAML-driven, modular transform system**:

1. **Pipeline Configuration (YAML)** — Defines transformation steps in order
2. **Transform Registry** — Maps step types to callable functions/classes
3. **Pipeline Orchestrator** — Reads config, applies transforms sequentially, handles I/O
4. **Logging & Dry-Run** — Configurable verbosity and preview mode without file writes

## Implementation Components

### 1. `transforms.py` — Transform Functions & Classes
**Purpose**: Individual, reusable data transformation operations

**Key Transforms to Implement**:
- `FilterRows` — Filter rows based on conditions (e.g., column > threshold)
- `RenameColumns` — Rename columns based on mapping
- `ComputeDerived` — Create new columns from expressions (e.g., column_c = column_a + column_b)
- Base `Transform` class for inheritance (optional, for consistency)

**Design**:
- Each transform should be a callable class or function
- Take dataframe as input, return modified dataframe
- Accept configuration dict with parameters
- Include docstrings describing inputs, outputs, and parameter schema

**Example Structure**:
```
class FilterRows:
    def __init__(self, config):
        self.column = config.get('column')
        self.operator = config.get('operator')  # '>', '<', '==', etc.
        self.value = config.get('value')

    def __call__(self, df):
        # Apply filter and return df
```

### 2. `pipeline.py` — Pipeline Orchestrator
**Purpose**: Main orchestrator that reads config, manages execution, handles I/O

**Key Components**:

#### PipelineConfig Class
- Reads YAML configuration file
- Validates schema (input_dir, output_dir, steps, dry_run, logging config)
- Provides easy access to settings

#### Pipeline Class
- Takes PipelineConfig as input
- `execute()` method:
  - Reads all CSV files from input directory
  - Applies transforms in sequence
  - Writes results to output directory (or skips if dry_run=true)
  - Logs progress at each step
- `dry_run()` method:
  - Simulates pipeline execution
  - Prints what would be written (sample rows, row counts, changes)
  - Does NOT write to output directory
- Error handling (missing files, invalid transforms, data issues)

#### Key Methods
- `_load_csvs(input_dir)` — Load all CSVs from directory
- `_apply_transforms(df, steps)` — Apply transforms in order
- `_get_transform_function(step_type)` — Instantiate or lookup transform
- `_write_output(df, output_dir, filename)` — Write to output directory

#### Logging Strategy
- Use Python's `logging` module
- Configurable levels: DEBUG, INFO, WARNING, ERROR
- Log each transform applied with row count before/after
- Log dry-run previews to console

### 3. `pipeline.yaml` — Example Configuration
**Purpose**: Define a sample pipeline configuration

**Schema**:
```yaml
input_dir: ./input_data
output_dir: ./output_data
dry_run: false
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

steps:
  - type: filter_rows
    config:
      column: age
      operator: ">"
      value: 18

  - type: rename_columns
    config:
      mapping:
        old_name: new_name
        first_name: firstname

  - type: compute_derived
    config:
      column_name: full_name
      expression: "first_name + ' ' + last_name"
```

**Validation**:
- All required fields present
- input_dir and output_dir are valid paths or create-able
- All step types are registered/available
- step configs match expected schema for their type

### 4. `test_pipeline.py` — Unit & Integration Tests
**Purpose**: Comprehensive test coverage

**Test Categories**:

#### Transform Tests
- **FilterRows**: Test various operators (>, <, ==, !=, in, not in)
- **RenameColumns**: Test single/multiple renames, missing columns, duplicates
- **ComputeDerived**: Test simple expressions, complex formulas, error handling

#### Pipeline Tests
- **Config Loading**: Valid YAML, missing fields, invalid schema
- **CSV Reading**: Multiple files, missing files, empty files, encoding issues
- **Transform Chaining**: Verify transforms apply in correct order
- **Dry-Run Mode**: Verify no files written, preview is accurate
- **Output Writing**: Verify files written correctly, data integrity
- **Logging**: Verify log messages contain expected info

#### Integration Tests
- End-to-end pipeline: input CSV → transforms → output CSV
- Multi-file processing
- Error scenarios (missing columns, type mismatches)

**Test Data**:
- Create minimal fixtures (small sample DataFrames)
- Example: 10-row CSV with columns: id, age, name, salary
- Test both happy path and error conditions

## Critical Files to Modify/Create

| File | Purpose | Type |
|------|---------|------|
| `transforms.py` | Transform function implementations | New |
| `pipeline.py` | Main orchestrator | New |
| `pipeline.yaml` | Example configuration | New |
| `test_pipeline.py` | Unit & integration tests | New |

## Verification Plan

**Manual Testing**:
1. Create sample CSV files in `WorkingDir/input_data/`
2. Create `pipeline.yaml` with example transforms
3. Run `python pipeline.py pipeline.yaml` and verify output
4. Run with `dry_run: true` and verify no output files created
5. Verify logging output at different levels (DEBUG, INFO, WARNING)

**Automated Testing**:
1. Run `pytest test_pipeline.py -v`
2. Verify all tests pass (unit transforms + integration)
3. Check code coverage with `pytest --cov=. test_pipeline.py`

**Edge Cases to Test**:
- Empty CSV files
- CSV with missing columns referenced in transforms
- Invalid YAML syntax
- Non-existent input directory
- Read-only output directory
- Unicode/special characters in data

## Technical Decisions

1. **YAML over JSON**: Human-readable, easy to edit, comment-friendly
2. **Function-based Transforms**: Lightweight, no complex class hierarchies
3. **pandas**: Efficient for tabular data, rich API for filtering/computing
4. **Logging**: Python's built-in logging module for production-grade control
5. **Dry-Run Implementation**: Simulates without writing; preview shows sample output
6. **Error Handling**: Fail fast with clear error messages; don't corrupt input data

## Dependencies

- `pandas` — Data manipulation
- `pyyaml` — YAML parsing
- `pytest` — Testing framework (optional, for test_pipeline.py)
- Python 3.8+

## Next Steps (Post-Planning)

1. Implement `transforms.py` with FilterRows, RenameColumns, ComputeDerived
2. Implement `pipeline.py` with Pipeline and PipelineConfig classes
3. Create `pipeline.yaml` example configuration
4. Implement `test_pipeline.py` with comprehensive test suite
5. Manual testing with sample data
6. Documentation/docstrings for all public APIs


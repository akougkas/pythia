---
case: case_003_data_pipeline
framework: claude_code
model: claude-haiku-4-5-20251001
provider: anthropic
session_id: c3d16e11-26ad-425a-a63a-d0c574e5816a
duration_ms: 34196
duration_wall_s: 36.0
cost_usd: 0.0335062
num_turns: 6
timestamp: 2026-03-19T14:13:21.676722+00:00
error: None
---

# Plan

# CSV Data Pipeline Implementation Plan

## Context

The objective is to create a flexible, configurable data pipeline that:
- Reads CSV files from an input directory
- Applies a series of transformations defined in a YAML configuration
- Writes processed results to an output directory
- Supports dry-run mode for preview without persistence
- Provides configurable logging for visibility into pipeline operations

This will enable users to define data processing workflows declaratively without writing custom code for each transformation.

## Architecture Overview

The pipeline will consist of:
1. **pipeline.py** — Main orchestrator that reads config, loads data, applies transforms in sequence, handles dry-run mode
2. **transforms.py** — Library of reusable transformation functions (filter, rename, derive columns, etc.)
3. **pipeline.yaml** — Example configuration file demonstrating transform syntax
4. **test_pipeline.py** — Unit tests covering core functionality

## Implementation Plan

### Phase 1: Core Pipeline Infrastructure (`pipeline.py`)

**Responsibilities:**
- Load pipeline configuration from YAML
- Read CSV files from input directory using pandas
- Execute transform chain sequentially
- Write output to output directory (or skip in dry-run mode)
- Provide structured logging at configurable verbosity levels

**Key Components:**
1. **Configuration Loader**
   - Parse YAML file
   - Validate transform definitions
   - Extract input/output directories, file patterns

2. **Data Pipeline Class**
   - `__init__(config_path, input_dir, output_dir, dry_run=False, verbosity='INFO')`
   - `load_data(file_pattern='*.csv')` — loads all matching CSVs
   - `apply_transforms(dataframe, transforms_list)` — applies transforms in order
   - `run()` — orchestrates full pipeline execution
   - `_log()` — handles logging with verbosity control

3. **Transform Executor**
   - Registry pattern to map transform names to functions
   - Dynamic function lookup and calling with parameters
   - Error handling with informative messages

**Assumptions:**
- All CSV files in input directory should be processed independently
- Multiple CSV files are processed and results written separately
- Transform execution order matters (sequence defined in YAML)

---

### Phase 2: Transform Library (`transforms.py`)

**Responsibilities:**
- Implement individual transformation functions
- Each function accepts a DataFrame and transform-specific parameters
- Return modified DataFrame

**Core Transforms:**
1. **filter_rows**
   - Parameters: column, operator (==, >, <, >=, <=, !=, in), value
   - Returns: filtered DataFrame
   - Example: Filter rows where age >= 18

2. **rename_columns**
   - Parameters: mapping dict {old_name: new_name}
   - Returns: DataFrame with renamed columns

3. **select_columns**
   - Parameters: list of column names to keep
   - Returns: DataFrame with only selected columns

4. **drop_columns**
   - Parameters: list of column names to remove
   - Returns: DataFrame without specified columns

5. **derive_column**
   - Parameters: column_name, expression (string), source_columns
   - Uses pandas eval() to compute new column
   - Returns: DataFrame with new derived column

6. **drop_duplicates**
   - Parameters: subset (optional column list), keep ('first'|'last')
   - Returns: deduplicated DataFrame

7. **fill_missing**
   - Parameters: column, method ('forward'|'backward'|'mean'|'median'|value)
   - Returns: DataFrame with filled values

8. **sort_rows**
   - Parameters: by (column or list), ascending (bool)
   - Returns: sorted DataFrame

9. **sample_rows**
   - Parameters: n (number of rows) or frac (fraction), random_state
   - Returns: sampled DataFrame

**Extensibility:**
- Simple function signature: `transform_func(df: pd.DataFrame, **params) -> pd.DataFrame`
- New transforms can be added by defining new functions following this pattern
- Registry mechanism in pipeline.py maps transform names to functions

---

### Phase 3: Configuration Format (`pipeline.yaml`)

**Structure:**
```yaml
pipeline:
  input_directory: "./input_data"
  output_directory: "./output_data"
  file_pattern: "*.csv"

transforms:
  - name: filter_rows
    params:
      column: "age"
      operator: ">="
      value: 18

  - name: select_columns
    params:
      columns: ["id", "name", "email", "age"]

  - name: rename_columns
    params:
      mapping:
        "email": "contact_email"
        "age": "years_old"

  - name: derive_column
    params:
      column_name: "is_adult"
      expression: "years_old >= 18"

  - name: drop_duplicates
    params:
      subset: ["id"]
      keep: "first"

logging:
  verbosity: "INFO"  # DEBUG, INFO, WARNING, ERROR
  log_file: "./pipeline.log"
```

---

### Phase 4: Testing (`test_pipeline.py`)

**Test Coverage:**

1. **Configuration Tests**
   - Valid YAML parsing
   - Invalid configuration detection
   - Missing required fields handling

2. **Transform Tests**
   - Each transform applies correctly
   - Parameter validation
   - Edge cases (empty DataFrames, missing columns, etc.)

3. **Pipeline Integration Tests**
   - End-to-end pipeline execution
   - Dry-run mode produces no output files
   - Normal mode produces expected output
   - Multiple CSV files processed correctly
   - Transform chaining works in correct order

4. **Logging Tests**
   - Verbosity levels respected
   - Log file written when specified
   - Error messages informative

---

## Critical Files to Create

1. `/home/jye/publications/cases/case_003_data_pipeline/pipeline.py` (300-400 lines)
2. `/home/jye/publications/cases/case_003_data_pipeline/transforms.py` (200-300 lines)
3. `/home/jye/publications/cases/case_003_data_pipeline/pipeline.yaml` (40-60 lines)
4. `/home/jye/publications/cases/case_003_data_pipeline/test_pipeline.py` (400-500 lines)

## Key Design Decisions

1. **YAML Configuration**: Declarative approach makes pipeline definitions readable and shareable
2. **Function Registry**: Dynamic lookup of transforms allows easy extensibility without code changes
3. **Dry-Run Mode**: Separates execution planning from persistence, enables preview before commit
4. **Logging Verbosity**: DEBUG, INFO, WARNING, ERROR levels support various use cases
5. **Sequential Transform Chain**: Simple, predictable execution model; order defined in config
6. **Per-File Processing**: Each CSV processed independently for clarity and error isolation

## Assumptions

1. Input CSV files are well-formed (though missing values allowed)
2. Transform parameters are validated at runtime with clear error messages
3. Column names in transform definitions must match the actual DataFrame columns
4. Derived columns use pandas eval() syntax for expressions
5. All CSV files in input directory matching the pattern should be processed
6. Output files use same naming as input files but in output directory

## Verification Strategy

1. **Unit Tests**: Run test_pipeline.py to verify individual components
2. **Integration Test**: Create sample input CSV, define pipeline.yaml, run pipeline in dry-run mode
3. **End-to-End Test**: Run pipeline in normal mode, verify output files match expectations
4. **Error Handling**: Test invalid configs, missing columns, bad transform parameters

## Implementation Order

1. Define transform functions in transforms.py
2. Implement pipeline.py with config loading and orchestration
3. Create example pipeline.yaml with representative transforms
4. Write comprehensive test suite
5. Verify with sample data in WorkingDir/


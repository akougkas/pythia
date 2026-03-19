---
case: case_003_data_pipeline
framework: claude_code
model: qwen3.5:4b
provider: ollama
session_id: 66971f35-2d4a-4d0c-ace6-127f819455b1
duration_ms: 42785
duration_wall_s: 44.5
cost_usd: 0.664845
num_turns: 4
timestamp: 2026-03-19T14:15:42.323915+00:00
error: None
---

# Plan

# Case 003: CSV Data Pipeline Implementation Plan

## Context
This case requires building a configurable data pipeline that reads CSV files, applies transformations defined in a YAML configuration, and writes results to an output directory. The WorkingDir is empty, so this is a fresh implementation.

## Materials Needed
- Sample CSV files (to be provided)
- Reference pipeline.yaml (to be provided)
- Python environment with pandas installed

## Recommended Approach

### 1. Project Structure
```
case_003_data_pipeline/
├── WorkingDir/
│   ├── input/
│   │   └── sample_data.csv
│   ├── output/
│   ├── pipeline.py          # Main orchestrator
│   ├── transforms.py        # Individual transform functions
│   ├── pipeline.yaml        # Example pipeline config
│   └── test_pipeline.py     # Unit tests
└── requirements.txt
```

### 2. Core Design Decisions

#### Transform Functions (transforms.py)
Implement these transform functions:
- `load_csv()` - Read CSV files with pandas
- `filter_rows()` - Filter rows based on conditions
- `rename_columns()` - Rename columns by mapping
- `add_derived_column()` - Compute derived columns
- `select_columns()` - Select specific columns
- `drop_duplicates()` - Remove duplicate rows
- `aggregate()` - Perform aggregations
- `sort()` - Sort data by columns
- `export_csv()` - Write output to CSV

#### Pipeline Orchestrator (pipeline.py)
- Parse pipeline.yaml configuration
- Build a list of transform steps
- Support dry-run mode (verbose, no write)
- Handle errors gracefully with retry logic
- Log progress with configurable verbosity

#### Pipeline Configuration (pipeline.yaml)
```yaml
pipeline:
  name: "sample_pipeline"
  dry_run: false
  verbosity: "INFO"

input:
  directory: "input"
  extensions: [".csv"]
  file_pattern: ".*\.csv"

output:
  directory: "output"
  file_pattern: "processed_{original_name}"

steps:
  - type: "load"
    name: "load_data"
  - type: "filter"
    name: "filter_invalid"
    condition: "${column_a} >= 0 AND ${column_b} > 0"
  - type: "rename"
    name: "rename_columns"
    mapping:
      column_a: "revenue"
      column_b: "quantity"
  - type: "derive"
    name: "add_total"
    expression: "${revenue} * ${quantity}"
  - type: "export"
    name: "export_result"
```

### 3. Transformation Functions Specification

| Function | Description | Parameters |
|----------|-------------|------------|
| load_csv | Read CSV from directory | input_dir, file_pattern, extensions, columns |
| filter_rows | Filter rows by condition | dataframe, condition |
| rename_columns | Rename columns by mapping | dataframe, mapping |
| add_derived | Compute new column from existing | dataframe, column, expression |
| select_columns | Select specific columns | dataframe, columns |
| drop_duplicates | Remove duplicate rows | dataframe, subset |
| aggregate | Aggregate data by group | dataframe, by, aggregation, axis |
| sort | Sort dataframe by columns | dataframe, columns, ascending |
| export_csv | Write dataframe to CSV | dataframe, output_dir, file_pattern |

### 4. Pipeline Configuration Format
- `pipeline.name`: Pipeline identifier
- `pipeline.dry_run`: Boolean, if true don't write output
- `pipeline.verbosity`: Logging level (DEBUG/INFO/WARNING/ERROR)
- `input.directory`: Input directory path
- `input.file_pattern`: Glob pattern for file matching
- `output.directory`: Output directory path
- `output.file_pattern`: Glob pattern for output files
- `steps[]`: List of transform steps with `type`, `name`, and type-specific config

### 5. Error Handling
- Catch exceptions during transform execution
- Log with appropriate verbosity level
- Support retry for transient failures
- Provide detailed error messages for debugging

### 6. Testing Strategy (test_pipeline.py)
- Test each transform function individually
- Test pipeline orchestration with various configurations
- Test dry-run mode
- Test error handling
- Test with sample CSV data

## Implementation Phases

### Phase 1: Core Transform Functions
1. Create `transforms.py` with individual transform functions
2. Implement `load_csv()` with pandas
3. Implement `filter_rows()`, `rename_columns()`, `add_derived_column()`
4. Implement `select_columns()`, `drop_duplicates()`, `aggregate()`, `sort()`
5. Implement `export_csv()`
6. Add docstrings and type hints to all functions

### Phase 2: Pipeline Orchestrator
1. Create `pipeline.py` with main orchestrator class
2. Implement YAML configuration parsing
3. Build step chaining logic
4. Add dry-run mode support
5. Add logging with configurable verbosity
6. Add error handling and retry logic

### Phase 3: Configuration & Testing
1. Create sample `pipeline.yaml` configuration
2. Create sample input CSV file
3. Write `test_pipeline.py` with unit tests
4. Test end-to-end pipeline execution
5. Validate dry-run mode output

## Dependencies
- pandas >= 1.5.0
- pyyaml >= 6.0

## Verification Steps
1. Run `python -m unittest test_pipeline` to run all tests
2. Run `python pipeline.py --dry-run` to test dry-run mode
3. Run `python pipeline.py --write` to test full pipeline execution
4. Verify output CSVs are created in output directory
5. Verify transformation results match expected values

## Critical Files to Modify
1. `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/transforms.py`
2. `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/pipeline.py`
3. `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/pipeline.yaml`
4. `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/test_pipeline.py`

## Reusable Patterns Found
- pandas DataFrame operations for data manipulation
- YAML configuration for pipeline definition
- Command-line argument parsing for mode selection

## Next Steps
1. Create `transforms.py` with all transform functions
2. Create `pipeline.py` orchestrator
3. Create `pipeline.yaml` sample configuration
4. Create sample input CSV file
5. Write and run unit tests
6. Test full pipeline execution including dry-run mode


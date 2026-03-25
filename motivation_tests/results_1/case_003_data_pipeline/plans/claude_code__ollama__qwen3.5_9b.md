---
case: case_003_data_pipeline
framework: claude_code
model: qwen3.5:9b
provider: ollama
session_id: 2b4b097b-020b-45a0-9929-b76b45dc1802
duration_ms: 60037
duration_wall_s: 62.5
cost_usd: 0.8579199999999999
num_turns: 5
timestamp: 2026-03-19T14:13:56.897137+00:00
error: None
---

# Plan

# CSV Data Pipeline Implementation Plan

## Context

This plan addresses the requirement to design a configurable CSV data pipeline that reads input CSV files, applies chainable transformations, and writes results to an output directory. The pipeline must use pandas for data manipulation, support transformations defined in `pipeline.yaml`, include dry-run mode, and feature configurable logging. Since no sample materials exist, this plan defines the complete system from scratch.

## Design Rationale

The pipeline uses a functional pipeline architecture where each transformation is an independent function that returns a transformed DataFrame. This approach:
- Enables easy chaining of arbitrary transforms
- Allows selective composition of transformations
- Supports dry-run mode without side effects
- Facilitates unit testing of individual transforms

## Phase 1: Core Transform Functions (`transforms.py`)

### 1.1 Filter Rows Transform
- **Function**: `filter_rows(df: pd.DataFrame, condition: str, *args) -> pd.DataFrame`
- **Purpose**: Filter rows based on a pandas-style condition string (e.g., `"age > 25"`, `"status == 'active'"`)
- **Implementation**: Uses `eval()` with controlled variable injection for safety
- **Input**: DataFrame, condition string, and optional argument values
- **Output**: Filtered DataFrame

### 1.2 Rename Columns Transform
- **Function**: `rename_columns(df: pd.DataFrame, mapping: dict) -> pd.DataFrame`
- **Purpose**: Rename columns using a dictionary mapping old names to new names
- **Implementation**: Uses pandas `rename()` with the mapping dictionary
- **Input**: DataFrame, column name mapping dictionary
- **Output**: DataFrame with renamed columns

### 1.3 Add Derived Column Transform
- **Function**: `add_derived_column(df: pd.DataFrame, name: str, expression: str, *args) -> pd.DataFrame`
- **Purpose**: Add a new column computed from existing columns via expression string
- **Implementation**: Uses `pandas.eval()` or lambda-based computation
- **Input**: DataFrame, column name, expression string (e.g., `"price * quantity"`), optional values
- **Output**: DataFrame with new derived column

### 1.4 Select Columns Transform
- **Function**: `select_columns(df: pd.DataFrame, column_names: list) -> pd.DataFrame`
- **Purpose**: Select specific columns to include in output
- **Implementation**: Uses pandas `df[column_names]` indexing
- **Input**: DataFrame, list of column names to select
- **Output**: DataFrame with only selected columns

### 1.5 Drop Columns Transform
- **Function**: `drop_columns(df: pd.DataFrame, column_names: list) -> pd.DataFrame`
- **Purpose**: Remove specified columns
- **Implementation**: Uses pandas `df.drop()` with column names
- **Input**: DataFrame, list of column names to drop
- **Output**: DataFrame without specified columns

### 1.6 Sort Values Transform
- **Function**: `sort_values(df: pd.DataFrame, by: list, ascending: bool = True) -> pd.DataFrame`
- **Purpose**: Sort DataFrame by specified column(s)
- **Implementation**: Uses pandas `sort_values()`
- **Input**: DataFrame, column name(s) to sort by, ascending flag
- **Output**: Sorted DataFrame

### 1.7 Transform Column Values Transform
- **Function**: `transform_column(df: pd.DataFrame, column: str, func_name: str, *args) -> pd.DataFrame`
- **Purpose**: Apply a function to transform values in a single column
- **Implementation**: Uses getattr() to dynamically call numpy/pandas functions
- **Input**: DataFrame, column name, function name (e.g., `"upper"`, `"str"`, `"round"`), optional args
- **Output**: DataFrame with transformed column values

## Phase 2: Main Orchestrator (`pipeline.py`)

### 2.1 YAML Configuration Loading
- **Function**: `load_config(config_path: str) -> dict`
- **Purpose**: Parse and load pipeline configuration from YAML file
- **Implementation**: Uses `pyyaml` to parse YAML, validates structure
- **Returns**: Dictionary with pipeline settings, transforms list, and output config

### 2.2 Pipeline Execution Engine
- **Class**: `CSVDataPipeline`
- **Constructor**: `__init__(config_path: str, input_dir: str, output_dir: str, logging_level: str = "INFO", dry_run: bool = False)`
  - Loads configuration
  - Initializes transform registry
  - Sets up logging configuration
  - Creates input/output directories if they don't exist (except in dry-run)

### 2.3 Dry-Run Mode
- **Implementation**: When `dry_run=True`, execute all transforms in memory, print what would happen via logging, but skip all file I/O operations
- **Purpose**: Preview pipeline effects without modifying filesystem

### 2.4 Transform Chaining
- **Method**: `_chain_transforms(df: pd.DataFrame, transforms: list) -> pd.DataFrame`
- **Purpose**: Sequentially apply a list of transforms to a DataFrame
- **Implementation**: Iterate through transforms, validate each, apply and chain result

### 2.5 File Processing
- **Method**: `process_file(input_path: str, output_path: str) -> bool`
- **Purpose**: Read a CSV file, apply transforms, write output (or log in dry-run)
- **Implementation**: Reads CSV with pandas, chains transforms, writes to CSV

### 2.6 Main Processing Loop
- **Method**: `run() -> dict`
- **Purpose**: Process all CSV files in input directory
- **Implementation**:
  1. Discover all `.csv` files in input directory
  2. For each file:
     - Build output path (preserve filename or use mapping from config)
     - Process file and collect results
  3. Return processing summary

### 2.7 Logging System
- **Implementation**: Uses Python's `logging` module with configurable level
- **Levels**: DEBUG, INFO, WARNING, ERROR
- **Features**: Timestamped messages, severity-appropriate formatting
- **Configuration**: Parse log level from config (e.g., "DEBUG", "INFO", "WARNING")

## Phase 3: Configuration (`pipeline.yaml`)

### Structure:
```yaml
# Input/Output Configuration
input_dir: "./input"
output_dir: "./output"
dry_run: false  # Enable preview mode

# Logging Configuration
logging:
  level: "INFO"  # Options: DEBUG, INFO, WARNING, ERROR
  format: "%(asctime)s - %(levelname)s - %(message)s"

# File Processing
files:
  glob_pattern: "*.csv"  # Pattern to match input files
  # Optional: custom output naming rules
  output_naming:
    use_original: true  # Keep original filename or transform

# Transforms - Chain of operations applied to each file
transforms:
  - name: "filter_active"
    type: "filter_rows"
    condition: "status == 'active'"

  - name: "select_columns"
    type: "select_columns"
    columns:
      - "name"
      - "email"
      - "age"

  - name: "add_discount"
    type: "add_derived_column"
    name: "discounted_price"
    expression: "price * (1 - discount_rate)"
    args:
      discount_rate: 0.1

# Output options
output:
  force_overwrite: false  # Overwrite existing files
  add_timestamp: false   # Append timestamp to output filename
```

## Phase 4: Testing (`test_pipeline.py`)

### 4.1 Transform Unit Tests
- **Setup**: Create sample CSV files with known data structure
- **Tests for filter_rows**:
  - Correctly filters rows matching condition
  - Handles invalid condition strings
  - Returns empty DataFrame when no rows match

- **Tests for rename_columns**:
  - Renames columns correctly
  - Ignores non-existent columns gracefully
  - Preserves column order

- **Tests for add_derived_column**:
  - Correctly computes expression
  - Handles edge cases (null values, division by zero)

- **Tests for select_columns**:
  - Selects correct columns
  - Raises error on non-existent column

- **Tests for drop_columns**:
  - Drops correct columns
  - Ignores non-existent columns

- **Tests for sort_values**:
  - Sorts ascending correctly
  - Sorts descending correctly
  - Multi-column sorting

- **Tests for transform_column**:
  - Applies numpy functions (upper, lower, round)
  - Applies pandas functions

### 4.2 Pipeline Orchestrator Tests
- **Tests for load_config**:
  - Loads valid YAML correctly
  - Raises error on invalid YAML
  - Validates required fields

- **Tests for CSVDataPipeline initialization**:
  - Creates input/output directories
  - Configures logging level correctly
  - Dry-run mode sets flag

- **Tests for file processing**:
  - Processes single file correctly
  - Processes multiple files
  - Handles missing input files gracefully
  - Handles file read/write errors

- **Tests for dry-run mode**:
  - Executes transforms without writing files
  - Logs what would happen
  - Output directory not created if no processing occurs

- **Integration test**:
  - End-to-end pipeline execution
  - Verifies output files match expected results
  - Tests with various combinations of transforms

### 4.3 Test Data Files (for test suite)
- **test_input/*.csv**: Small test datasets
- **expected_output/*.csv**: Expected results for validation

## Phase 5: Usage Examples

### Example 1: Basic Pipeline Execution
```python
from pipeline import CSVDataPipeline

# Create pipeline from config
pipeline = CSVDataPipeline(
    config_path="pipeline.yaml",
    input_dir="./data",
    output_dir="./results",
    logging_level="INFO"
)

# Run the pipeline
summary = pipeline.run()
print(summary)
```

### Example 2: Dry-Run Preview
```python
pipeline = CSVDataPipeline(
    config_path="pipeline.yaml",
    input_dir="./data",
    output_dir="./results",
    dry_run=True  # Preview without writing
)
pipeline.run()
```

### Example 3: Custom Logging
```python
pipeline = CSVDataPipeline(
    config_path="pipeline.yaml",
    input_dir="./data",
    output_dir="./results",
    logging_level="DEBUG"  # Show detailed execution
)
pipeline.run()
```

## Critical Files to Create

| File | Purpose | Location |
|------|---------|----------|
| `transforms.py` | Transform function definitions | `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/transforms.py` |
| `pipeline.py` | Main orchestrator class | `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/pipeline.py` |
| `pipeline.yaml` | Example pipeline configuration | `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/pipeline.yaml` |
| `test_pipeline.py` | Unit and integration tests | `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/test_pipeline.py` |
| `test_data/*.csv` | Sample test data files | `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/test_data/` |
| `test_data/expected/*.csv` | Expected test outputs | `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/test_data/expected/` |

## Dependencies

- `pandas` - Core data manipulation
- `pyyaml` - YAML configuration parsing
- `numpy` - Numerical operations for transforms
- `logging` - Standard library (no installation needed)

## Verification Steps

1. **Install dependencies**: `pip install pandas pyyaml numpy`
2. **Create test data**: Run sample CSV creation scripts
3. **Run unit tests**: `pytest test_pipeline.py -v`
4. **Run pipeline**: Copy test data to input dir, run `python pipeline.py`
5. **Verify outputs**: Check output files match expected results
6. **Dry-run test**: Enable `dry_run: true` in config and verify no files are created

## Assumptions Made

1. Input CSV files should have consistent column types within each file
2. All transforms are applied in order as defined in the transforms list
3. Missing columns in transforms are handled gracefully (skip or error depending on transform)
4. Transform function names are hardcoded strings mapped to actual function names
5. Logging uses Python standard library `logging` module with configurable level
6. No external database connections needed - pure CSV processing


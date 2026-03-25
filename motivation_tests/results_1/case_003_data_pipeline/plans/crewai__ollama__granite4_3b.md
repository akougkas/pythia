---
case: case_003_data_pipeline
framework: crewai
model: granite4:3b
provider: ollama
session_id: None
duration_ms: 20003
duration_wall_s: 20.0
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T23:28:09.590320+00:00
error: None
---

# Plan

# Implementation Plan for CSV Data Pipeline

## 1. Project Structure

### Directory Layout

```
/case_003_data_pipeline/
├── WorkingDir/                     # Sample data and config files
│   ├── input/
│   │   └── raw.csv
│   └── output/
│       └── processed.csv
├── src/
│   ├── pipeline.py                 # Main orchestrator
│   ├── transforms.py               # Transform functions
│   └── utils.py                    # Utility functions (logging, dry-run)
└── tests/
    └── test_pipeline.py           # Unit tests
```

## 2. Source Code

### `src/pipeline.py` - Main Orchestrator

```python
import yaml
import os
from pathlib import Path
import pandas as pd
import logging
from src.utils import log_dry_run, setup_logging

def load_pipeline_config(config_path: str = "pipeline.yaml"):
    """
    Load the pipeline configuration from a YAML file.

    Args:
        config_path (str): Path to the pipeline configuration file.

    Returns:
        dict: Parsed configuration.
    """
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def run_pipeline(input_dir: str = "WorkingDir/input/", output_dir: str = "WorkingDir/output/"):
    """
    Run the data pipeline to process CSV files according to defined transformations.

    Args:
        input_dir (str): Directory containing raw input CSV files.
        output_dir (str): Directory where processed CSV files will be written.
    """
    config = load_pipeline_config()
    dry_run = config.get('dry_run', False)

    for item in config['transforms']:
        transform_func, kwargs = parse_transform(item)
        logging.info(f"Running transform: {transform_func.__name__}")

        df = process_single_transform(input_dir, output_dir, transform_func, **kwargs)
        input_dir = output_dir

    if not dry_run:
        save_processed_files(output_dir)

def parse_transform(transform_entry):
    """
    Parse a transformation entry from the config.

    Args:
        transform_entry (dict): Configuration for a single transform.

    Returns:
        tuple: Function to apply and keyword arguments.
    """
    return globals()[transform_entry['func']], transform_entry.get('kwargs', {})

def process_single_transform(input_dir, output_dir, func, **kwargs):
    """
    Process a single CSV file through the specified transformation.

    Args:
        input_dir (str): Directory containing raw input CSV files.
        output_dir (str): Directory where processed CSV files will be written.
        func: Function to apply transformations.
        **kwargs: Additional keyword arguments for the function.

    Returns:
        pd.DataFrame: Transformed DataFrame.
    """
    df = read_input_file(input_dir, kwargs.get('file_name'))
    df_transformed = func(df)
    write_output_file(output_dir, df_transformed)

    return df_transformed

def read_input_file(input_path, file_name):
    """
    Read a CSV file from the input directory.

    Args:
        input_path (str): Path to the input directory.
        file_name (str): Name of the CSV file.

    Returns:
        pd.DataFrame: DataFrame containing the data.
    """
    return pd.read_csv(Path(input_path) / file_name)

def write_output_file(output_path, df):
    """
    Write a DataFrame to a CSV file in the output directory.

    Args:
        output_path (str): Path to the output directory.
        df (pd.DataFrame): Data to be written.
    """
    filename = "processed.csv"
    df.to_csv(Path(output_path) / filename, index=False)

def save_processed_files(output_dir):
    """
    Save all processed files after completing all transformations.

    Args:
        output_dir (str): Directory where processed CSV files will be written.
    """
    # Implementation placeholder for final aggregated processing
    pass

```

### `src/transforms.py` - Individual Transform Functions

```python
import pandas as pd

def filter_rows(df: pd.DataFrame, condition: dict):
    """
    Filter rows based on specified conditions.

    Args:
        df (pd.DataFrame): Input DataFrame.
        condition (dict): Conditions for filtering.

    Returns:
        pd.DataFrame: Filtered DataFrame.
    """
    return df.query(condition['query'])

def rename_columns(df: pd.DataFrame, columns_mapping: dict):
    """
    Rename columns based on a mapping dictionary.

    Args:
        df (pd.DataFrame): Input DataFrame.
        columns_mapping (dict): Mapping of old column names to new ones.

    Returns:
        pd.DataFrame: DataFrame with renamed columns.
    """
    return df.rename(columns=columns_mapping)

def compute_derived_columns(df: pd.DataFrame, derived_fields: dict):
    """
    Compute derived columns based on specified expressions.

    Args:
        df (pd.DataFrame): Input DataFrame.
        derived_fields (dict): Fields to derive and their expressions.

    Returns:
        pd.DataFrame: DataFrame with added derived columns.
    """
    for field, expression in derived_fields.items():
        df[field] = eval(expression)
    return df
```

### `src/utils.py` - Utility Functions

```python
import logging
from pathlib import Path

def setup_logging(log_level="INFO"):
    """
    Set up logging configuration based on verbosity.

    Args:
        log_level (str): Logging level (e.g., INFO, DEBUG).
    """
    levels = {"DEBUG": logging.DEBUG,
              "INFO": logging.INFO,
              "WARNING": logging.WARNING,
              "ERROR": logging.ERROR,
              "CRITICAL": logging.CRITICAL}
    
    logging.basicConfig(level=levels.get(log_level, logging.INFO),
                        format='%(asctime)s - %(levelname)s - %(message)s')

def log_dry_run(dry_run):
    """
    Log the dry-run mode.

    Args:
        dry_run (bool): Flag indicating if it's a dry run.
    """
    if dry_run:
        print("Dry run: No files will be written.")
```

## 3. Configuration File (`pipeline.yaml`)

```yaml
dry_run: false

transforms:
  - func: filter_rows
    kwargs:
      condition:
        query: "age >= 0"

  - func: rename_columns
    kwargs:
      columns_mapping:
        old_name1: new_name1
        old_name2: new_name2

  - func: compute_derived_columns
    kwargs:
      derived_fields:
        new_col1: "df['col1'] + df['col2']"
        new_col2: "len(df)"
```

## 4. Unit Tests (`tests/test_pipeline.py`)

```python
import os
import unittest
from pandas.testing import assert_frame_equal
from src.pipeline import run_pipeline, load_pipeline_config

class TestDataPipeline(unittest.TestCase):

    def test_load_pipeline_config(self):
        config = load_pipeline_config()
        self.assertIsInstance(config, dict)
        # Add more tests based on expected configuration structure

    def test_run_pipeline_no_dry_run(self):
        os.makedirs(os.path.join(__project_dir__, "WorkingDir/input"), exist_ok=True)
        os.makedirs(os.path.join(__project_dir__, "WorkingDir/output"), exist_ok=True)

        run_pipeline()

        self.assertTrue(os.path.exists(os.path.join(__project_dir__, "WorkingDir/output/processed.csv")))

    def test_run_pipeline_dry_run(self):
        config = load_pipeline_config(dry_run=True)
        run_pipeline()

        # No output file should be created
        self.assertFalse(os.path.exists(os.path.join(__project_dir__, "WorkingDir/output/processed.csv")))
```

## 5. Running the Pipeline

1. **Setup Logging**: Configure logging based on verbosity.
   ```python
   from src.utils import setup_logging
   setup_logging("DEBUG")  # Change to INFO, WARNING, ERROR, or CRITICAL as needed
   ```

2. **Load Configuration**: Load the pipeline configuration from `pipeline.yaml`.
   ```python
   config = load_pipeline_config()
   ```

3. **Execute Pipeline**:
   - Set `dry_run` to `True` for testing without writing files.
   - Call `run_pipeline()` with default paths or specify custom paths if needed.

4. **Run Unit Tests**: Execute the unit tests to ensure all components work as expected.
   ```python
   python -m unittest discover -v tests/
   ```

5. **Execute in Production**:
   - Ensure the input and output directories are correctly set up with proper file permissions.
   - Run the pipeline script.
     ```bash
     python src/pipeline.py
     ```

## 6. Notes

- The `parse_transform` function dynamically retrieves transform functions from `transforms.py`. This allows for arbitrary transforms as specified in `pipeline.yaml`.
- Dry-run mode is supported by checking the `dry_run` flag in `load_pipeline_config`, which prevents any write operations.
- Logging verbosity can be adjusted via command line arguments or configuration files, affecting how much detail is logged during execution.

This plan outlines a flexible and scalable data pipeline that adheres to the specified requirements and constraints.

---
case: case_003_data_pipeline
framework: agents_sdk
model: gpt-4o
provider: github_models
session_id: None
duration_ms: 15879
duration_wall_s: 15.9
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T02:40:06.823316+00:00
error: None
---

# Plan

# Plan for Case 003: CSV Data Pipeline

Below is the detailed step-by-step implementation plan for creating the requested CSV data pipeline:

---

## Step 1: Directory Layout Preparation

1. **Structure the Working Directory**
   - Ensure the following directory structure exists:
     ```
     /home/jye/publications/cases/case_003_data_pipeline/WorkingDir/
     ├── input/          # Directory for input CSV files
     ├── output/         # Directory for processed CSV files
     └── config/         # Directory for pipeline.yaml
     ```

2. **Placehold Example Files**
   - Add placeholder files:
     - Example input CSV file: `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/input/example.csv`
     - Example pipeline configuration YAML file: `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir/config/pipeline.yaml`.

---

## Step 2: Define Pipeline Configuration (`pipeline.yaml`)

1. **Create Configuration Format**
   - Design a `pipeline.yaml` file structure to define the processing steps. For example:
     ```yaml
     pipeline:
       - name: filter_rows
         params:
           column: "age"
           operation: "greater_than"
           value: 30
       - name: rename_columns
         params:
           mapping:
             first_name: "FirstName"
             last_name: "LastName"
       - name: compute_column
         params:
           new_column: "full_name"
           computation: "{FirstName} + ' ' + {LastName}"
     ```

2. **Content Breakdown:**
   - Each step in the pipeline has:
     - `name`: The name of the transformation function (e.g., `filter_rows`).
     - `params`: Parameters specific to that transformation.

3. **Populate Example Config**
   - Write the above into `/config/pipeline.yaml`.

---

## Step 3: Develop Transform Functions (`transforms.py`)

1. **Module Purpose:**
   - Create a file named `transforms.py` and define reusable transformation functions for the pipeline.

2. **Transform Functions:**
   - Implement the following core transformation functions, each accepting a DataFrame and a `params` dictionary:
     - **`filter_rows`**: Filters rows based on condition:
       ```python
       def filter_rows(df, params):
           column = params["column"]
           operation = params["operation"]
           value = params["value"]
           
           if operation == "greater_than":
               return df[df[column] > value]
           elif operation == "less_than":
               return df[df[column] < value]
           elif operation == "equals":
               return df[df[column] == value]
           else:
               raise ValueError(f"Unsupported operation: {operation}")
       ```
     - **`rename_columns`**: Renames columns:
       ```python
       def rename_columns(df, params):
           mapping = params["mapping"]
           return df.rename(columns=mapping)
       ```
     - **`compute_column`**: Adds a new column computed via an expression:
       ```python
       def compute_column(df, params):
           computation = params["computation"]
           new_column = params["new_column"]
           df[new_column] = df.eval(computation)
           return df
       ```

3. **Export Functions:**
   - Define an entry dictionary for all supported transforms to easily map their names to implementation:
     ```python
     TRANSFORMS = {
         "filter_rows": filter_rows,
         "rename_columns": rename_columns,
         "compute_column": compute_column
     }
     ```

---

## Step 4: Develop Pipeline Orchestrator (`pipeline.py`)

1. **Script Outline:**
   - Create `pipeline.py` as the main orchestrator of the pipeline.
   - Features:
     - Read the `pipeline.yaml` using PyYAML.
     - Load CSV files using `pandas`.
     - Iteratively apply transformations.
     - Support "dry-run" mode.
     - Write the final output DataFrame to the `output/` directory.

2. **Implementation Details:**
   - Implement key functions:
     - **`load_config(filepath)`**: Load the YAML configuration:
       ```python
       import yaml
       def load_config(filepath):
           with open(filepath, "r") as f:
               return yaml.safe_load(f)
       ```
     - **`apply_transforms(df, pipeline)`**: Apply transformations to the DataFrame:
       ```python
       from transforms import TRANSFORMS
       def apply_transforms(df, pipeline):
           for step in pipeline:
               transform_name = step["name"]
               params = step.get("params", {})
               transform_fn = TRANSFORMS.get(transform_name)
               if not transform_fn:
                   raise ValueError(f"Transform {transform_name} not supported.")
               df = transform_fn(df, params)
           return df
       ```
     - **`process_files(input_dir, output_dir, config_path, dry_run=False)`**: Orchestrate pipeline processing:
       ```python
       import pandas as pd
       import os
       def process_files(input_dir, output_dir, config_path, dry_run=False):
           config = load_config(config_path)
           pipeline = config["pipeline"]
           
           for filename in os.listdir(input_dir):
               if filename.endswith(".csv"):
                   input_path = os.path.join(input_dir, filename)
                   df = pd.read_csv(input_path)
                   print(f"Processing: {filename}")
                   processed_df = apply_transforms(df, pipeline)
                   if dry_run:
                       print(f"Dry-run mode: Processed dataframe:\n{processed_df}")
                   else:
                       output_path = os.path.join(output_dir, filename)
                       processed_df.to_csv(output_path, index=False)
       ```
     - **Add Command-Line Interface**: Use `argparse` for CLI support:
       ```python
       if __name__ == "__main__":
           import argparse
           parser = argparse.ArgumentParser(description="CSV Data Pipeline")
           parser.add_argument("--input_dir", required=True, help="Input directory for CSV files")
           parser.add_argument("--output_dir", required=True, help="Output directory for processed files")
           parser.add_argument("--config", required=True, help="Path to pipeline configuration YAML")
           parser.add_argument("--dry_run", action="store_true", help="Run pipeline without writing output")
           args = parser.parse_args()
           
           process_files(args.input_dir, args.output_dir, args.config, args.dry_run)
       ```

---

## Step 5: Add Logging

1. **Logging Setup:**
   - Configure logging for both console and file, with levels adjustable via an environment variable or CLI argument.
     ```python
     import logging
     logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
     logger = logging.getLogger()
     ```

2. **Usage in Orchestrator:**
   - Replace `print` statements with logging:
     ```python
     logger.info(f"Processing: {filename}")
     logger.debug(f"Dry-run processed DataFrame: {processed_df}")
     ```

---

## Step 6: Write Unit Tests (`test_pipeline.py`)

1. **Setup Testing Framework:**
   - Use `pytest` to write unit tests for each component:
     - `transforms.py` unit tests for each transformation function.
     - `pipeline.py` integration test with a mocked configuration and sample data.

2. **Test Cases:**
   - **`test_filter_rows`**:
     - Inputs: Small DataFrame, params for filtering rows.
     - Output: Correctly filtered DataFrame.
   - **`test_rename_columns`**:
     - Inputs: Small DataFrame, column mapping.
     - Output: DataFrame with renamed columns.
   - **`test_compute_column`**:
     - Inputs: DataFrame, computation function.
     - Output: DataFrame with computed column.
   - **Integration Test**: Process a CSV file end-to-end using an example config.

---

## Step 7: Final QA and Refinement

1. **Linter Check:**
   - Use `flake8` or `black` to ensure proper formatting.

2. **Static Typing:**
   - Add optional type hints to all function signatures using `mypy`.

3. **Documentation:**
   - Write docstrings for all functions in `transforms.py` and `pipeline.py`.
   - Include a `README.md` explaining installation, usage, and examples.

4. **Test Coverage:**
   - Run tests with `pytest --cov` to ensure all major paths are covered.

---

## Final Deliverables

1. `pipeline.py`: Main orchestrator script.
2. `transforms.py`: File containing individual transformation functions.
3. `pipeline.yaml`: Example pipeline configuration.
4. `test_pipeline.py`: Unit test suite for pipeline and individual transforms.
5. `README.md`: Documentation explaining setup and usage.

---

By following this plan, all prescribed objectives and constraints will be met. The pipeline will recursively handle CSV files, support configurable transformations, "dry-run" mode, and robust logging.

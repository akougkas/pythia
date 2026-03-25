---
case: case_003_data_pipeline
framework: agents_sdk
model: granite4:3b
provider: ollama
session_id: None
duration_ms: 7960
duration_wall_s: 8.0
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T23:09:34.830596+00:00
error: None
---

# Plan

## Implementation Plan

### 1. Project Structure

Create the following directories and files in the project root:

```
/project_root/
│
├── pipeline.py          # Main orchestrator script
├── transforms.py        # Module containing transform functions
├── test_pipeline.py     # Unit tests for the pipeline
└── pipeline.yaml        # Example pipeline configuration
```

### 2. `transforms.py` – Transform Functions

Implement individual transformation functions to be chained together by the orchestrator.

**File:** `project_root/transforms.py`

```python
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def filter_rows(df, **filters):
    """
    Apply row-level filters.
    
    Parameters:
    - df (pd.DataFrame): Input DataFrame
    - **filters: keyword arguments where key is column name and value can be list of values to keep,
      or a function that takes DataFrame and returns boolean Series
    
    Returns:
    pd.DataFrame with filtered rows.
    """
    for col, condition in filters.items():
        if callable(condition):
            df = df[df.eval(condition(df))
        else:
            df = df[df[col].isin(condition) if isinstance(condition, (list, tuple)) else None]
    
    return df

def rename_columns(df, mapping):
    """
    Rename columns using a dictionary.
    
    Parameters:
    - df (pd.DataFrame): Input DataFrame
    - mapping (dict): Mapping of original column names to new names
    
    Returns:
    pd.DataFrame with renamed columns.
    """
    logger.info(f"Renaming columns: {mapping}")
    return df.rename(columns=mapping)

def compute_derived_columns(df, **expressions):
    """
    Compute derived columns from existing ones.
    
    Parameters:
    - df (pd.DataFrame): Input DataFrame
    - **expressions: keyword arguments where key is new column name and value is a pandas Series expression
    
    Returns:
    pd.DataFrame with additional derived columns.
    """
    logger.info(f"Computing derived columns: {list(expressions.keys())}")
    for col, expr in expressions.items():
        df[col] = eval(expr)
    
    return df
```

### 3. `pipeline.py` – Orchestrator

Implement the main orchestrator script that reads input parameters and runs the transformation chain.

**File:** `project_root/pipeline.py`

```python
import yaml
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_config(config_path):
    """Load YAML pipeline configuration."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def run_pipeline(input_dir, output_dir, config_name='pipeline.yaml', dry_run=False, verbose=1):
    """
    Execute the data pipeline.
    
    Parameters:
    - input_dir (str): Path to directory containing CSV files
    - output_dir (str): Path to directory where processed CSVs will be written
    - config_name (str, optional): Name of YAML configuration file in WorkingDir
    - dry_run (bool, optional): If True, shows what would happen without writing files
    - verbose (int, optional): 0-5 for logging level
    
    Returns:
    None
    """
    # Load configurations
    config = load_config(f'WorkingDir/{config_name}')
    
    # Setup logging based on verbosity
    log_levels = {0: 'CRITICAL', 1: 'ERROR', 2: 'WARNING', 
                  3: 'INFO', 4: 'DEBUG', 5: 'NOTARY'}
    logging.basicConfig(level=log_levels[verbose])
    
    logger.info(f"Starting pipeline run with config name: {config_name}")
    
    # Determine files to process
    input_paths = sorted(Path(input_dir).glob('*.csv'))
    
    for path in input_paths:
        read_path = str(path)
        
        # Load CSV
        df_in = pd.read_csv(read_path)
        logger.info(f"Loaded file: {read_path}")
        
        # Process data according to config
        if verbose >= 3:
            print("Applying transformations...")
            
        for step, args in config.get('steps', {}).items():
            if step == 'filter_rows':
                df = filter_rows(df_in, **args)
            elif step == 'rename_columns':
                df, rename_map = rename_columns(df_in.copy(), mapping=args)
                df_in = df
            elif step == 'compute_derived_columns':
                df = compute_derived_columns(df_in, **args)
                df_in = df
        # End of transformations
        
        if verbose >= 3:
            print("Transformations complete.")
            
        # Rename with output extension for dry run check
        out_path = path.with_suffix('.out')
        
        if dry_run:
            logger.info(f"DRY RUN: Would write to {out_path}, skipping actual write")
        else:
            df_in.to_csv(str(out_path), index=False)
            logger.info(f"Wrote processed CSV to: {out_path}")
```

### 4. `pipeline.yaml` – Example Configuration

```yaml
# project_root/WorkingDir/pipeline.yaml
version: "1"

steps:
  - filter_rows:
      age: [30, 40]
      gender: ['Male', 'Female']
    description: "Filter for specific ages and genders"
    
  - rename_columns:
      mapping:
        year: "date"
        region_name: "region"  
      description: "Rename columns to lowercase kebab case"
      
  - compute_derived_columns:
      new_income_category:
          expr: "income >= 50000 ? 'High' : 'Low'"
      age_group:
          expr: "age < 30 ? '<30' : '>=30'"
```

### 5. `test_pipeline.py` – Unit Test

Create unit tests to ensure core functionality of the pipeline works as expected.

**File:** `project_root/test_pipeline.py`

```python
import unittest
from pandas.testing import assert_frame_equal
from transforms import filter_rows, rename_columns, compute_derived_columns
import pandas as pd
import logging

# Configure for test flatness
logging.basicConfig(level=logging.INFO)

class TestDataPipeline(unittest.TestCase):

    def setUp(self):
        self.base_data = pd.DataFrame({
            'name': ['Alice', 'Bob', 'Charlie'],
            'age': [27, 35, 28],
            'income': [45000, 60000, 55000]
        })

    def test_filter_rows(self):
        filtered = filter_rows(self.base_data, age=[30, 40])
        self.assertTrue(filtered.loc[0, 'age'] == 35)

    def test_rename_columns(self):
        renamed = rename_columns(self.base_data.copy(), mapping={'name': 'person'})
        expected = pd.DataFrame({
            'person': ['Alice', 'Bob', 'Charlie'],
            'age': [27, 35, 28],
            'income': [45000, 60000, 55000]
        })
        assert_frame_equal(renamed, expected)

    def test_compute_derived_columns(self):
        computed = compute_derived_columns(self.base_data, new_income_category='High')
        self.assertTrue('new_income_category' in computed.columns)
        self.assertTrue(computed.iloc[0]['new_income_category'] == 'Low')

if __name__ == '__main__':
    unittest.main()
```

### 6. Running the Pipeline

1. **Development Environment Setup**  
   Ensure Python is installed along with `pandas`, `pyyaml`. Set up a virtual environment if needed.

2. **Testing Unit Tests**  
   Run `python -m unittest test_pipeline.py` to ensure all unit tests pass successfully.

3. **Dry-Run the Pipeline**  
   Execute the pipeline script first in dry-run mode:
   ```bash
   python pipeline.py --input-dir /home/jye/publications/cases/case_003_data_pipeline/WorkingDir/test_inputs \
                     --output-dir /home/jye/publications/cases/case_003_data_pipeline/WorkingDir/test_outputs \
                     --dry-run true
   ```

4. **Execute Full Pipeline**  
   After confirming dry-run works:
   ```bash
   python pipeline.py --input-dir /home/jye/publications/cases/case_003_data_pipeline/WorkingDir/test_inputs \
                     --output-dir /home/jye/publications/cases/case_003_data_pipeline/WorkingDir/test_outputs
   ```

### 7. Verification

- **Check Logs** - Ensure logs are produced at the configured verbosity level.
- **Inspect Output Files** - Verify generated CSV files in `output_dir` after running pipeline normally.

---

**Assumptions Made**

1. The YAML config is stored under `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir`.
2. `dry_run` parameter is boolean (`True` or `False`).
3. Logging verbosity maps to standard Python levels (CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTARY).

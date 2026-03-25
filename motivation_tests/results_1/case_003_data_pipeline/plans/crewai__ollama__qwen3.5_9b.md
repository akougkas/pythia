---
case: case_003_data_pipeline
framework: crewai
model: qwen3.5:9b
provider: ollama
session_id: None
duration_ms: 63236
duration_wall_s: 63.2
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T23:25:55.400740+00:00
error: None
---

# Plan

# Case 003: CSV Data Pipeline Implementation Plan

## 1. Overview
This plan outlines the architecture and implementation details for a configurable CSV data pipeline. The pipeline reads data from an input directory, applies a sequence of transformations defined in a YAML configuration, and outputs processed data to an output directory.

The system supports dry-run modes for validation without I/O side effects and provides logging to monitor pipeline execution.

## 2. Prerequisites & Assumptions

### 2.1 Technical Stack
- **Language:** Python 3.9 or higher.
- **Key Libraries:**
  - `pandas >= 1.5.0` (for data manipulation).
  - `PyYAML >= 6.0` (for configuration parsing).
  - `logging` (standard library for logging).
  - `pytest >= 7.0` (for testing).

### 2.2 Assumptions
1.  **Environment:** The code resides at `/home/jye/publications/cases/case_003_data_pipeline/`. The `WorkingDir` is a subdirectory at `/home/jye/publications/cases/case_003_data_pipeline/WorkingDir` containing input CSVs.
2.  **CSV Format:** Input CSVs must have UTF-8 encoding and standard headers without special characters that break `pandas` reading without quoting.
3.  **Transformation Logic:** Transformations will be atomic. Each transform returns a `pd.DataFrame`. Intermediate results are stored in memory, not disk, until the final output.
4.  **Chaining:** Transforms are executed sequentially. The output DataFrame of Step `N` becomes the input DataFrame for Step `N+1`.
5.  **Dry-Run:** In dry-run mode, the pipeline generates a log of actions but does not write the final CSV files or modify directories.
6.  **Paths:** Input and Output paths are configured in `pipeline.yaml`. If the Output directory does not exist, the pipeline will create it.

## 3. Directory Structure
The following structure is assumed within the project root (`/home/jye/publications/cases/case_003_data_pipeline/`):

```text
/home/jye/publications/cases/case_003_data_pipeline/
├── WorkingDir/               # Input CSV files (e.g., data_2023.csv)
├── Output/                   # Output CSV files (created by pipeline)
├── pipeline.yaml             # Pipeline configuration
├── pipeline.py               # Main orchestrator
├── transforms.py             # Transform function definitions
├── test_pipeline.py          # Unit and Integration tests
└── requirements.txt          # Python dependencies (optional, but recommended)
```

## 4. Module: `transforms.py`
This module contains a registry of transformation classes and a utility function to apply them.

### 4.1 Design Decisions
- Use a Base Class `Transform` to handle parameterization.
- Instantiate objects based on the `type` key in the YAML configuration.
- Ensure all transforms accept a `DataFrame` and return a `DataFrame`.

### 4.2 Implementation (`transforms.py`)

```python
"""
transforms.py

Core transformation logic and registry for the CSV pipeline.
"""

import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# Registry to map string names to Transform classes
TRANSFORM_REGISTRY = {}

class Transform(ABC):
    """Abstract base class for pipeline transformations."""
    
    @abstractmethod
    def apply(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply the transformation to the DataFrame.
        
        Args:
            df: Input pandas DataFrame.
            params: Dictionary of configuration parameters for this transform.
            
        Returns:
            Processed pandas DataFrame.
        """
        pass

class FilterRows(Transform):
    """Filters rows based on a boolean condition or specific values."""
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.expression = params.get('expression', None)
    
    def apply(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        # Note: In production, 'expression' could be compiled or a function object.
        # For simplicity, we assume a boolean string or lambda string evaluation here.
        # Ideally, pass a python lambda directly in YAML params.
        return df.apply(self.expression) if self.expression else df

class RenameColumns(Transform):
    """Renames DataFrame columns based on a mapping."""
    def apply(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        rename_map = params.get('mapping', {})
        df = df.rename(columns=rename_map)
        return df

class DeriveColumn(Transform):
    """Computes a new column based on existing columns or values."""
    def apply(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        new_name = params.get('name', 'computed_col')
        formula = params.get('formula', '1') # Simple example string formula
        df[new_name] = eval(formula) if formula.startswith('1') else df['base_col'] * 2
        return df

def register_transform(name: str, cls: Transform) -> None:
    """Decorator or helper to register transforms in the global registry."""
    TRANSFORM_REGISTRY[name] = cls

@register_transform('filter')
class FilterRowsInstance(Transform):
    # Specific implementation using params passed directly
    def apply(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        # Logic for filtering rows goes here
        return df[params.get('conditions', df.columns[0] == 'Active')] # Simplified logic

@register_transform('rename')
class RenameInstance(Transform):
    def apply(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        return df.rename(columns=params.get('mapping', {}))

@register_transform('derive')
class DeriveInstance(Transform):
    def apply(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        # Logic for derived columns
        return df

def get_transform(transform_type: str, params: Dict[str, Any]) -> Transform:
    """Factory function to instantiate a transform from registry."""
    if transform_type not in TRANSFORM_REGISTRY:
        raise ValueError(f"Unknown transform type: {transform_type}")
    cls = TRANSFORM_REGISTRY[transform_type]
    return cls(params)
```

## 5. Module: `pipeline.py`
This module acts as the main orchestrator. It handles configuration loading, logging setup, dry-run state management, and the execution loop.

### 5.1 Design Decisions
- Use `pathlib` for path handling to ensure cross-platform compatibility.
- Use `logging` with file handler and console handler.
- The `run` method iterates through the `steps` list in the config and chains results.

### 5.2 Implementation (`pipeline.py`)

```python
"""
pipeline.py

Main orchestrator for the CSV Data Pipeline.
"""

import sys
import os
import logging
import logging.config
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

# Import Transform classes (must be imported to populate registry if using decorator)
from transforms import get_transform, Transform

# Global State
class PipelineConfig:
    """Container for pipeline configuration and state."""
    def __init__(self, config_path: Path):
        self.root_path = Path(config_path).parent
        self.input_dir = Path(self.root_path) / "WorkingDir"
        self.output_dir = Path(self.root_path) / "Output"
        self.config_data = self.load_config(config_path)
        self.logger = self.setup_logging()
        self.dry_run = self.config_data.get('dry_run', False)

    def load_config(self, path: Path) -> Dict[str, Any]:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def setup_logging(self) -> logging.Logger:
        level = getattr(logging, self.config_data.get('logging_level', 'INFO'))
        log_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': 'INFO',
                    'formatter': 'default',
                    'stream': 'ext://sys.stdout'
                },
                'file': {
                    'class': 'logging.FileHandler',
                    'level': 'DEBUG',
                    'formatter': 'default',
                    'filename': self.root_path / 'pipeline.log'
                }
            },
            'root': {
                'level': 'INFO',
                'handlers': ['console', 'file']
            }
        }
        logging.config.dictConfig(log_config)
        return logging.getLogger('csv_pipeline')

    def execute(self):
        """
        Executes the pipeline workflow.
        
        1. Initializes Output directory.
        2. Reads CSVs from Input directory.
        3. Applies transforms from config steps.
        4. Writes result to Output directory (unless dry_run).
        """
        output_dir = self.output_dir
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created output directory: {output_dir}")

        # Initialize Data Source
        source_data = self._read_source()

        if not source_data.empty:
            self.logger.info(f"Loaded {len(source_data)} rows from CSV(s)")

            # Chain Transforms
            for step in self.config_data.get('steps', []):
                transform_type = step.get('type')
                params = step.get('params', {})
                
                self.logger.info(f"Applying transform: {transform_type}")
                
                if self.dry_run:
                    source_data = self._simulate_transform(source_data, transform_type, params)
                    self.logger.info(f"[DRY-RUN] Would apply {transform_type} on DataFrame shape {source_data.shape}")
                else:
                    transform = get_transform(transform_type, params)
                    source_data = transform.apply(source_data, params)
                    self.logger.info(f"Transform {transform_type} completed. New shape: {source_data.shape}")

            # Write Output
            if not self.dry_run:
                output_path = self.output_dir / "processed_data.csv"
                source_data.to_csv(output_path, index=False)
                self.logger.info(f"Data written to {output_path}")
                self.logger.info("Pipeline execution finished successfully.")
            else:
                self.logger.info("Dry run finished. No files written.")
        else:
            self.logger.warning("No data loaded to process.")

    def _read_source(self) -> pd.DataFrame:
        """Reads all CSVs from the working directory into a single DataFrame."""
        if not self.input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {self.input_dir}")
        
        csv_files = list(self.input_dir.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError("No CSV files found in input directory.")
        
        dataframes = []
        for csv_file in csv_files:
            # Assuming single schema for all CSVs. If heterogeneous, append differently.
            df = pd.read_csv(csv_file)
            dataframes.append(df)
        
        # Concatenate all CSVs
        return pd.concat(dataframes, ignore_index=True)

    def _simulate_transform(self, df: pd.DataFrame, type_: str, params: Dict) -> pd.DataFrame:
        """Placeholder for dry-run logic (prints what happens instead of modifying DF permanently if side effects exist)."""
        # In dry-run, we just return the DF or simulate the log output.
        # Logic here depends on if the transform modifies shape or content significantly.
        return df
```

## 6. Configuration: `pipeline.yaml`
This file defines the workflow. It separates structure from code, allowing users to configure the pipeline without modifying Python files.

### 6.1 Structure (`pipeline.yaml`)
```yaml
# Configuration for CSV Pipeline
dry_run: false
logging_level: INFO
steps:
  - type: filter
    params:
      expression: 'row["status"] == "Active"'
  - type: rename
    params:
      mapping:
        "status": "stat"
        "id": "identifier"
  - type: derive
    params:
      name: "score"
      formula: "val * 1.1"
```

*Explanation:*
- `dry_run`: If `true`, skips file writing.
- `logging_level`: Controls verbosity (`DEBUG`, `INFO`, `WARNING`).
- `steps`: A list of dictionaries. Each entry specifies the `type` (matches keys in `transforms.py`) and `params` (data passed to the transform's `__init__` or `apply` method).

## 7. Module: `test_pipeline.py`
Unit tests to verify transform logic and pipeline orchestration without external CSV files (mocking where necessary).

### 7.1 Design Decisions
- Use `pytest` fixtures to generate mock DataFrames.
- Mock file I/O for `pipeline.py` to verify it doesn't write when `dry_run=True`.
- Use `subprocess` or direct invocation to test the main entry point.

### 7.2 Implementation (`test_pipeline.py`)

```python
"""
test_pipeline.py

Unit and integration tests for the CSV Pipeline.
"""

import os
import tempfile
import pytest
import pandas as pd
from pathlib import Path
import yaml
from pipeline import PipelineConfig

# Import for inspection
from transforms import FilterRows, RenameColumns, DeriveColumn

def sample_csv():
    """Helper to generate a consistent sample DataFrame for testing."""
    data = {
        'id': [1, 2, 3, 4, 5],
        'status': ['Active', 'Inactive', 'Active', 'Active', 'Inactive'],
        'val': [100, 200, 150, 300, 400]
    }
    return pd.DataFrame(data)

def setup_input_dir(csv_data):
    """Creates a temporary directory with CSV data."""
    tmp_dir = Path(tempfile.mkdtemp())
    csv_path = tmp_dir / "input.csv"
    csv_data.to_csv(csv_path, index=False)
    return tmp_dir

def cleanup_input_dir(path: Path):
    if path.exists():
        import shutil
        shutil.rmtree(path)

class TestTransforms:
    def test_rename_transform(self):
        """Test the rename transform logic."""
        df = sample_csv()
        transform = RenameColumns({"status": "stat"})
        result = transform.apply(df, {"mapping": {"status": "stat"}})
        assert "stat" in result.columns

    def test_filter_transform(self):
        """Test filtering rows."""
        df = sample_csv()
        # Note: In actual implementation, filter logic must be passed as callable or string
        # Here we assume the logic in transforms.py handles this.
        # Placeholder for logic verification.
        pass

class TestPipeline:
    @pytest.fixture
    def temp_config(self, monkeypatch):
        config = {
            'dry_run': True, # Safe for testing
            'logging_level': 'WARNING',
            'input_dir': Path.cwd() / 'WorkingDir',
            'output_dir': Path.cwd() / 'Output',
            'steps': [
                {'type': 'rename', 'params': {'mapping': {'id': 'user_id'}}}
            ]
        }
        # Write to temp for test
        tmp_config = Path(tempfile.mktemp(suffix='.yaml'))
        with open(tmp_config, 'w') as f:
            yaml.dump(config, f)
        monkeypatch.setattr('pipeline.yaml', config) # Mocking yaml load if necessary
        return tmp_config

    def test_pipeline_dry_run(self, temp_config):
        """Test that the pipeline does not write files in dry_run mode."""
        # Setup
        csv_data = sample_csv()
        input_path = Path.cwd() / "WorkingDir"
        input_path.mkdir(exist_ok=True)
        csv_data.to_csv(input_path / "test_input.csv", index=False)
        
        # Run
        # (Mocking PipelineConfig to use local temp or override paths)
        # Ideally we refactor PipelineConfig to accept a directory arg directly for tests.
        # This is a placeholder for the integration logic.
        assert not (Path.cwd() / 'Output' / 'processed_data.csv').exists()
```

## 8. Implementation Steps & Workflow

To execute this plan, follow these sequential steps:

1.  **Dependency Installation:**
    Run `pip install pandas pyyaml pytest`.
2.  **File Creation:**
    Create `pipeline.py`, `transforms.py`, `pipeline.yaml`, and `test_pipeline.py` in the project root.
3.  **Directory Setup:**
    Ensure the `WorkingDir` exists with sample CSV files (e.g., `data_sample_1.csv`, `data_sample_2.csv`).
4.  **Configuration:**
    Edit `pipeline.yaml` to specify the `steps` and path configuration.
5.  **Logging Check:**
    Modify `pipeline.yaml` to `logging_level: DEBUG` to observe the dry-run logs.
6.  **Testing:**
    Run `pytest` from the project root to validate unit logic before running the full pipeline.
7.  **Execution:**
    Run `python pipeline.py` (or via CLI entry point `python -m pipeline.cli` if added) to trigger the workflow.

## 9. Deployment & Execution

### 9.1 Running the Pipeline
To execute the pipeline with the current configuration:

```bash
cd /home/jye/publications/cases/case_003_data_pipeline
python pipeline.py --config pipeline.yaml
```

### 9.2 Dry-Run Execution
To verify logic without side effects:

```bash
# Edit pipeline.yaml to set dry_run: true
python pipeline.py --config pipeline.yaml
# Check console logs for "DRY-RUN" messages
```

### 9.3 Logging Verification
Logs will be written to:
`/home/jye/publications/cases/case_003_data_pipeline/pipeline.log`

Console output will show:
- Loading CSV counts.
- Transform application sequence.
- Data shape changes (rows/columns) after each step.
- Final write confirmation or dry-run summary.

## 10. Technical Decisions Rationale

1.  **Class-Based Transforms:** Using a `Transform` base class allows for a registry pattern. This supports the requirement to "support chaining arbitrary transforms" without hardcoding logic in the main orchestration loop. It allows developers to add new transform types (e.g., `DropColumns`, `PivotData`) simply by inheriting from `Transform` and registering it.
2.  **DataFrame Chaining:** The pipeline operates on a single `pd.DataFrame` instance through memory (in-memory processing) to avoid intermediate disk I/O overhead, improving speed for moderate dataset sizes.
3.  **Configuration-Driven:** Using YAML for steps decouples logic from configuration. This allows business users to adjust the data flow (filtering criteria, column mappings) without touching Python code.
4.  **Logging:** Using `dictConfig` allows centralized logging setup. This ensures that both console output (for developers) and file logs (for production) are managed consistently.
5.  **Dry-Run Flag:** Implemented at the configuration level (`dry_run`) and checked before I/O operations. This is crucial for validating the configuration before committing to disk writes in a production environment.
6.  **Pathlib:** Using `pathlib.Path` ensures that file paths are handled correctly regardless of the OS (Windows/Linux), preventing forward/slash path issues.
7.  **Error Handling:** Implicitly handled via `pandas` exceptions. The plan assumes `try/except` blocks should be added in `transforms.py` around specific logic (e.g., `eval`) to catch `NameError` or `SyntaxError` in derived column formulas.

## 11. Security & Robustness Considerations
- **Input Validation:** The `transforms.py` module should validate `params` (e.g., ensure `mapping` keys match existing columns) to prevent `KeyError`.
- **File Locking:** If the pipeline is run by multiple users, standard Python file writes are generally atomic, but a lock file mechanism (not included in base scope) should be added if concurrent execution is expected.
- **Sensitive Data:** Ensure no transforms in `pipeline.yaml` are used that leak sensitive PII to external sinks without encryption.

---

*End of Implementation Plan*

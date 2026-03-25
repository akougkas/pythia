---
case: case_003_data_pipeline
framework: langgraph
model: gpt-oss:20b
provider: ollama
session_id: None
duration_ms: 19471
duration_wall_s: 19.5
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T22:53:37.237545+00:00
error: None
---

# Plan

## Implementation Plan – CSV Data Pipeline (Case 003)

Below is a **step‑by‑step, actionable plan** that covers every deliverable, the overall architecture, the key design decisions, and the unit‑test strategy.  
All code will be written in **Python 3.11+** and will run in the provided working directory:

```
/home/jye/publications/cases/case_003_data_pipeline/WorkingDir
```

> **Assumptions**  
> 1. The working directory contains a sub‑folder `input/` with CSV files and a sub‑folder `output/` for results.  
> 2. The reference `pipeline.yaml` in the repo is a valid example; we will use it as a template.  
> 3. The user will run the orchestrator via `python pipeline.py --config pipeline.yaml [--dry-run] [--log-level INFO]`.  
> 4. No external dependencies beyond `pandas`, `pyyaml`, and the standard library.  

---

### 1. Project Skeleton

```
case_003_data_pipeline/
├── pipeline.py          # Orchestrator
├── transforms.py        # Individual transform functions
├── pipeline.yaml        # Example config
├── test_pipeline.py     # Unit tests
├── requirements.txt
└── README.md
```

---

### 2. Configuration Schema (`pipeline.yaml`)

The YAML file describes the pipeline as a list of steps. Each step has:

| Key | Type | Description |
|-----|------|-------------|
| `name` | str | Human‑readable step name (used in logs). |
| `type` | str | One of: `filter`, `rename`, `derive`. |
| `params` | dict | Parameters specific to the step type. |

#### Example

```yaml
steps:
  - name: Filter rows where age > 30
    type: filter
    params:
      condition: "age > 30"

  - name: Rename columns
    type: rename
    params:
      mapping:
        first_name: first
        last_name: last

  - name: Compute full name
    type: derive
    params:
      new_column: full_name
      expression: "first + ' ' + last"
```

> **Note**: The `condition` and `expression` strings are evaluated with `pandas.eval` (safe subset).  

---

### 3. `transforms.py`

Define a **transform registry** mapping step types to functions. Each function receives a `pandas.DataFrame` and the `params` dict, returns a transformed `DataFrame`.

```python
# transforms.py
import pandas as pd
from typing import Dict, Callable

def filter_rows(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    condition = params["condition"]
    return df.query(condition)

def rename_columns(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    mapping = params["mapping"]
    return df.rename(columns=mapping)

def derive_column(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    new_col = params["new_column"]
    expr = params["expression"]
    df[new_col] = df.eval(expr)
    return df

TRANSFORM_REGISTRY: Dict[str, Callable[[pd.DataFrame, Dict], pd.DataFrame]] = {
    "filter": filter_rows,
    "rename": rename_columns,
    "derive": derive_column,
}
```

*All functions are pure (no side‑effects) and raise `KeyError` if required keys are missing.*

---

### 4. `pipeline.py`

#### 4.1 Imports & Argument Parsing

```python
import argparse
import logging
import os
import sys
import yaml
import pandas as pd
from pathlib import Path
from transforms import TRANSFORM_REGISTRY
```

#### 4.2 Logging Setup

```python
def setup_logging(level: str):
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )
```

#### 4.3 YAML Loader

```python
def load_config(path: Path) -> dict:
    with path.open("r") as f:
        cfg = yaml.safe_load(f)
    if "steps" not in cfg or not isinstance(cfg["steps"], list):
        raise ValueError("Config must contain a top‑level 'steps' list.")
    return cfg
```

#### 4.4 Core Pipeline Execution

```python
def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    cfg: dict,
    dry_run: bool = False,
) -> None:
    input_files = sorted(input_dir.glob("*.csv"))
    if not input_files:
        logging.warning("No CSV files found in %s", input_dir)
        return

    for csv_path in input_files:
        logging.info("Processing file: %s", csv_path.name)
        df = pd.read_csv(csv_path)

        for step_cfg in cfg["steps"]:
            step_name = step_cfg.get("name", "Unnamed step")
            step_type = step_cfg["type"]
            params = step_cfg.get("params", {})

            logging.debug("  Step: %s (%s)", step_name, step_type)
            transform_fn = TRANSFORM_REGISTRY.get(step_type)
            if not transform_fn:
                raise ValueError(f"Unknown transform type: {step_type}")

            df = transform_fn(df, params)

        if dry_run:
            logging.info("Dry‑run: would write to %s", output_dir / csv_path.name)
        else:
            out_path = output_dir / csv_path.name
            df.to_csv(out_path, index=False)
            logging.info("  Written to %s", out_path)
```

#### 4.5 Main Entry Point

```python
def main():
    parser = argparse.ArgumentParser(description="CSV Data Pipeline")
    parser.add_argument("--config", required=True, type=Path, help="Path to pipeline.yaml")
    parser.add_argument("--input-dir", default="input", type=Path, help="Directory with input CSVs")
    parser.add_argument("--output-dir", default="output", type=Path, help="Directory for output CSVs")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing files")
    parser.add_argument("--log-level", default="INFO", help="Logging verbosity (DEBUG, INFO, WARNING, ERROR)")
    args = parser.parse_args()

    setup_logging(args.log_level)

    cfg = load_config(args.config)

    args.input_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    run_pipeline(args.input_dir, args.output_dir, cfg, args.dry_run)

if __name__ == "__main__":
    main()
```

---

### 5. `pipeline.yaml` (Example)

```yaml
steps:
  - name: Filter rows where age > 30
    type: filter
    params:
      condition: "age > 30"

  - name: Rename columns
    type: rename
    params:
      mapping:
        first_name: first
        last_name: last

  - name: Compute full name
    type: derive
    params:
      new_column: full_name
      expression: "first + ' ' + last"
```

Place this file in the project root. Users can modify it to add/remove steps.

---

### 6. Unit Tests (`test_pipeline.py`)

#### 6.1 Test Strategy

| Test | Purpose |
|------|---------|
| `test_filter_rows` | Verify that `filter_rows` correctly filters rows. |
| `test_rename_columns` | Verify column renaming. |
| `test_derive_column` | Verify derived column calculation. |
| `test_pipeline_execution` | End‑to‑end pipeline on a small in‑memory CSV. |
| `test_dry_run` | Ensure no files are written when `dry_run=True`. |
| `test_invalid_step` | Pipeline raises error on unknown transform type. |

#### 6.2 Test Implementation

```python
# test_pipeline.py
import io
import os
import tempfile
import yaml
import pandas as pd
import pytest
from pathlib import Path
from pipeline import run_pipeline, load_config
from transforms import TRANSFORM_REGISTRY

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "first_name": ["Alice", "Bob"],
        "last_name": ["Smith", "Jones"],
        "age": [25, 35]
    })

def test_filter_rows(sample_df):
    df = TRANSFORM_REGISTRY["filter"](sample_df.copy(), {"condition": "age > 30"})
    assert len(df) == 1
    assert df.iloc[0]["first_name"] == "Bob"

def test_rename_columns(sample_df):
    df = TRANSFORM_REGISTRY["rename"](sample_df.copy(), {"mapping": {"first_name": "first"}})
    assert "first" in df.columns
    assert "first_name" not in df.columns

def test_derive_column(sample_df):
    df = TRANSFORM_REGISTRY["derive"](sample_df.copy(), {
        "new_column": "full_name",
        "expression": "first_name + ' ' + last_name"
    })
    assert "full_name" in df.columns
    assert df.iloc[0]["full_name"] == "Alice Smith"

def test_pipeline_execution(tmp_path):
    # Create input CSV
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    csv_path = input_dir / "test.csv"
    sample_df = pd.DataFrame({
        "first_name": ["Alice", "Bob"],
        "last_name": ["Smith", "Jones"],
        "age": [25, 35]
    })
    sample_df.to_csv(csv_path, index=False)

    # Config
    cfg = {
        "steps": [
            {"name": "Filter", "type": "filter", "params": {"condition": "age > 30"}},
            {"name": "Rename", "type": "rename", "params": {"mapping": {"first_name": "first"}}},
            {"name": "Derive", "type": "derive", "params": {"new_column": "full_name", "expression": "first + ' ' + last_name"}}
        ]
    }

    run_pipeline(input_dir, output_dir, cfg, dry_run=False)

    out_csv = output_dir / "test.csv"
    assert out_csv.exists()
    out_df = pd.read_csv(out_csv)
    assert len(out_df) == 1
    assert "full_name" in out_df.columns
    assert out_df.iloc[0]["full_name"] == "Bob Jones"

def test_dry_run(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    csv_path = input_dir / "test.csv"
    pd.DataFrame({"a": [1, 2]}).to_csv(csv_path, index=False)

    cfg = {"steps": []}
    run_pipeline(input_dir, output_dir, cfg, dry_run=True)

    # No file should be created
    assert not any(output_dir.iterdir())

def test_invalid_step(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    csv_path = input_dir / "test.csv"
    pd.DataFrame({"a": [1]}).to_csv(csv_path, index=False)

    cfg = {"steps": [{"name": "Bad", "type": "unknown", "params": {}}]}
    with pytest.raises(ValueError, match="Unknown transform type"):
        run_pipeline(input_dir, output_dir, cfg, dry_run=False)
```

Run tests with:

```
pytest test_pipeline.py
```

---

### 7. `requirements.txt`

```
pandas>=2.0
pyyaml>=6.0
pytest>=7.0
```

---

### 8. README (Optional)

Provide a short usage guide:

```
# CSV Data Pipeline

## Setup
pip install -r requirements.txt

## Run
python pipeline.py --config pipeline.yaml

## Dry‑run
python pipeline.py --config pipeline.yaml --dry-run

## Logging
python pipeline.py --config pipeline.yaml --log-level DEBUG
```

---

### 9. Execution Flow Summary

1. **CLI** parses arguments → sets up logging.  
2. **Config** loaded from YAML → validated.  
3. **Input directory** scanned for CSVs.  
4. For each file:  
   - Load into `pandas.DataFrame`.  
   - Iterate over `steps` → apply corresponding transform.  
   - If `dry_run` → log intended output path.  
   - Else → write transformed DataFrame to `output_dir`.  
5. **Unit tests** cover individual transforms, pipeline orchestration, dry‑run, and error handling.

---

### 10. Deliverables Checklist

| Deliverable | Status |
|-------------|--------|
| `pipeline.py` | **Planned** – code skeleton provided. |
| `transforms.py` | **Planned** – registry and functions defined. |
| `pipeline.yaml` | **Planned** – example config included. |
| `test_pipeline.py` | **Planned** – full test suite. |
| `requirements.txt` | **Planned** – dependencies listed. |
| `README.md` | **Optional** – brief usage guide. |

All files will be committed to the repository under the working directory. The plan above contains every step needed to implement, test, and run the CSV data pipeline.

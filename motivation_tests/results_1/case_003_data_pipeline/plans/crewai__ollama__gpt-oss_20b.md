---
case: case_003_data_pipeline
framework: crewai
model: gpt-oss:20b
provider: ollama
session_id: None
duration_ms: 22556
duration_wall_s: 22.6
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T23:26:57.027087+00:00
error: None
---

# Plan

# Case 003 – CSV Data Pipeline  
**Implementation Plan**  
*(Markdown – do **not** execute any code)*

---

## 1.  High‑level Overview
| Component | Responsibility |
|-----------|----------------|
| `pipeline.py` | CLI entry point, config loader, orchestrator, logging, dry‑run handling |
| `transforms.py` | Registry of all transform functions, helper utilities |
| `config/pipeline.yaml` | Example pipeline configuration |
| `tests/test_pipeline.py` | Unit & integration tests |
| `WorkingDir/input/` | Folder with source CSVs |
| `WorkingDir/output/` | Folder for processed CSVs |
| `logs/` | Runtime log files |

---

## 2.  Assumptions
1. **Python 3.10+** is available.  
2. `pandas` ≥ 1.5.0, `pyyaml` ≥ 5.3, `pytest` ≥ 7.0 are installed.  
3. No external job‑queue or streaming framework is required – the pipeline runs as a single process.  
4. All CSVs share the same schema; otherwise, missing columns are filled with NaNs.  
5. Configuration will **always** be in `config/pipeline.yaml`; the path can be overridden with `--config`.  
6. Logging verbosity levels: `ERROR` (0), `WARNING` (1), `INFO` (2), `DEBUG` (3).  

---

## 3.  Technical Decisions

| Decision | Reasoning |
|----------|-----------|
| **Use a registry dict** to map step names to callable transforms – enables extensibility without hard‑coding a `if‑else` chain. | Clean, O(1) lookup, easy to add new transforms. |
| **`pandas.eval`** for derived columns – safe expression parsing and vectorized operations. | Keeps transform logic declarative; users can write expressions like `"A + B * 2"`. |
| **Dry‑run flag**: if set, the orchestrator logs the actions but **skips** writing files. | Allows validation of config and pipeline logic without I/O. |
| **`argparse`** for CLI arguments. | Simple, standard library, no external deps. |
| **`logging` module** with a dedicated logger (`pipeline`). | Centralizes configuration; supports file + console handlers. |
| **Test coverage**: unit tests for each transform; integration test that processes a small sample CSV and compares output. | Guarantees functional correctness and regression protection. |

---

## 4.  Directory Layout
```
/home/jye/publications/cases/case_003_data_pipeline/
├── pipeline.py
├── transforms.py
├── config/
│   └── pipeline.yaml
├── WorkingDir/
│   ├── input/
│   │   └── sample1.csv
│   └── output/
├── tests/
│   └── test_pipeline.py
└── logs/
```

*All file paths in this plan are relative to the project root (`/home/jye/publications/cases/case_003_data_pipeline/`).*

---

## 5.  Configuration Schema (`config/pipeline.yaml`)

```yaml
# Example pipeline.yaml

input_dir: "../WorkingDir/input"      # relative to project root
output_dir: "../WorkingDir/output"    # relative to project root
dry_run: false
verbosity: 2                          # 0=ERROR, 1=WARNING, 2=INFO, 3=DEBUG

steps:
  - type: filter_rows
    name: "filter_positive"
    params:
      conditions:
        - column: "value"
          op: "gt"
          value: 0

  - type: rename_columns
    name: "rename_to_camel"
    params:
      columns:
        old_col1: "NewCol1"
        old_col2: "NewCol2"

  - type: compute_column
    name: "calc_total"
    params:
      new_column: "Total"
      expression: "NewCol1 + NewCol2"

```

*Schema explanation*

| Key | Type | Description |
|-----|------|-------------|
| `input_dir` | string | Path to source CSVs |
| `output_dir` | string | Path where results will be written |
| `dry_run` | bool | If `true`, pipeline will log actions only |
| `verbosity` | int | Logging level |
| `steps` | list | Ordered list of transform steps |
| `type` | string | Must match a key in the transform registry (`filter_rows`, `rename_columns`, `compute_column`, …) |
| `name` | string | Human‑readable identifier – used only for logging |
| `params` | dict | Keyword arguments forwarded to the transform function |

---

## 6.  `transforms.py` – Implementation Blueprint

```python
# transforms.py
"""
Utility module containing all data transforms.
Each transform is registered via the @register_transform decorator.
"""

import pandas as pd
from typing import Callable, Dict, Any, List
import logging

# ---------- Registry ----------
_registry: Dict[str, Callable] = {}

def register_transform(name: str) -> Callable:
    """Decorator to register a transform in the global registry."""
    def decorator(func: Callable) -> Callable:
        _registry[name] = func
        return func
    return decorator

def get_transform(name: str) -> Callable:
    """Retrieve a transform by name. Raises KeyError if not found."""
    return _registry[name]

# ---------- Individual transforms ----------
@register_transform('filter_rows')
def filter_rows(df: pd.DataFrame, conditions: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Filters rows based on a list of conditions.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe.
    conditions : list of dict
        Each dict must contain:
            - column: column name
            - op: one of 'eq', 'ne', 'lt', 'le', 'gt', 'ge'
            - value: value to compare against
    """
    import operator
    op_map = {
        'eq': operator.eq,
        'ne': operator.ne,
        'lt': operator.lt,
        'le': operator.le,
        'gt': operator.gt,
        'ge': operator.ge,
    }
    mask = pd.Series(True, index=df.index)
    for cond in conditions:
        col = cond['column']
        op = op_map[cond['op']]
        val = cond['value']
        mask &= op(df[col], val)
    return df[mask].copy()

@register_transform('rename_columns')
def rename_columns(df: pd.DataFrame, columns: Dict[str, str]) -> pd.DataFrame:
    """
    Renames columns according to the provided mapping.

    Parameters
    ----------
    df : pd.DataFrame
    columns : dict
        Mapping from old name -> new name
    """
    return df.rename(columns=columns)

@register_transform('compute_column')
def compute_column(df: pd.DataFrame, new_column: str, expression: str) -> pd.DataFrame:
    """
    Adds a derived column using pandas.eval for vectorised computation.

    Parameters
    ----------
    df : pd.DataFrame
    new_column : str
        Name of the new column to add.
    expression : str
        Pandas-compatible expression referencing existing columns.
    """
    df[new_column] = df.eval(expression)
    return df
```

**Extension point**: to add a new transform, simply create a function decorated with `@register_transform('my_new_type')`.

---

## 7.  `pipeline.py` – Orchestrator Blueprint

```python
#!/usr/bin/env python3
# pipeline.py
"""
Main orchestrator for the CSV data pipeline.
"""

import argparse
import logging
import pathlib
import sys
import time
import yaml
import pandas as pd
from typing import Dict, Any

from transforms import get_transform, _registry  # import registry for introspection

# ---------- Logging ----------
LOG = logging.getLogger('pipeline')

def setup_logging(verbosity: int) -> None:
    level = {0: logging.ERROR, 1: logging.WARNING, 2: logging.INFO, 3: logging.DEBUG}.get(verbosity, logging.INFO)
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # File handler
    logfile = pathlib.Path('logs') / f'pipeline_{time.strftime("%Y%m%d_%H%M%S")}.log'
    logfile.parent.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(logfile)
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    LOG.addHandler(file_handler)

# ---------- Configuration ----------
def load_config(path: pathlib.Path) -> Dict[str, Any]:
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f)
    # Resolve relative paths
    base = cfg.get('base_path', pathlib.Path.cwd())
    cfg['input_dir'] = pathlib.Path(cfg['input_dir']).expanduser().resolve()
    cfg['output_dir'] = pathlib.Path(cfg['output_dir']).expanduser().resolve()
    return cfg

# ---------- Pipeline Execution ----------
def process_file(input_path: pathlib.Path, output_path: pathlib.Path,
                 steps: list, dry_run: bool) -> None:
    LOG.info(f"Processing file: {input_path.name}")
    df = pd.read_csv(input_path)
    LOG.debug(f"Loaded {len(df)} rows")

    for idx, step_cfg in enumerate(steps, start=1):
        step_type = step_cfg['type']
        name = step_cfg.get('name', f'step_{idx}')
        params = step_cfg.get('params', {})
        LOG.debug(f"Applying step {idx} ({step_type}): {name}")
        transform = get_transform(step_type)
        df = transform(df, **params)
        LOG.debug(f"Rows after step {idx}: {len(df)}")

    if dry_run:
        LOG.info(f"[DRY RUN] Would write to {output_path}")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        LOG.info(f"Wrote {len(df)} rows to {output_path}")

def main() -> None:
    parser = argparse.ArgumentParser(description="CSV Data Pipeline")
    parser.add_argument('--config', type=pathlib.Path, default='config/pipeline.yaml',
                        help="Path to YAML configuration file")
    parser.add_argument('--input-dir', type=pathlib.Path, default=None,
                        help="Override input directory")
    parser.add_argument('--output-dir', type=pathlib.Path, default=None,
                        help="Override output directory")
    parser.add_argument('--dry-run', action='store_true',
                        help="Show what would happen without writing files")
    parser.add_argument('--verbosity', type=int, default=2,
                        help="Logging verbosity level (0=ERROR, 1=WARNING, 2=INFO, 3=DEBUG)")
    args = parser.parse_args()

    setup_logging(args.verbosity)

    cfg = load_config(args.config)

    # Override directories if CLI args supplied
    if args.input_dir:
        cfg['input_dir'] = args.input_dir.resolve()
    if args.output_dir:
        cfg['output_dir'] = args.output_dir.resolve()

    LOG.info(f"Input dir: {cfg['input_dir']}")
    LOG.info(f"Output dir: {cfg['output_dir']}")
    LOG.info(f"Dry run: {args.dry_run or cfg.get('dry_run', False)}")

    # Gather CSV files
    input_files = list(cfg['input_dir'].glob('*.csv'))
    if not input_files:
        LOG.warning("No CSV files found in input directory.")
        return

    steps = cfg.get('steps', [])
    if not steps:
        LOG.warning("No transformation steps defined in config.")
        return

    for in_file in input_files:
        out_file = cfg['output_dir'] / in_file.name
        process_file(in_file, out_file, steps, args.dry_run or cfg.get('dry_run', False))

if __name__ == '__main__':
    main()
```

**Key Points**

1. **Logging** – console + file. Log file is timestamped.  
2. **Configuration override** – CLI can change directories and dry‑run flag.  
3. **Step execution** – each step calls the registered transform.  
4. **Dry‑run** – simply logs the intended write path.  
5. **Graceful handling** – if no CSVs or no steps, logs a warning and exits.

---

## 8.  Unit / Integration Tests (`tests/test_pipeline.py`)

```python
# tests/test_pipeline.py
import pathlib
import shutil
import tempfile
import pytest
import pandas as pd
import yaml

from pipeline import process_file
from transforms import _registry, filter_rows, rename_columns, compute_column

# ---------- Fixtures ----------
@pytest.fixture
def sample_csv(tmp_path):
    df = pd.DataFrame({
        'old_col1': [1, 2, 3],
        'old_col2': [4, 5, 6],
        'value': [10, -5, 20]
    })
    csv_path = tmp_path / 'sample.csv'
    df.to_csv(csv_path, index=False)
    return csv_path, df

@pytest.fixture
def tmp_output_dir(tmp_path):
    out_dir = tmp_path / 'out'
    out_dir.mkdir()
    return out_dir

# ---------- Individual transform tests ----------
def test_filter_rows():
    df = pd.DataFrame({'x': [1, 2, 3]})
    out = filter_rows(df, [{'column': 'x', 'op': 'gt', 'value': 1}])
    assert len(out) == 2
    assert out['x'].tolist() == [2, 3]

def test_rename_columns():
    df = pd.DataFrame({'a': [1], 'b': [2]})
    out = rename_columns(df, {'a': 'alpha', 'b': 'beta'})
    assert list(out.columns) == ['alpha', 'beta']

def test_compute_column():
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    out = compute_column(df, 'sum', 'a + b')
    assert out['sum'].tolist() == [4, 6]

# ---------- Integration test ----------
def test_full_pipeline(sample_csv, tmp_output_dir):
    in_path, _ = sample_csv
    out_path = tmp_output_dir / 'sample.csv'

    steps = [
        {'type': 'filter_rows', 'params': {'conditions': [{'column': 'value', 'op': 'gt', 'value': 0}]}},
        {'type': 'rename_columns', 'params': {'columns': {'old_col1': 'NewCol1', 'old_col2': 'NewCol2'}}},
        {'type': 'compute_column', 'params': {'new_column': 'Total', 'expression': 'NewCol1 + NewCol2'}}
    ]

    process_file(in_path, out_path, steps, dry_run=False)

    # Verify output file exists
    assert out_path.exists()
    out_df = pd.read_csv(out_path)

    # Should have 2 rows (value > 0)
    assert len(out_df) == 2
    # Columns renamed
    assert 'NewCol1' in out_df.columns
    assert 'NewCol2' in out_df.columns
    # Derived column
    assert 'Total' in out_df.columns
    assert out_df['Total'].tolist() == [5, 9]

# ---------- Dry‑run test ----------
def test_dry_run(sample_csv, tmp_output_dir, caplog):
    in_path, _ = sample_csv
    out_path = tmp_output_dir / 'sample.csv'

    steps = [{'type': 'filter_rows', 'params': {'conditions': []}}]

    process_file(in_path, out_path, steps, dry_run=True)

    # Log should contain DRY RUN notice
    assert any("[DRY RUN]" in rec.message for rec in caplog.records)
    # No file written
    assert not out_path.exists()
```

**Notes**

- Tests use `tmp_path` fixture to create isolated directories.  
- `caplog` captures logging output to verify dry‑run behavior.  
- The integration test covers the full transform chain and verifies the final CSV.

---

## 9.  Example `config/pipeline.yaml`

```yaml
# config/pipeline.yaml
# This file demonstrates a typical pipeline configuration.

# Directory paths – relative to project root
input_dir: "../WorkingDir/input"
output_dir: "../WorkingDir/output"

# Execution flags
dry_run: false          # Set to true to validate without writing
verbosity: 2            # 0=ERROR, 1=WARNING, 2=INFO, 3=DEBUG

# Transformation chain
steps:
  - type: filter_rows
    name: "KeepPositive"
    params:
      conditions:
        - column: "value"
          op: "gt"
          value: 0

  - type: rename_columns
    name: "CamelCaseColumns"
    params:
      columns:
        old_col1: "NewCol1"
        old_col2: "NewCol2"

  - type: compute_column
    name: "CalculateTotal"
    params:
      new_column: "Total"
      expression: "NewCol1 + NewCol2"
```

---

## 10.  Build & Run Instructions

```bash
# 1. Clone / copy the repo into the specified working directory
cd /home/jye/publications/cases/case_003_data_pipeline

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install pandas pyyaml pytest

# 4. Run the pipeline (replace paths if needed)
python pipeline.py --config config/pipeline.yaml

# 5. To perform a dry‑run
python pipeline.py --config config/pipeline.yaml --dry-run

# 6. Run tests
pytest tests/test_pipeline.py
```

---

## 11.  Summary of Deliverables

| File | Purpose |
|------|---------|
| `pipeline.py` | CLI orchestrator, config loader, logging, dry‑run support |
| `transforms.py` | Registry and implementations of filter, rename, compute |
| `config/pipeline.yaml` | Sample pipeline configuration |
| `tests/test_pipeline.py` | Unit & integration tests for transforms and pipeline |
| `WorkingDir/input/` | Sample CSV files (provided in `WorkingDir`) |
| `WorkingDir/output/` | Destination for processed CSVs |
| `logs/` | Runtime log files (auto‑created) |

This plan gives a complete, reproducible blueprint for implementing, testing, and executing the CSV data pipeline with the specified constraints.

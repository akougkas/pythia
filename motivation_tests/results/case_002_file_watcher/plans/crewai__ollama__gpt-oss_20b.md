---
case: case_002_file_watcher
framework: crewai
model: gpt-oss:20b
provider: ollama
session_id: None
duration_ms: 20004
duration_wall_s: 20.0
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T23:24:43.603467+00:00
error: None
---

# Plan

# Implementation Plan – Case 002: File Watcher  
**Project root:** `/home/jye/publications/cases/case_002_file_watcher/`  

---

## 1. Overall Architecture

| Component | Responsibility | Tech Stack | Key Decisions |
|-----------|----------------|------------|---------------|
| `watcher.py` | CLI entry‑point; parses arguments, loads config, starts watchdog loop | argparse, watchdog, subprocess, logging | Single‑threaded process, uses watchdog’s `Observer` |
| `config.py` | Reads `watcher.yaml`, validates schema, exposes config object | pyyaml, jsonschema | YAML → Python dict → Typed dataclass for safety |
| `watcher.yaml` | Example config file | YAML | Show defaults, include/exclude, debounce, command |
| `test_watcher.py` | Unit tests for config loading, debounce logic, command execution | pytest, unittest.mock, tempfile | Test isolation using temporary directories |
| `tests/` | (Optional) Additional integration tests | pytest | Run watcher against a simulated file system |

> **Assumptions**
> * Python ≥3.9 is available.
> * Users will install dependencies via `pip install -r requirements.txt`.
> * The tool will run on Unix‑like OSes (Linux/macOS). Windows support is optional but not required for this spec.
> * Debounce interval is configurable per config file; defaults to 300 ms.

---

## 2. Directory Structure

```
case_002_file_watcher/
├── watcher.py
├── config.py
├── watcher.yaml
├── test_watcher.py
├── requirements.txt
├── README.md
└── WorkingDir/          # example project to monitor (provided)
```

`requirements.txt` will list:

```
watchdog>=2.0.0
pyyaml>=5.0
jsonschema>=4.0
```

`README.md` will describe usage.

---

## 3. Detailed File Contents

### 3.1 `watcher.py`

```python
#!/usr/bin/env python3
"""
watcher.py – CLI tool that watches a directory and runs a command on changes.
"""

import argparse
import logging
import os
import sys
import subprocess
import time
from pathlib import Path
from typing import List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import load_config, WatcherConfig

# --------------------------------------------------------------------------- #
# Logging setup
# --------------------------------------------------------------------------- #

def init_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

# --------------------------------------------------------------------------- #
# Event Handler
# --------------------------------------------------------------------------- #

class DebouncedEventHandler(FileSystemEventHandler):
    """
    Handles file system events and triggers the configured command
    after a debounce period.
    """

    def __init__(self, config: WatcherConfig):
        super().__init__()
        self.config = config
        self._timer = None
        self._lock = False  # simple flag to prevent re‑entrancy

    def on_any_event(self, event):
        if self._lock:
            return  # ignore events while timer is active
        if not event.is_directory and self._should_include(event.src_path):
            logging.debug(f"Event detected: {event}")
            self._schedule_command()

    def _should_include(self, path: str) -> bool:
        rel_path = os.path.relpath(path, self.config.watch_dir)
        for pattern in self.config.exclude:
            if Path(rel_path).match(pattern):
                return False
        for pattern in self.config.include:
            if Path(rel_path).match(pattern):
                return True
        # If no include patterns, default to include all
        return not self.config.include

    def _schedule_command(self):
        self._lock = True
        debounce = self.config.debounce_ms / 1000.0
        logging.debug(f"Scheduling command in {debounce}s")
        self._timer = self.config._observer.schedule(
            lambda: self._run_command(),
            debounce,
        )

    def _run_command(self):
        logging.info(f"Running command: {self.config.command}")
        try:
            subprocess.run(
                self.config.command,
                shell=True,
                check=True,
                cwd=self.config.watch_dir,
            )
            logging.info("Command finished successfully.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed: {e}")
        finally:
            self._lock = False

# --------------------------------------------------------------------------- #
# CLI parsing
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a directory for changes and run a command."
    )
    parser.add_argument(
        "-c",
        "--config",
        default="watcher.yaml",
        help="Path to YAML config file (default: watcher.yaml)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug level logging",
    )
    return parser.parse_args()

# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #

def main() -> None:
    args = parse_args()
    init_logging(logging.DEBUG if args.debug else logging.INFO)

    config_path = Path(args.config).expanduser()
    if not config_path.is_file():
        logging.error(f"Config file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)

    observer = Observer()
    handler = DebouncedEventHandler(config)
    observer.schedule(handler, path=str(config.watch_dir), recursive=True)
    observer.start()

    logging.info(f"Watching directory: {config.watch_dir}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Stopping watcher...")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
```

**Key Technical Decisions**

| Decision | Reason |
|----------|--------|
| Use `watchdog.Observer` with a custom handler | Lightweight, proven event loop. |
| Debounce implemented via a simple timer (`_timer` flag) | Avoids external async libs, keeps single‑threaded. |
| Command executed via `subprocess.run(..., shell=True)` | Allows arbitrary shell commands (e.g., `pytest`). |
| Include/exclude handled by `pathlib.Path.match()` | Supports glob patterns (`*.py`, `tests/**`). |
| Logging at INFO by default, DEBUG when `--debug` | Gives useful feedback without clutter. |

---

### 3.2 `config.py`

```python
"""
config.py – Loads and validates watcher.yaml
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Any, Optional

from jsonschema import validate, ValidationError

# --------------------------------------------------------------------------- #
# Schema definition (YAML file must match this schema)
# --------------------------------------------------------------------------- #

WATCHER_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "watch_dir": {"type": "string"},
        "command": {"type": "string"},
        "debounce_ms": {"type": "integer", "minimum": 0, "default": 300},
        "include": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
        "exclude": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
    },
    "required": ["watch_dir", "command"],
    "additionalProperties": False,
}

# --------------------------------------------------------------------------- #
# Dataclass
# --------------------------------------------------------------------------- #

@dataclass
class WatcherConfig:
    watch_dir: Path
    command: str
    debounce_ms: int = 300
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)

# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #

def load_config(path: Path) -> WatcherConfig:
    with path.open("r") as fh:
        data = yaml.safe_load(fh)

    try:
        validate(instance=data, schema=WATCHER_SCHEMA)
    except ValidationError as exc:
        raise ValueError(f"Invalid config file {path}: {exc.message}") from exc

    # Resolve relative watch_dir to absolute
    watch_dir = Path(data["watch_dir"]).expanduser().resolve()

    return WatcherConfig(
        watch_dir=watch_dir,
        command=data["command"],
        debounce_ms=data.get("debounce_ms", 300),
        include=data.get("include", []),
        exclude=data.get("exclude", []),
    )
```

**Decisions**

| Decision | Reason |
|----------|--------|
| Use `jsonschema` for validation | Provides clear error messages, future extensibility. |
| `watch_dir` resolved to absolute | Avoids ambiguity when running from different CWDs. |
| Defaults for optional fields defined in schema | Simplifies code, avoids `None` checks. |

---

### 3.3 `watcher.yaml` (Example)

```yaml
# watcher.yaml – Example configuration for the file watcher

# Directory to monitor (relative to the config file or absolute)
watch_dir: "./WorkingDir"

# Command to run when a change is detected
command: "pytest -q"

# Debounce time in milliseconds (default 300)
debounce_ms: 300

# Glob patterns to include (empty means include all)
include:
  - "**/*.py"

# Glob patterns to exclude
exclude:
  - "**/__pycache__/**"
  - "**/*.tmp"
```

**Notes**

- `watch_dir` can be relative; it will be resolved relative to the config file location.
- `include` defaults to all files if omitted; otherwise only matching patterns trigger the command.
- `exclude` patterns are processed first; any file matching an exclude pattern is ignored regardless of include.

---

### 3.4 `test_watcher.py`

```python
"""
test_watcher.py – Unit tests for the file watcher package.
"""

import os
import sys
import time
import shutil
import subprocess
import tempfile
import json
from pathlib import Path
from unittest import mock
import pytest

# Ensure the package import path works
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from config import load_config, WatcherConfig
from watcher import DebouncedEventHandler, init_logging

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d)

@pytest.fixture
def sample_config(temp_dir):
    """Return a WatcherConfig object pointing to temp_dir."""
    cfg_path = temp_dir / "watcher.yaml"
    cfg_path.write_text(
        """
watch_dir: "."
command: "echo test_command"
debounce_ms: 100
include: ["*.txt"]
exclude: []
"""
    )
    return load_config(cfg_path)

# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_load_config_valid(sample_config: WatcherConfig):
    assert sample_config.watch_dir == Path(".").resolve()
    assert sample_config.command == "echo test_command"
    assert sample_config.debounce_ms == 100
    assert sample_config.include == ["*.txt"]
    assert sample_config.exclude == []

def test_load_config_invalid(tmp_path: Path):
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text("invalid: yaml: true")
    with pytest.raises(ValueError):
        load_config(cfg_path)

def test_event_handler_triggers_command(temp_dir: Path, sample_config: WatcherConfig):
    # Mock subprocess.run to capture invocation
    with mock.patch("subprocess.run") as mock_run:
        handler = DebouncedEventHandler(sample_config)
        # Simulate file creation
        new_file = temp_dir / "hello.txt"
        new_file.write_text("hi")
        # Fire event manually
        event = mock.Mock()
        event.is_directory = False
        event.src_path = str(new_file)
        handler.on_any_event(event)

        # Debounce is 100 ms; wait a little longer
        time.sleep(0.15)

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert kwargs["shell"] is True
        assert kwargs["check"] is True
        assert kwargs["cwd"] == str(sample_config.watch_dir)

def test_exclude_pattern(temp_dir: Path, sample_config: WatcherConfig):
    sample_config.exclude = ["*.txt"]
    handler = DebouncedEventHandler(sample_config)
    new_file = temp_dir / "ignore.txt"
    new_file.write_text("should be ignored")
    event = mock.Mock()
    event.is_directory = False
    event.src_path = str(new_file)
    with mock.patch("subprocess.run") as mock_run:
        handler.on_any_event(event)
        time.sleep(0.15)
        mock_run.assert_not_called()
```

**Testing Strategy**

1. **Configuration Loading**
   * Validate that a correct YAML loads into a `WatcherConfig` with expected defaults.
   * Confirm that malformed YAML raises a `ValueError`.

2. **Debounce & Command Execution**
   * Mock `subprocess.run` to avoid actually executing commands.
   * Simulate a file system event and verify that the command is invoked once after the debounce period.
   * Ensure that the command runs in the correct working directory.

3. **Include/Exclude Logic**
   * Test that files matching an exclude pattern never trigger the command.
   * Test that include patterns work as expected.

4. **Integration (Optional)**
   * Run the full `watcher.py` in a subprocess with a temporary config, make changes to files, and assert that the command is executed.  
   * This can be added in a separate `integration_test.py` if desired.

---

## 4. Build & Run Instructions

1. **Create a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the watcher**

   ```bash
   python watcher.py
   ```

   * The tool will read `watcher.yaml` from the current directory.  
   * Use `--config /path/to/watcher.yaml` to specify a different file.  
   * Use `--debug` to enable debug logging.

4. **Run tests**

   ```bash
   pytest test_watcher.py
   ```

   * Ensure the `WorkingDir/` contains some `.py` files to observe real events if you wish to run the integration test.

---

## 5. Deployment / Packaging (Optional)

If the tool should be installable via pip:

```text
# setup.py (minimal)
from setuptools import setup, find_packages

setup(
    name="filewatcher",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "watchdog>=2.0",
        "pyyaml>=5.0",
        "jsonschema>=4.0",
    ],
    entry_points={
        "console_scripts": [
            "filewatcher=watcher:main",
        ],
    },
)
```

Run:

```bash
pip install .
```

Then use:

```bash
filewatcher --config /path/to/watcher.yaml
```

---

## 6. Potential Enhancements (Not Required)

| Feature | Description | Priority |
|---------|-------------|----------|
| Watch multiple directories | Accept a list of watch directories in config | Low |
| Async execution | Use `asyncio` for debouncing instead of a simple flag | Medium |
| Logging to file | Add `--logfile` argument | Low |
| Signal handling | Gracefully shut down on SIGHUP | Low |

These can be added later if needed.

---

**End of Implementation Plan**

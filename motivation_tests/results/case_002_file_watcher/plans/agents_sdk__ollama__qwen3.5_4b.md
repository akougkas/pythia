---
case: case_002_file_watcher
framework: agents_sdk
model: qwen3.5:4b
provider: ollama
session_id: None
duration_ms: 16258
duration_wall_s: 16.3
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T23:08:21.661517+00:00
error: None
---

# Plan

# Implementation Plan: File Watcher CLI Tool (Case 002)

## Overview
Build a Python CLI tool that monitors a directory for file changes using `watchdog`, runs configurable commands on detected changes, with pattern filtering and debouncing.

---

## Phase 1: Dependencies & Environment Setup

### 1.1 Required Python Packages
```bash
# Install dependencies
pip install watchdog pyyaml pytest
```

### 1.2 Working Directory Structure
```
/home/jye/publications/cases/case_002_file_watcher/
├── watcher.py        # Main CLI entry point
├── config.py         # YAML config loader
├── watcher.yaml      # Configuration file
├── test_watcher.py   # Unit tests
├── WorkingDir/       # Directory to monitor
│   ├── src/
│   │   ├── __init__.py
│   │   └── example.py
│   └── tests/
│       └── test_example.py
└── requirements.txt  # Dependencies
```

---

## Phase 2: Configuration File (`watcher.yaml`)

### 2.1 Structure
```yaml
# Path to directory/file to watch
watch:
  paths: ["WorkingDir/src", "WorkingDir/tests"]
  include_patterns:
    - "*.py"
    - "*.txt"
  exclude_patterns:
    - ".pyc"
    - "__pycache__"
    - ".git"
  command:
    path: "pytest"
    module: "test_suite.py"
    args: ["-v", "-x"]
  debounce_ms: 300
watcher:
  mode: "polling"
  recursive: true
  debug: false
```

---

## Phase 3: Core Implementation - `config.py`

### 3.1 Functions to Implement
- `load_config(config_path: str) -> dict`
  - Load YAML configuration file
  - Apply defaults
  - Validate required fields
  
- `get_glob_patterns(patterns: list) -> tuple`
  - Return (included_set, excluded_set) from glob patterns
  
- `validate_command(cmd: dict) -> bool`
  - Ensure command path and args exist

### 3.2 Features
- Use `yaml.safe_load` for loading
- Validate nested structures (command path, args, watch settings)
- Support environment variable override for config path
- Return structured configuration dict

---

## Phase 4: Core Implementation - `watcher.py`

### 4.1 Imports
```python
import argparse
import sys
import time
import threading
from watchdog.events import FileSystemEventHandler, FileSystemMonitor
from watchdog.observers import Observer
import signal
from config import load_config, get_glob_patterns
```

### 4.2 Main Logic Components

#### 4.2.1 Event Handler (`FileSystemEventHandler`)
```python
class EventHandler(FileSystemEventHandler):
    def __init__(self, watch_config, debounce_config):
        self.config = watch_config
        self.debounce = debounce_config.get('debounce_ms', 300)
        self.included, self.excluded = get_glob_patterns(self.config.get('include_patterns', ['*.py']))
        
    def on_event(self, event, event_src, event_name, event_file):
        # Check include/exclude patterns
        # Check debounce timer
        # Run command if changes detected
```

#### 4.2.2 Debounce Mechanism
- Track last event timestamp per path
- 300ms minimum wait before executing command
- Use `time.time()` for timestamp tracking

#### 4.2.3 Command Execution
```python
import subprocess
def run_command(command, config):
    proc = subprocess.Popen(
        [command, '-v'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # Capture and print output
    output, error = proc.communicate(timeout=30)
    return proc.returncode
```

#### 4.2.4 CLI Argument Parsing
```python
parser = argparse.ArgumentParser(description="File Watcher CLI")
parser.add_argument("--config", "-c", default="watcher.yaml")
parser.add_argument("--watch-dir", "-w", required=True)
parser.add_argument("--command", type=str, default="pytest")
args = parser.parse_args()
```

### 4.3 Main Entry Point Structure
```python
def main():
    config = load_config(args.config)
    handler = EventHandler(config)
    observer = Observer()
    observer.schedule(handler, args.watch_dir, recursive=True)
    observer.start()
    try:
        loop()
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
```

---

## Phase 5: Unit Tests (`test_watcher.py`)

### 5.1 Test Categories

#### 5.1.1 Config Loading Tests
- Test YAML with valid structure
- Test YAML with incomplete fields
- Test environment variable override
- Test error handling with malformed YAML

#### 5.1.2 Debounce & Timing Tests
- Test initial debounce timer
- Test rapid change detection
- Test 300ms wait enforcement
- Test multiple rapid events

#### 5.1.3 Pattern Matching Tests
- Test include pattern detection
- Test exclude pattern filtering
- Test mixed include/exclude patterns
- Test recursive pattern matching

#### 5.1.4 Command Execution Tests
- Test successful pytest command
- Test command timeout handling
- Test command return code capture
- Test argument passing to command

#### 5.1.5 Integration Tests
- Test full watch cycle
- Test config loading → handler creation → event detection → command execution
- Test graceful shutdown on Ctrl+C

---

## Phase 6: Final Verification & Validation

### 6.1 Validation Checklist
- [ ] All required files created (`watcher.py`, `config.py`, `watcher.yaml`, `test_watcher.py`)
- [ ] `config.py` loads `watcher.yaml` correctly
- [ ] Debounce is 300ms (or configurable)
- [ ] Include/exclude patterns filter events
- [ ] Command executes on file change
- [ ] CLI accepts `--watch-dir` argument
- [ ] Unit tests pass for all components
- [ ] Test coverage > 85%

---

## Phase 7: Execution Sequence

```python
# 1. Install dependencies
pip install watchdog pyyaml pytest

# 2. Create watcher.yaml
# (See Phase 2)

# 3. Create config.py (Phase 3)

# 4. Create watcher.py (Phase 4)

# 5. Create test_watcher.py (Phase 5)

# 6. Run tests
pytest test_watcher.py -v
```

---

## Expected Deliverables Summary

| File | Purpose | Lines |
|------|---------|-------|
| `watcher.py` | Main CLI entry point | ~200 |
| `config.py` | YAML config loader | ~80 |
| `watcher.yaml` | Example configuration | ~30 |
| `test_watcher.py` | Unit tests | ~180 |
| **Total** | | **~490** |

---

## Success Criteria

- ✅ `watcher.py` runs without CLI arguments error
- ✅ `watcher.py` watches directory on `python watcher.py --watch-dir WorkingDir`
- ✅ Command runs on file modification (verified via test suite)
- ✅ Debounce timer prevents multiple command executions for rapid changes
- ✅ All unit tests pass
- ✅ Configuration is correctly parsed and validated

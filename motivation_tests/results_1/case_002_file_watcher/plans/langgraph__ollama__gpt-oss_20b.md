---
case: case_002_file_watcher
framework: langgraph
model: gpt-oss:20b
provider: ollama
session_id: None
duration_ms: 21078
duration_wall_s: 21.1
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T22:47:38.477588+00:00
error: None
---

# Plan

## Implementation Plan – File Watcher CLI Tool  
*(All steps are **planning only** – no code will be executed.)*

---

### 1. Project Layout (what will exist after the plan is followed)

```
/home/jye/publications/cases/case_002_file_watcher/
├── watcher.py          # CLI entry point
├── config.py           # YAML config loader
├── watcher.yaml        # Example configuration
├── tests/
│   └── test_watcher.py # Unit tests
├── requirements.txt    # Dependencies (watchdog, pyyaml, pytest)
└── WorkingDir/         # Example project to monitor (provided)
```

---

### 2. Assumptions

| Item | Assumption |
|------|------------|
| Python version | ≥ 3.8 (required by `watchdog` and `pyyaml`) |
| Operating system | Linux/Unix (but code will be cross‑platform) |
| `watcher.yaml` location | Same directory as `watcher.py` (or `--config` CLI option) |
| Command to run | A shell command string (e.g., `"pytest"`) |
| Debounce interval | Default 300 ms, configurable via YAML or CLI |
| Include/Exclude patterns | Glob patterns relative to the watched directory |
| Logging | Simple stdout logging is sufficient |

---

### 3. High‑Level Architecture

```
watcher.py
 ├─ parse CLI args (argparse)
 ├─ load config (config.py)
 ├─ create Watcher instance
 └─ start Observer

config.py
 ├─ load YAML
 ├─ validate schema
 └─ expose Config dataclass

watcher.py (continued)
 ├─ Watcher class
 │   ├─ __init__(config, path)
 │   ├─ start()
 │   └─ stop()
 ├─ FileEventHandler (subclass of watchdog.events.FileSystemEventHandler)
 │   ├─ on_modified/on_created/on_moved/on_deleted
 │   └─ debounce logic
 └─ CommandRunner
     ├─ run(command)
     └─ capture output & exit status
```

---

### 4. Detailed Step‑by‑Step Plan

#### 4.1. `requirements.txt`

```
watchdog>=4.0
pyyaml>=6.0
pytest>=7.0
```

#### 4.2. `watcher.yaml` (example)

```yaml
# watcher.yaml – Example configuration
watch_dir: "./WorkingDir"          # Directory to monitor (relative to watcher.py)
include:
  - "**/*.py"                      # Monitor all Python files
exclude:
  - "**/__pycache__/**"            # Exclude byte‑code directories
  - "**/*.tmp"                     # Exclude temporary files
command: "pytest"                  # Command to run on change
debounce_ms: 300                   # Debounce interval in milliseconds
```

#### 4.3. `config.py`

1. **Imports**  
   ```python
   import yaml
   from pathlib import Path
   from dataclasses import dataclass, field
   from typing import List, Optional
   ```

2. **Dataclass**  
   ```python
   @dataclass
   class WatcherConfig:
       watch_dir: Path
       include: List[str] = field(default_factory=lambda: ["**/*"])
       exclude: List[str] = field(default_factory=list)
       command: str = "pytest"
       debounce_ms: int = 300
   ```

3. **Loader Function**  
   ```python
   def load_config(path: Path) -> WatcherConfig:
       with path.open("r") as f:
           data = yaml.safe_load(f) or {}
       # Basic validation & defaults
       watch_dir = Path(data.get("watch_dir", ".")).resolve()
       include = data.get("include", ["**/*"])
       exclude = data.get("exclude", [])
       command = data.get("command", "pytest")
       debounce_ms = int(data.get("debounce_ms", 300))
       return WatcherConfig(
           watch_dir=watch_dir,
           include=include,
           exclude=exclude,
           command=command,
           debounce_ms=debounce_ms,
       )
   ```

4. **Error Handling** – raise `ValueError` if required keys missing or invalid types.

#### 4.4. `watcher.py`

##### 4.4.1. CLI Parsing

```python
import argparse
import sys
from pathlib import Path
from config import load_config, WatcherConfig
```

- `--config FILE` – optional, default `watcher.yaml` in same dir.
- `--debug` – optional flag to enable verbose logging.

##### 4.4.2. Logging Setup

```python
import logging
logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
```

##### 4.4.3. Watcher Class

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import subprocess
from threading import Timer, Lock
```

- **Constructor**  
  - Store `config`, `path` (resolved `watch_dir`), `debounce_ms`.
  - Create `Observer`.
  - Create `FileEventHandler` instance (inner class) passing `self`.

- **start()**  
  - `observer.schedule(handler, path, recursive=True)`
  - `observer.start()`
  - Log “Watching {path} …”

- **stop()**  
  - `observer.stop()`
  - `observer.join()`

##### 4.4.4. FileEventHandler (inner class)

```python
class _EventHandler(FileSystemEventHandler):
    def __init__(self, watcher):
        self.watcher = watcher
        self._timer: Optional[Timer] = None
        self._lock = Lock()
        self._pending = False

    def _schedule(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = Timer(self.watcher.debounce_ms / 1000.0, self._run_command)
            self._timer.start()
            self._pending = True

    def _run_command(self):
        with self._lock:
            self._pending = False
        logging.info(f"Running command: {self.watcher.command}")
        result = subprocess.run(
            self.watcher.command,
            shell=True,
            capture_output=True,
            text=True,
        )
        logging.info(f"Command exited with {result.returncode}")
        if result.stdout:
            logging.info(f"stdout:\n{result.stdout}")
        if result.stderr:
            logging.error(f"stderr:\n{result.stderr}")

    # Override event methods
    def on_any_event(self, event):
        if event.is_directory:
            return
        if not self.watcher._matches(event.src_path):
            return
        self._schedule()
```

- **Pattern Matching** – `watcher._matches(path)` uses `fnmatch.fnmatch` against include/exclude lists.

##### 4.4.5. Pattern Matching Helper

```python
import fnmatch

def _matches(self, path: str) -> bool:
    rel = Path(path).relative_to(self.path)
    # Include check
    if not any(fnmatch.fnmatch(str(rel), pat) for pat in self.config.include):
        return False
    # Exclude check
    if any(fnmatch.fnmatch(str(rel), pat) for pat in self.config.exclude):
        return False
    return True
```

##### 4.4.6. Main Function

```python
def main():
    parser = argparse.ArgumentParser(description="File Watcher CLI")
    parser.add_argument("--config", type=Path, default=Path("watcher.yaml"))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    config = load_config(args.config)
    watcher = Watcher(config)
    try:
        watcher.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Stopping watcher…")
        watcher.stop()
```

- Add `if __name__ == "__main__": main()` guard.

#### 4.5. Unit Tests – `tests/test_watcher.py`

1. **Test Config Loader**  
   - Load a sample YAML string via `yaml.safe_load` and `WatcherConfig`.
   - Verify defaults when keys omitted.
   - Verify error on invalid types.

2. **Test Pattern Matching**  
   - Instantiate a dummy `Watcher` with include/exclude patterns.
   - Call `_matches` with various paths; assert expected boolean.

3. **Test Debounce Logic**  
   - Use `unittest.mock` to patch `subprocess.run`.
   - Simulate rapid file events by calling `on_any_event` multiple times in quick succession.
   - Assert that `subprocess.run` is called only once after debounce interval.

4. **Test Command Execution**  
   - Mock `subprocess.run` to return a known `CompletedProcess`.
   - Verify that stdout/stderr are logged appropriately.

5. **Integration Test (Optional)**  
   - Create a temporary directory with a simple Python file.
   - Start the watcher in a background thread.
   - Modify the file, wait > debounce, check that command ran.

#### 4.6. Development Workflow

1. **Create Virtual Environment**  
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Create Files**  
   - `watcher.py`, `config.py`, `watcher.yaml`, `tests/test_watcher.py`.

3. **Run Tests**  
   ```bash
   pytest tests/
   ```

4. **Run CLI**  
   ```bash
   python watcher.py
   ```

5. **Verify**  
   - Modify a `.py` file in `WorkingDir`.
   - Observe that `pytest` runs automatically after 300 ms.

---

### 5. Edge Cases & Error Handling

| Case | Handling |
|------|----------|
| No `watcher.yaml` | Exit with error message. |
| Invalid YAML syntax | Catch `yaml.YAMLError`, print error, exit. |
| `watch_dir` does not exist | Log warning, create directory, or exit. |
| Command fails (non‑zero exit) | Log error, but continue watching. |
| Rapid events > debounce | Debounce ensures single run. |
| Permission denied on watched files | `watchdog` will raise `PermissionError`; log and ignore. |

---

### 6. Optional Enhancements (not required but useful)

- **Signal Handling** – graceful shutdown on `SIGTERM`.
- **Config Schema Validation** – use `pydantic` or `cerberus`.
- **Multiple Commands** – support a list of commands.
- **Dry‑run Mode** – print command without executing.
- **Cross‑platform Path Normalization** – use `Path` consistently.

---

### 7. Deliverables Summary

| File | Purpose |
|------|---------|
| `watcher.py` | CLI entry point, starts observer. |
| `config.py` | Loads and validates `watcher.yaml`. |
| `watcher.yaml` | Example configuration. |
| `tests/test_watcher.py` | Unit tests covering config, pattern matching, debounce, and command execution. |
| `requirements.txt` | Dependencies. |

---

**End of Plan**

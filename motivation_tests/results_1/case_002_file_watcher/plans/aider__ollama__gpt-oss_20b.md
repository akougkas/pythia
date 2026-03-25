---
case: case_002_file_watcher
framework: aider
model: gpt-oss:20b
provider: ollama
session_id: None
duration_ms: 12865
duration_wall_s: 12.9
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T15:28:10.857879+00:00
error: None
---

# Plan

**Implementation Plan – Case 002: File Watcher**

---

### 1. Project layout

```
case_002_file_watcher/
├── watcher.py          # CLI entry point
├── config.py           # YAML loader & validation
├── watcher.yaml        # Example configuration
├── tests/
│   └── test_watcher.py # Unit tests
├── requirements.txt    # watchdog, pyyaml, pytest
└── README.md
```

---

### 2. `watcher.yaml` – Example configuration

```yaml
# watcher.yaml
command: "pytest tests/"
debounce: 300          # milliseconds
include:
  - "**/*.py"
exclude:
  - "tests/**"
  - "venv/**"
```

*Assumption:* `debounce` is optional; defaults to 300 ms if omitted.

---

### 3. `config.py`

1. **Imports**  
   ```python
   import yaml
   from pathlib import Path
   from typing import List, Dict, Any
   ```

2. **`load_config(path: Path) -> Dict[str, Any]`**  
   * Read YAML file.  
   * Validate required keys: `command`, `include`.  
   * Optional keys: `exclude`, `debounce`.  
   * Convert `debounce` to `int` (ms).  
   * Return a dict with defaults applied.

3. **`validate_patterns(patterns: List[str])`**  
   * Ensure each pattern is a non‑empty string.  
   * Raise `ValueError` if validation fails.

4. **Export**  
   ```python
   __all__ = ["load_config"]
   ```

---

### 4. `watcher.py`

1. **Imports**  
   ```python
   import argparse
   import subprocess
   import sys
   import time
   from pathlib import Path
   from watchdog.observers import Observer
   from watchdog.events import FileSystemEventHandler
   from config import load_config
   ```

2. **Debounce helper**  
   * Class `DebouncedHandler(FileSystemEventHandler)`  
     * Store `last_run: float` (epoch ms).  
     * Store `debounce_ms: int`.  
     * Store `command: str`.  
     * Store `include_patterns: List[str]`, `exclude_patterns: List[str]`.  
     * `on_any_event(event)` → if event.src_path matches include & not exclude → call `_maybe_run()`.  
     * `_maybe_run()` checks current time vs `last_run`; if > debounce → run command via `subprocess.run` (capture output, print). Update `last_run`.

3. **Pattern matching**  
   * Use `Path(event.src_path).match(pattern)` for glob matching.  
   * For include: at least one pattern matches.  
   * For exclude: if any pattern matches → skip.

4. **CLI parsing**  
   * `argparse.ArgumentParser` with options:  
     * `--config PATH` (default `watcher.yaml` in current dir).  
     * `--path PATH` (default `.`).  
     * `--verbose` flag to print events.

5. **Main flow**  
   * Load config via `load_config`.  
   * Resolve `watch_path` to absolute `Path`.  
   * Instantiate `DebouncedHandler` with config values.  
   * Create `Observer`, schedule handler on `watch_path` (recursive).  
   * Start observer, loop `try: while True: time.sleep(1)`; `except KeyboardInterrupt: observer.stop()`.  
   * Join observer.

6. **Entry point**  
   ```python
   if __name__ == "__main__":
       main()
   ```

---

### 5. Unit tests – `tests/test_watcher.py`

1. **Test config loading**  
   * Provide a temporary YAML file with all fields.  
   * Assert returned dict contains expected values.  
   * Test missing required keys raise `ValueError`.  
   * Test default debounce.

2. **Test pattern matching logic**  
   * Instantiate `DebouncedHandler` with known patterns.  
   * Simulate events via `handler.on_any_event` with mock `event` objects (simple `type` and `src_path`).  
   * Verify that `_maybe_run` is called only when include matches and exclude does not.  
   * Use `unittest.mock` to patch `subprocess.run` and check it is called with correct command.

3. **Test debounce**  
   * Trigger two events within debounce interval; ensure `subprocess.run` called only once.  
   * Trigger after interval; ensure second call.

4. **Integration test (optional)**  
   * Create a temporary directory with a file.  
   * Run the watcher in a separate thread/process.  
   * Modify the file; assert command executed.

---

### 6. Dependencies

* `watchdog` – for filesystem monitoring.  
* `pyyaml` – for YAML parsing.  
* `pytest` – for tests.  
* `unittest.mock` – for mocking subprocess.

Add to `requirements.txt`:

```
watchdog>=4.0
pyyaml>=6.0
pytest>=8.0
```

---

### 7. Build & run

```bash
pip install -r requirements.txt
python watcher.py --config watcher.yaml --path WorkingDir
```

---

### 8. Documentation

* Add a brief `README.md` explaining usage, config options, and how to run tests.

---

**Assumptions**

* The command to run is a shell command; executed via `subprocess.run(..., shell=True)`.  
* Debounce is measured in milliseconds; converted to seconds for `time.time()`.  
* Include/exclude patterns use Unix‑style glob syntax (`**` for recursive).  
* The watcher stops cleanly on `Ctrl+C`.

---

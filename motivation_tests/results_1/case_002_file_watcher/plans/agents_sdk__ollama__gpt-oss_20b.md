---
case: case_002_file_watcher
framework: agents_sdk
model: gpt-oss:20b
provider: ollama
session_id: None
duration_ms: 12372
duration_wall_s: 12.4
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T23:08:09.278724+00:00
error: None
---

# Plan

## High‑Level Overview
We will build a small, self‑contained CLI application called **`watcher`** that

1. Loads a `watcher.yaml` configuration file (or defaults).
2. Watches a target directory for file system events with `watchdog`.
3. Debounces rapid changes (default 300 ms).
4. Filters those events with user‑supplied `include` / `exclude` glob patterns.
5. Emits a command (default: `pytest .`) when a change is confirmed.

The codebase will consist of four top‑level modules:

| File | Purpose |
|------|---------|
| `watcher.py` | CLI entry point, command parsing, orchestrator. |
| `config.py` | YAML parser & dataclass representing the configuration. |
| `watcher.yaml` | Example configuration (located next to `watcher.py`). |
| `test_watcher.py` | `pytest` test suite exercising the core logic (not the real OS file system). |

Only standard library and the external dependencies `pyyaml` and `watchdog` will be required.

---

## Detailed Implementation Plan
_All steps are *plan‑only*; no code will be executed here._

### 1. Directory & Package Layout

```
case_002_file_watcher/
├── WorkingDir/            # Provided by the case (unused by code generator)
├── watcher.py
├── config.py
├── watcher.yaml
├── test_watcher.py
└── requirements.txt
```

* `requirements.txt` lists `"watchdog"`, `"PyYAML"`, and `"pytest"` (dev).

---

### 2. `watcher.yaml` – Configuration Schema
Define an example in the repository root:

```yaml
# watcher.yaml
# Directory to monitor (relative/path or absolute)
watch_dir: .

# Command to invoke when a change is detected
command: pytest .

# Debounce delay in milliseconds (default 300)
debounce: 300

# Glob patterns to include (if empty, include all files)
include:
  - "*.py"
  - "tests/**/*.py"

# Glob patterns to exclude (ignored files)
exclude:
  - "venv/**"
  - "__pycache__/**"
```

> **Note**: If a key is missing, sensible defaults are provided (see `config.py`).

---

### 3. `config.py` – Config Loader

**Data Model**

```python
@dataclass
class WatchConfig:
    watch_dir: Path
    command: str = "pytest ."
    debounce: int = 300          # ms
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
```

**Loader Logic**

1. Import `yaml.safe_load`.
2. Resolve `watch_dir` to an absolute `Path`; if omitted, use current working dir.
3. Merge defaults via `dataclasses.replace()` or manual `dict.get(key, default)`.
4. Validate that `debounce` is an integer > 0; raise `ValueError` otherwise.
5. Provide a helper `load_config(path: Path | None = None) -> WatchConfig`.

**Error Handling**

- If `watcher.yaml` is missing, raise `FileNotFoundError`.
- If YAML is malformed, raise `yaml.YAMLError`.
- Convert `debounce` to `int` and clamp to range 50–5000 ms.

---

### 4. `watcher.py` – CLI Entry Point

#### 4.1 Imports
```python
import argparse
import subprocess
from pathlib import Path
import sys
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from config import load_config, WatchConfig
```

#### 4.2 Debounced Event Handler

```python
class DebounceHandler(FileSystemEventHandler):
    def __init__(self, config: WatchConfig, run_command: Callable[[], None]):
        super().__init__()
        self.config = config
        self.run_command = run_command
        self.lock = threading.Lock()
        self.timer: Optional[threading.Timer] = None
        self.pending = False
```

**Event Filtering**

```python
    def _matches(self, path: Path) -> bool:
        normalized = str(path.relative_to(self.config.watch_dir))
        # Skip directories
        if path.is_dir():
            return False
        # Exclude first
        for pat in self.config.exclude:
            if fnmatch.fnmatch(normalized, pat):
                return False
        # Include check
        if not self.config.include:
            return True
        return any(fnmatch.fnmatch(normalized, pat) for pat in self.config.include)
```

**Event Handling**

```python
    def on_any_event(self, event: FileSystemEvent):
        if not self._matches(Path(event.src_path)):
            return
        with self.lock:
            self.pending = True
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.config.debounce / 1000, self._trigger)
            self.timer.start()
```

**Trigger Execution**

```python
    def _trigger(self):
        with self.lock:
            if self.pending:
                self.pending = False
                self.run_command()
```

#### 4.3 Command Runner

```python
def run_shell_command(command: str):
    print(f"\n[watcher] Running: {command}")
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"[watcher] Command failed with exit code {exc.returncode}", file=sys.stderr)
```

#### 4.4 Main CLI Logic

```python
def main():
    parser = argparse.ArgumentParser(description="Watch a directory and run a command on changes.")
    parser.add_argument("--config", "-c", type=Path, default=Path("watcher.yaml"),
                        help="Path to config YAML (default: watcher.yaml)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print debug info")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print("Configuration:")
        print(config)

    # Set up observer
    event_handler = DebounceHandler(config, lambda: run_shell_command(config.command))
    observer = Observer()
    observer.schedule(event_handler, str(config.watch_dir), recursive=True)
    observer.start()

    print(f"[watcher] Watching {config.watch_dir} ... Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[watcher] Stopping...")
    finally:
        observer.stop()
        observer.join()
        sys.exit(0)
```

#### 4.5 Expose `__main__`

```python
if __name__ == "__main__":
    main()
```

---

### 5. `test_watcher.py` – Unit Tests

We cannot test real filesystem activity in CI; instead we will *mock* the `watchdog` observer and event flow.

#### 5.1 Test Layout

```python
import pytest
from unittest import mock
from pathlib import Path
from config import WatchConfig, load_config
from watcher import DebounceHandler, run_shell_command
import threading
import time
```

#### 5.2 Helper Mock Event

```python
class MockEvent:
    def __init__(self, src_path: str):
        self.src_path = src_path
```

#### 5.3 Test Cases

| Test | Description |
|------|-------------|
| `test_config_loading_defaults()` | Verify default config values when only minimal YAML is provided. |
| `test_config_loading_custom()` | Verify user config overrides (custom debounce, include/exclude). |
| `test_event_filtering()` | Ensure `DebounceHandler._matches()` correctly applies include/exclude globs. |
| `test_debounce_mechanism()` | Simulate rapid events (< debounce) and ensure only one command executed. |
| `test_debounce_trigger_on_gap()` | Simulate spaced events > debounce; expect two command executions. |
| `test_non_file_events_ignored()` | Directory creation events ignored. |
| `test_command_execution()` | Mock `subprocess.run` and assert call with expected command. |
| `test_invalid_yaml()` | Malformed YAML raises `yaml.YAMLError`. |

##### Key Testing Techniques

- **`mock.patch`** for `subprocess.run` and for the `threading.Timer` inside `DebounceHandler` to avoid real waiting.
- Use `pytest` fixtures to create temporary `watcher.yaml` files with `tmp_path`.
- Use `time.sleep` *only inside tests that actually delay*; otherwise mock time or timers.
- Capture `stdout` via `capsys` to assert printed messages.

#### 5.4 Example Snippet: Debounce Test

```python
def test_debounce_mechanism(monkeypatch, tmp_path):
    # Arrange
    conf = WatchConfig(
        watch_dir=tmp_path,
        command="echo hi",
        debounce=200,
        include=[],
        exclude=[]
    )

    called = []

    def fake_run(command):
        called.append(command)

    handler = DebounceHandler(conf, fake_run)

    # Mock Timer to call trigger immediately (simulate no wait)
    class FakeTimer:
        def __init__(self, interval, function):
            self.function = function
        def start(self):
            self.function()
        def cancel(self):
            pass

    monkeypatch.setattr(threading, "Timer", FakeTimer)

    # Act: Emit two events quickly
    event1 = MockEvent(str(tmp_path / "a.py"))
    event2 = MockEvent(str(tmp_path / "b.py"))
    handler.on_any_event(event1)
    handler.on_any_event(event2)

    # Assert: Only one command execution
    assert called == ["echo hi"]
```

---

### 6. Additional Deliverables

| File | What to include |
|------|-----------------|
| `requirements.txt` | `watchdog`, `pyyaml`, `pytest` |
| `README.md` | Usage instructions, `watcher`, example config, how to run tests |
| `.gitignore` | Python build artefacts, `__pycache__`, `*.pyc`, `venv/` |

---

### 7. Build & Run Guide (for developers)

```bash
# Virtualenv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run watcher
python watcher.py

# Test
pytest test_watcher.py
```

You may also use `python -m watcher` if the file is marked executable or add a console_script entry in `setup.cfg` (outside scope).

---

### 8. Assumptions & Clarifications

| Assumption | Reason |
|------------|--------|
| `watcher.yaml` resides at project root | Standard for CLI tools |
| `--config` option accepts absolute or relative path | User convenience |
| `observer.schedule(..., recursive=True)` | Most monitoring use‑cases require subdirectories |
| Debounce threshold is given in **milliseconds** | Matches requirement; converted to seconds internally |
| Commands run via `shell=True` | Allows complex shell commands (e.g., pipenv run) |
| Tests use `tmp_path` for isolation | Keeps filesystem clean |
| `watcher.yaml` may omit optional keys | Defaults are applied |

---

## Final Checklist

- [ ] `watcher.py` implements CLI, observer, debounce logic.
- [ ] `config.py` contains robust YAML loader with validation.
- [ ] `watcher.yaml` demonstrates all config fields.
- [ ] `test_watcher.py` covers all major behaviours using mocks.
- [ ] `requirements.txt` lists external dependencies.
- [ ] README with usage examples and test instructions.

Once this plan is followed, the repository will contain a fully functional, tested command‑line file‑watcher as specified in **Case 002**.

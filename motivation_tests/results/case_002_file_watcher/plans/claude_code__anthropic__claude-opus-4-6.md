---
case: case_002_file_watcher
framework: claude_code
model: claude-opus-4-6
provider: anthropic
session_id: 6d20b76a-4bea-4da3-8baa-a730f44efefe
duration_ms: 163419
duration_wall_s: 168.1
cost_usd: 0.4056711
num_turns: 6
timestamp: 2026-03-19T14:02:22.262458+00:00
error: None
---

# Plan

# Plan: File Watcher CLI Tool

## Context
Create a Python CLI tool in `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/` that monitors a directory for file changes and auto-runs a configurable command. The WorkingDir is currently empty — all four files are created from scratch.

**Dependencies:** `watchdog`, `PyYAML` (external); `dataclasses`, `fnmatch`, `os`, `sys`, `time`, `threading`, `subprocess`, `argparse`, `unittest`, `unittest.mock` (stdlib).

---

## Step 1: Create `watcher.yaml` — example configuration

```yaml
watch_directory: "."
command: "python -m pytest"
include_patterns:
  - "*.py"
exclude_patterns:
  - "__pycache__/*"
  - ".*"
recursive: true
debounce_ms: 300
```

All fields have defaults except `command` (required).

---

## Step 2: Create `config.py` — YAML config loader

- **`class ConfigError(Exception)`** — custom error for config issues
- **`@dataclass class WatcherConfig`** with fields:
  - `watch_directory: str = "."`
  - `command: str = ""`
  - `include_patterns: list[str] = ["*"]`
  - `exclude_patterns: list[str] = []`
  - `debounce_ms: int = 300`
  - `recursive: bool = True`
- **`load_config(path: str) -> WatcherConfig`**:
  - Read file (catch `FileNotFoundError` → `ConfigError`)
  - `yaml.safe_load()` — reject `None`/non-dict results
  - Validate `command` is non-empty string, `debounce_ms` is non-negative int, patterns are lists of strings
  - Return populated `WatcherConfig`

---

## Step 3: Create `watcher.py` — main CLI entry point

### 3a. Pattern matching helpers
- `matches_any(filename, patterns) -> bool` — `fnmatch` against list
- `should_process(filepath, config) -> bool` — exclude takes priority over include; matches against `os.path.basename(filepath)`

### 3b. Command runner
- `run_command(command: str)` — `subprocess.run(command, shell=True)`, prints status, never raises

### 3c. `DebouncedEventHandler(FileSystemEventHandler)`
- `__init__(config)` — stores config, `_timer: Timer | None = None`, `_lock = threading.Lock()`
- `on_any_event(event)` — skip directory events, skip non-matching files via `should_process()`, call `_schedule_run()`
- `_schedule_run()` — under lock: cancel existing timer, start new `threading.Timer(debounce_ms/1000, self._execute)` as daemon
- `_execute()` — calls `run_command(self.config.command)`

### 3d. CLI
- `parse_args()` — `argparse` with `--config/-c` (default `watcher.yaml`)
- `main()`:
  - Load config, validate watch directory exists
  - Create handler + `Observer`, schedule, start
  - Print status, enter `while True: sleep(1)` loop
  - `KeyboardInterrupt` → `observer.stop(); observer.join()`

---

## Step 4: Create `test_watcher.py` — unit tests

### `TestConfig` (7 tests)
| Test | Validates |
|---|---|
| `test_load_valid_config` | All fields parse correctly |
| `test_load_minimal_config` | Only `command` → defaults applied |
| `test_load_missing_file` | Raises `ConfigError` |
| `test_load_invalid_yaml` | Raises `ConfigError` |
| `test_load_empty_file` | Raises `ConfigError` |
| `test_load_missing_command` | Raises `ConfigError` |
| `test_load_invalid_debounce` | Negative value raises `ConfigError` |

Technique: `tempfile.NamedTemporaryFile` with real YAML content.

### `TestPatternMatching` (5 tests)
| Test | Validates |
|---|---|
| `test_include_matches` | `*.py` includes `.py`, excludes `.txt` |
| `test_exclude_matches` | `*.pyc` rejected |
| `test_exclude_overrides_include` | Both match → rejected |
| `test_empty_include_matches_all` | `["*"]` matches everything |
| `test_empty_exclude_blocks_nothing` | Empty list blocks nothing |

Technique: Construct `WatcherConfig` directly, call `should_process()`.

### `TestDebounce` (3 tests)
| Test | Validates |
|---|---|
| `test_single_event_triggers_command` | One event → command runs once |
| `test_rapid_events_trigger_once` | Burst of events → one execution |
| `test_spaced_events_trigger_multiple` | Separated events → multiple executions |

Technique: Mock `run_command`, use 50ms debounce, `time.sleep()` with 4x margin.

### `TestEventHandler` (3 tests)
| Test | Validates |
|---|---|
| `test_directory_event_ignored` | `is_directory=True` skipped |
| `test_excluded_file_ignored` | Excluded file skipped |
| `test_included_file_processed` | Matching file triggers debounce |

Technique: Mock `_schedule_run` to isolate filtering from timing.

---

## Step 5: Install dependencies & verify

```bash
pip install watchdog PyYAML
cd /home/jye/publications/cases/case_002_file_watcher/WorkingDir
python -m pytest test_watcher.py -v        # run unit tests
python watcher.py --help                    # verify CLI works
python watcher.py                           # manual smoke test (Ctrl+C to stop)
```

---

## Implementation Order
1. `watcher.yaml`
2. `config.py`
3. `watcher.py`
4. `test_watcher.py`
5. Install deps + run tests

